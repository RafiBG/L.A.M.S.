import threading
import os
import time
import requests
import base64
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

class PrivateChatHandler:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    def handle(self, event, say, client):
        if event.get("bot_id"):
            return

        conv_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        user_id = event.get("user")
        raw_text = event.get("text", "")
        user_input = raw_text.strip()

        if user_input.lower().startswith("!forget"):
            return self._handle_forget_command(conv_id, thread_ts, client)
        
        if user_input.lower().startswith("!help"):
            return self._handle_help_command(conv_id, thread_ts, client)

        # Post placeholder
        initial_msg = client.chat_postMessage(
            channel=conv_id, 
            text="_Initializing..._",
            thread_ts=thread_ts 
        )
        msg_ts = initial_msg["ts"]

        # File Processing (Text + Images)
        file_texts, file_images = [], []

        if "files" in event:
            client.chat_update(channel=conv_id, ts=msg_ts, text="_Reading files..._")
            file_texts, file_images = self._process_files(event["files"], client)

            if file_texts:
                # Include the text content for context
                user_input = (
                    "IMPORTANT: The user has uploaded a document. Use the following text to answer the question.\n"
                    "--- START OF DOCUMENT ---\n"
                    f"{file_texts}\n"
                    "--- END OF DOCUMENT ---\n\n"
                    f"USER QUESTION: {user_input if user_input else 'Please summarize this document.'}"
                )
            else:
                # Debug info
                print("DEBUG: File extraction resulted in no text.")

        # Get LLM Response
        client.chat_update(channel=conv_id, ts=msg_ts, text="_Thinking..._")

        self.llm_service.comfy_image_tool.is_generating = False
        self.llm_service.music_generation_tool.is_generating = False

        try:
            # Pass images to LLM so it can analyze them
            final_text = self.llm_service.generate_reply(conv_id, user_input, images=file_images)
        except Exception as e:
            print(f"LLM Error: {e}")
            final_text = "Sorry, I had trouble processing that request."

        # Search sources (Attachments)
        attachments = []
        serper_links = getattr(self.llm_service.serper_web_search_tool, 'latest_links', [])
        if serper_links:
            attachments.append({
                "color": "#36a64f",
                "title": "🔗 Research Sources",
                "text": "\n".join([f"• {link}" for link in serper_links])
            })
            # Clear links after use so they don't appear in the next message
            self.llm_service.serper_web_search_tool.latest_links = []

        # Final update with attachments
        client.chat_update(
            channel=conv_id, 
            ts=msg_ts, 
            text=final_text if final_text.strip() else "Done.",
            attachments=attachments
        )

        # Image watcher
        if self.llm_service.comfy_image_tool.is_generating:
            threading.Thread(
                target=self._image_watcher_thread, 
                args=(conv_id, client, thread_ts),
                daemon=True
            ).start()

        # Music watcher
        if self.llm_service.music_generation_tool.is_generating:
            threading.Thread(
                target=self._music_watcher_thread, 
                args=(conv_id, client, thread_ts), 
                daemon=True
            ).start()

    def _image_watcher_thread(self, channel, client, thread_ts):
        path = self.llm_service.config.COMFYUI_IMAGE_PATH
        initial_files = set(os.listdir(path))
        for _ in range(90):
            time.sleep(3)
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files
            if new_files:
                png_files = [os.path.join(path, f) for f in new_files if f.endswith('.png')]
                if png_files:
                    time.sleep(1)
                    latest_image = max(png_files, key=os.path.getctime)
                    try:
                        client.files_upload_v2(
                            channel=channel,
                            thread_ts=thread_ts,
                            file=latest_image,
                            title="AI Generated Image",
                            initial_comment="🎨 *Image ready:*"
                        )
                    except Exception as e:
                        print(f"Image upload failed: {e}")
                    return

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
    
    def _handle_forget_command(self, conv_id, thread_ts, client):
            """Clears the LLM memory for the specific conversation."""
            self.llm_service.clear_memory(conv_id)
            client.chat_postMessage(
                channel=conv_id,
                text="*Memory Cleared:* I've forgotten our previous context in this channel.",
                thread_ts=thread_ts
        )

    def _handle_help_command(self, conv_id, thread_ts, client):
        """Sends a help menu to the user."""
        help_text = (
            "*Assistant Commands:*\n"
            "• `!forget` - Wipes my current memory of this chat.\n"
            "• `!help` - Shows this menu.\n\n"
            "_You can also upload PDFs, Images, or Word docs for me to analyze!_"
        )
        client.chat_postMessage(
            channel=conv_id,
            text=help_text,
            thread_ts=thread_ts
        )

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
