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
        # Streaming state tracking for UI updates
        self.last_update_time = 0
        self.update_interval = 1.2  # Seconds between Slack updates

    def handle(self, event, say, client, thread_ts, req_headers=None):
        
        # Ignore bot messages
        if event.get("bot_id"):
            return
        
        raw_text = event.get("text", "")
        # Check if there is no text and files to ignore ghost events
        # This happens when AI uses tool to read websites inside them and the delay there 
        # causes Slack to send an empty message event with just files and no text, which can trigger unwanted threads
        if not raw_text and "files" not in event:
            print("DEBUG: Ignored epmty ghost event with no text and no files.")
            return
        
        # Get Bot Identity
        auth_info = client.auth_test()
        bot_user_id = auth_info["user_id"]
        user_info = client.users_info(user=bot_user_id)
        bot_name = user_info["user"]["real_name"]

        conv_id = event.get("channel")
        #user_id = event.get("user")
        # Reset tool flags
        self.llm_service.memory_tool.memory_saved = False
        self.llm_service.memory_tool.memory_recalled = False
        self.llm_service.memory_tool.memory_saved_failed = False
        self.llm_service.memory_tool.memory_recalled_failed = False
        self.llm_service.python_tool.code_executed = False
        self.llm_service.python_tool.code_failed = False
        self.llm_service.comfy_image_tool.is_generating = False
        self.llm_service.comfy_image_tool.generation_failed = False
        self.llm_service.music_generation_tool.generation_failed = False
        self.llm_service.music_generation_tool.is_generating = False
        self.llm_service.read_url_tool.website_read_success = False
        self.llm_service.read_url_tool.website_read_failed = False

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
        print(f"\n--- Decision: {status} ---")
        print(f"Reason: {reason}")
        print(f"Message: '{raw_text.strip()}'")
        print(f"--------------------------")

        if not should_respond:
            return
        
        # Strip bot mention from user input
        user_input = re.sub(r'<@.*?>', '', raw_text).strip()

        # If text is empty and there are no files, ignore the message
        if not user_input and not event.get("files"):
            return


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

        client.chat_update(channel=conv_id, ts=msg_ts, text="_Thinking..._")

        # --- STREAMING CALLBACK ---
        def slack_stream_callback(content, is_final=False):
            now = time.time()
            if is_final or (now - self.last_update_time > self.update_interval):
                text_to_display = content
                attachments = []

                if is_final:
                    status_tags = []
                    # Python Tool Status
                    if self.llm_service.python_tool.code_executed: 
                        status_tags.append("`[Python Executed]`")
    
                    if self.llm_service.python_tool.code_failed:
                        status_tags.append("`[Python Tool Failed]` _Check connection or if service is running._")
                    # ComfyUI Status
                    if self.llm_service.comfy_image_tool.is_generating:
                        status_tags.append("`[Image Generating]`")

                    if self.llm_service.comfy_image_tool.generation_failed:
                        status_tags.append("`[ComfyUI Failed]` _Check connection or if service is running._")

                    # MusicGen Status
                    if self.llm_service.music_generation_tool.is_generating:
                        status_tags.append("`[Music Generation]`")

                    if self.llm_service.music_generation_tool.generation_failed:
                        status_tags.append("`[MusicGen Failed]` _Check connection or if service is running._")
                    # Memory Status
                    if self.llm_service.memory_tool.memory_saved: 
                        status_tags.append("`[Memory Saved]`")

                    if self.llm_service.memory_tool.memory_saved_failed:
                        status_tags.append("`[Memory Save Failed]` _There is no memory saved yet or embedding model name is wrong._")
                    
                    if self.llm_service.memory_tool.memory_recalled: 
                        status_tags.append("`[Memory Recalled]`")

                    if self.llm_service.memory_tool.memory_recalled_failed:
                        status_tags.append("`[Memory Recall Failed]` _There is no memory saved yet or embedding model name is wrong._")

                    # Website Reader Status
                    if self.llm_service.read_url_tool.website_read_success:
                        status_tags.append("`[Website Read]`")

                    if self.llm_service.read_url_tool.website_read_failed:
                        status_tags.append("`[Read Failed]` _Site blocked me, link was empty, or not enough info found._")
                    
                    if status_tags:
                        text_to_display += "\n\n" + " ".join(status_tags)

                    provider, search_links = self.llm_service.get_latest_search_info()
                    if search_links:
                        attachments.append({
                            "color": "#36a64f",
                            "title": f"🌐 Research Sources ({provider})",
                            "text": "\n".join([f"• {link}" for link in search_links])
                        })
                else:
                    text_to_display += " ▌"

                try:
                    client.chat_update(
                        channel=conv_id,
                        ts=msg_ts,
                        text=text_to_display or "...",
                        attachments=attachments
                    )
                    self.last_update_time = now
                except Exception as e:
                    print(f"Streaming Error: {e}")

        # --- WORKER THREAD ---
        def run_streaming_worker():
            try:
                self.llm_service.generate_reply_stream(
                    conversation_id=conv_id,
                    prompt=user_input,
                    callback_fn=slack_stream_callback,
                    images=file_images
                )
                
                # Start watchers if needed
                if self.llm_service.comfy_image_tool.is_generating:
                    threading.Thread(target=self._image_watcher_thread, args=(conv_id, client, thread_ts), daemon=True).start()
                if self.llm_service.music_generation_tool.is_generating:
                    threading.Thread(target=self._music_watcher_thread, args=(conv_id, client, thread_ts), daemon=True).start()
            
            except Exception as e:
                print(f"Generation Error: {e}")
                client.chat_update(channel=conv_id, ts=msg_ts, text="I encountered an error processing this group request.")

        threading.Thread(target=run_streaming_worker, daemon=True).start()

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
        path = self.llm_service.config.COMFYUI_IMAGE_PATH
        api_url = self.llm_service.comfy_image_tool.api_url
        prompt_id = getattr(self.llm_service.comfy_image_tool, "latest_prompt_id", None)
        initial_files = set(os.listdir(path))
        total_nodes = 11 

        progress_msg = client.chat_postMessage(
            channel = channel, thread_ts = thread_ts, text = "⏳ *ComfyUI:* Initializing..."
        )
        progress_ts = progress_msg["ts"]
        # 300 = 15 minutes max (3 sec sleep * 300 loops)
        for i in range(300): 
            time.sleep(3)
            
            percent_complete = 0

            if prompt_id:
                try:
                    resp = requests.get(f"{api_url}/prompt")
                    if resp.status_code == 200:
                        data = resp.json()
                        exec_info = data.get("executing", {})
                    
                        if exec_info.get("prompt_id") == prompt_id:
                            current_node = str(exec_info.get("node"))
                            
                            try:
                                node_idx = int(current_node)
                                percent_complete = min(int((node_idx / total_nodes) * 100), 99)
                            except:
                                percent_complete = 50
                except:
                    pass

            # Logic for progress bar
            display_pct = percent_complete if percent_complete > 0 else min(i * 3, 95)
            bar_length = 10
            filled = int((display_pct / 100) * bar_length)
            bar = "■" * filled + "□" * (bar_length - filled)
        
            try:
                client.chat_update(
                    channel = channel,
                    ts = progress_ts,
                    text = f"🎨 *ComfyUI Progress:* `[{bar}]` *{display_pct}%*)"
                )
            except Exception:
                pass

            
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files
            if new_files:
                png_files = [os.path.join(path, f) for f in new_files if f.endswith('.png')]
                if png_files:
                    time.sleep(1.5) # Wait for file to finish writing
                    latest_image = max(png_files, key = os.path.getctime)
                    try:
                        client.chat_update(
                            channel = channel, ts = progress_ts, 
                            text = f"🎨 *ComfyUI Progress:* `[■■■■■■■■■■]` *100%* (Done!)"
                        )
                        time.sleep(0.5)
                        client.chat_delete(channel = channel, ts = progress_ts)
                    
                        client.files_upload_v2(
                            channel = channel, thread_ts = thread_ts,
                            file = latest_image, title = "AI Generated Image",
                            initial_comment = "🎨 *Image ready:*"
                        )
                    except Exception as e:
                        print(f"Upload failed: {e}")
                    return 

        client.chat_update(channel=channel, ts=progress_ts, text="❌ *ComfyUI:* Timed out.")
                
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
            response = self.llm_service.quick_query(decision_prompt).strip().lower()
            
            # Strict cleaning to catch "yes"
            # Some LLMs might say "Yes." or "Decision: yes"
            is_yes = response.startswith("yes") or response == "y"
            
            return is_yes
        except Exception as e:
            # If the LLM call fails, we print the error and default to False (Ignore)
            print(f"[Decision Fallback] Error: {e}")
            return False
        
    