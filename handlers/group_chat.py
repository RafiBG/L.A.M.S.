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
        
        conv_id = event.get("channel")
        user_id = event.get("user")
        raw_text = event.get("text", "")
        
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

        # Return must be OUTSIDE the loop
        return extracted_text, extracted_images

    
    def _image_watcher_thread(self, channel, client, thread_ts):
        """Monitors folder for new images and uploads them as a standalone message in the group."""
        path = self.llm_service.config.COMFYUI_IMAGE_PATH
        initial_files = set(os.listdir(path))
        
        # Poll for up to 4.5 minutes
        for _ in range(90):
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
        # Ensure your Config class has MUSIC_GENERATION_PATH (the folder where Flask saves)
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