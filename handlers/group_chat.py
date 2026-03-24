import threading
import os
import time
import re
import requests
import base64
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

class GroupChatHandler:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    def handle(self, event, say, client, thread_ts):
        if event.get("bot_id") is not None:
            return
        
        # Get Bot Identity
        auth_info = client.auth_test()
        bot_user_id = auth_info["user_id"]
        user_info = client.users_info(user=bot_user_id)
        bot_name = user_info["user"]["real_name"]

        conv_id = event.get("channel")
        #user_id = event.get("user")
        raw_text = event.get("text", "")

        # --- DECISION LOGIC ---
        should_respond = False
        reason = ""

        # Check for Direct Tag
        if f"<@{bot_user_id}>" in raw_text:
            should_respond = True
            reason = "[FORCED: Tagged]"
        
        # Check for Thread Reply (if the bot started/joined the thread)
        elif event.get("thread_ts") and event.get("parent_user_id") == bot_user_id:
            should_respond = True
            reason = "[FORCED: Thread Reply]"

        # Fallback to AI Decision Agent
        if not should_respond:
            should_respond = self._ai_wants_to_respond(raw_text, bot_name)
            reason = "[CHOICE: AI Decision]" if should_respond else "[SKIP: AI Ignored]"

        status = "RESPONDING" if should_respond else "IGNORING"
        print(f"--- Decision: {status} ---")
        print(f"Reason: {reason}")
        print(f"Message: '{raw_text.strip()}'")
        print(f"--------------------------")

        # Exit early if we aren't responding
        if not should_respond:
            return
        # --- Proceed with Response ---
        
        # Strip bot mention from user input
        user_input = re.sub(r'<@.*?>', '', raw_text).strip()

        # Initial Placeholder
        initial_msg = client.chat_postMessage(
            channel=conv_id, 
            thread_ts=thread_ts,
            text="_Initializing group request..._"
        )
        msg_ts = initial_msg["ts"]

        # File Processing
        file_texts = []
        file_images = []
        if "files" in event:
            
            file_texts, file_images = self._process_files(event["files"], client)
            
            if file_texts:
                user_input = (
                    "IMPORTANT: The user has provided the following document context.\n"
                    "--- START OF DOCUMENT ---\n"
                    f"{file_texts}\n"
                    "--- END OF DOCUMENT ---\n\n"
                    f"USER QUESTION: {user_input if user_input else 'Please analyze these files.'}"
                )

        # Invoke Agent (Non-Streaming)
        client.chat_update(channel=conv_id, ts=msg_ts, text="_Thinking..._")
        # Flags
        self.llm_service.comfy_image_tool.is_generating = False
        self.llm_service.music_generation_tool.is_generating = False

        try:
            final_text = self.llm_service.generate_reply(conv_id, user_input, images = file_images)
        except Exception as e:
            print(f"Group LLM Error: {e}")
            final_text = "I'm sorry, I hit a snag while processing that group request."

        # Handle Search Sources (Attachments)
        attachments = []
        serper_links = getattr(self.llm_service.serper_web_search_tool, 'latest_links', [])
        if serper_links:
            attachments.append({
                "color": "#36a64f",
                "title": "🔗 Research Sources",
                "text": "\n".join([f"• {link}" for link in serper_links])
            })
            self.llm_service.serper_web_search_tool.latest_links = []

        # Final UI Update
        # Ensures that even if final_text is weirdly empty, the "Thinking" text is replaced
        display_text = final_text if (final_text and final_text.strip()) else "Processed."
        client.chat_update(
            channel=conv_id, 
            ts=msg_ts, 
            text=display_text, 
            attachments=attachments
        )

        # Post-Response Image Watcher
        if self.llm_service.comfy_image_tool.is_generating:
            threading.Thread(
                target=self._image_watcher_thread, 
                args=(conv_id, client, thread_ts),
                daemon=True
            ).start()

        if self.llm_service.music_generation_tool.is_generating:
            threading.Thread(
                target=self._music_watcher_thread, 
                args=(conv_id, client, thread_ts),
                daemon=True
        ).start()

    def _process_files(self, files, client):
        extracted_text = []
        extracted_images = []
        token = client.token

        for file_info in files:
            file_url = file_info.get("url_private_download")
            if not file_url:
                continue

            file_name = file_info.get("name")
            temp_path = f"temp_{int(time.time())}_{file_name}"
            extension = os.path.splitext(file_name)[1].lower()

            try:
                resp = requests.get(
                    file_url,
                    headers={"Authorization": f"Bearer {token}"},
                    stream=True
                )

                if resp.status_code != 200:
                    continue

                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                time.sleep(0.3)

                # TEXT FILES
                if extension == ".pdf":
                    loader = PyPDFLoader(temp_path)
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                    extracted_text.append(f"--- FILE: {file_name} ---\n{content}")

                elif extension in [".docx", ".doc"]:
                    loader = Docx2txtLoader(temp_path)
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                    extracted_text.append(f"--- FILE: {file_name} ---\n{content}")

                elif extension in [".txt", ".md", ".py", ".json", ".csv"]:
                    loader = TextLoader(temp_path, encoding="utf-8")
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                    extracted_text.append(f"--- FILE: {file_name} ---\n{content}")

                # IMAGE FILES
                elif extension in [".png", ".jpg", ".jpeg"]:
                    with open(temp_path, "rb") as img_file:
                        encoded = base64.b64encode(img_file.read()).decode("utf-8")
                        extracted_images.append({
                            "filename": file_name,
                            "base64": encoded
                        })

                else:
                    print(f"Unsupported file type: {extension}")

            except Exception as e:
                print(f"Error processing {file_name}: {e}")

            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        print(f"Could not delete temp file: {e}")

        return extracted_text, extracted_images

    
    def _image_watcher_thread(self, channel, client, thread_ts):
        """Monitors folder for new images and uploads them as a standalone message in the group."""
        path = self.llm_service.config.COMFYUI_IMAGE_PATH
        initial_files = set(os.listdir(path))
        
        # Poll for up to 10 minutes
        for _ in range(200):
            time.sleep(3)
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files
            
            if new_files:
                png_files = [os.path.join(path, f) for f in new_files if f.endswith('.png')]
                if png_files:
                    time.sleep(1) # Buffer for saving
                    latest_image = max(png_files, key=os.path.getctime)
                    
                    try:
                        client.files_upload_v2(
                            channel=channel,
                            file=latest_image,
                            thread_ts=thread_ts,
                            title="AI Generated Image",
                        )
                    except Exception as e:
                        print(f"Group upload failed: {e}")
                    return
                
    def _music_watcher_thread(self, channel, client, thread_ts):
        """Watches for a new .wav file and uploads it to the Slack thread."""
        path = self.llm_service.config.MUSIC_GENERATION_PATH 
        
        if not os.path.exists(path):
            print(f"ERROR: Music path does not exist: {path}")
            return

        initial_files = set(os.listdir(path))
        
        # Search for up to 5 minutes (100 loops * 3 seconds)
        for _ in range(100):
            time.sleep(3)
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files
            
            if new_files:
                # Filter for .wav files
                wav_files = [os.path.join(path, f) for f in new_files if f.lower().endswith('.wav')]
                if wav_files:
                    # Small buffer to ensure the file is completely written to disk
                    time.sleep(1) 
                    latest_audio = max(wav_files, key=os.path.getctime)
                    
                    try:
                        client.files_upload_v2(
                            channel=channel,
                            thread_ts=thread_ts,
                            file=latest_audio,
                            title="AI Generated Music",
                            initial_comment="*Your music is ready!*"
                        )
                    except Exception as e:
                        print(f"Music upload failed: {e}")
                    return # Exit thread after successful upload
                    
        print(f"Music generation timed out for channel {channel}")

    def _ai_wants_to_respond(self, last_message, bot_name):
        """Replicates the strict Decision Agent logic."""
        prompt_bot_name = f"{bot_name}, AI, Bot, Assistant"
        
        # This matches your specific C# string interpolation logic
        decision_prompt = (
            "You are a decision agent.\n"
            "Your ONLY job is to decide if the AI should respond to the **LAST message below**.\n"
            "Ignore all earlier messages.\n"
            "Focus ONLY on the last line. Output 'yes' or 'no'.\n\n"
            "CONTEXT:\n"
            "- This is a Slack group chat.\n"
            f"- The AI's name or nicknames: [{prompt_bot_name}]\n\n"
            "RESPOND with 'yes' if **ANY** are true for the LAST MESSAGE:\n"
            f"1. It mentions the AI by name/nickname (e.g., AI, bot, assistant, {bot_name})\n"
            "2. It is a direct question (contains ?, or words like 'what', 'how', 'help', 'tell me')\n"
            "3. It is a direct command/request (e.g., 'respond', 'talk to me', 'answer')\n\n"
            "RESPOND with 'no' if:\n"
            "- The last message is just 'hi', 'hello', 'hey' with NO name/tag.\n"
            "- It says 'stop', 'shut up', etc.\n\n"
            f"**LAST MESSAGE TO EVALUATE:** {last_message}"
        )

        try:
            # Call the quick_query method in your llm_service
            response = self.llm_service.quick_query(decision_prompt).strip().lower()
            
            # Strict cleaning to ensure we only catch "yes"
            # Some LLMs might say "Yes." or "Decision: yes", so we check starts_with
            is_yes = response.startswith("yes") or response == "y"
            
            return is_yes
        except Exception as e:
            # If the LLM call fails, we print the error and default to False (Ignore)
            print(f"[Decision Fallback] Error: {e}")
            return False
        
    