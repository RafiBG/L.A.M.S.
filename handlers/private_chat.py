import threading
import os
import time
import requests
import base64
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

class PrivateChatHandler:
    def __init__(self, llm_service):
        self.llm_service = llm_service
        # Track streaming timing to avoid Slack rate limits
        self.last_update_time = 0
        self.update_interval = 1.2 # seconds
        self.user_name_cache = {}

        
    def handle(self, event, say, client):
        
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

        conv_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        user_id = event.get("user")
        user_input = raw_text.strip()

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
        self.llm_service.company_knowledge_tool.is_company_file_read = False
        self.llm_service.company_knowledge_tool.company_file_read_failed = False

        # If text is still empty, check if it's in the first file's title or comment
        if not raw_text and "files" in event:
            # Slack often puts the message in the 'initial_comment' of the first file
            raw_text = event["files"][0].get("initial_comment", "") or event["files"][0].get("title", "")

        user_input = raw_text.strip()
        print(f"[PrivateChat] User: {user_input}")
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
                print("DEBUG: File extraction resulted in no text or there was no text to the image.")

        if user_id in self.user_name_cache:
            real_name = self.user_name_cache[user_id]
            #print(f"DEBUG: Retrieved name from cache for user {user_id}: {real_name}")
        else:
            try:
                #print(f"DEBUG: Cache miss for user {user_id}. Querying Slack API...")
                user_info_resp = client.users_info(user=user_id)
                if user_info_resp.get("ok"):
                    user_profile = user_info_resp.get("user", {})
                    real_name = user_profile.get("real_name") or user_profile.get("name") or "Unknown User"
                    
                    # Save to local RAM map instance
                    self.user_name_cache[user_id] = real_name
                else:
                    real_name = "User"
            except Exception as name_err:
                print(f"Error resolving user real name: {name_err}")
                real_name = "User"

        # Prepend identity formatting to the text context payload
        formatted_prompt = f"[User: {real_name}]: {user_input}"

        # Get LLM Response
        client.chat_update(channel=conv_id, ts=msg_ts, text="_Thinking..._")

        def slack_stream_callback(content, is_final=False):
            now = time.time()
            # Only update Slack every 1.2s to avoid rate limits, or if it's the end
            if is_final or (now - self.last_update_time > self.update_interval):
                
                text_to_display = content
                attachments = []  # Initialize empty attachments list

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
                        status_tags.append("`[Website Read Failed]` _Site blocked me, link was empty, or not enough info found._")
                    
                    # Company Knowledge Base Status
                    if self.llm_service.company_knowledge_tool.is_company_file_read:
                        status_tags.append("`[Company Files Searched]`")

                    if self.llm_service.company_knowledge_tool.company_file_read_failed:
                        status_tags.append("`[Company Files Failed]` _Database collection empty, sync required, or no documents matched context query._")

                    if status_tags:
                        text_to_display += "\n\n" + " ".join(status_tags)

                    # Fetch the links from the LLM service at the very end
                    provider, search_links = self.llm_service.get_latest_search_info()
                    if search_links:
                        attachments.append({
                            "color": "#36a64f",
                            "title": f"🌐 Research Sources (via {provider})",
                            "text": "\n".join([f"• {link}" for link in search_links])
                        })
                else:
                    # Show a typing cursor while it's still working
                    text_to_display += " ▌"

                try:
                    client.chat_update(
                        channel=conv_id,
                        ts=msg_ts,
                        text=text_to_display or "The AI responded with empty content. Check if the AI server is running and properly connected.",
                        attachments=attachments
                    )
                    self.last_update_time = now
                except Exception as e:
                    print(f"Streaming UI Error: {e}")

        def run_streaming_worker():
            try:
                # Call the new streaming method in LLMService
                self.llm_service.generate_reply_stream(
                    conversation_id=conv_id,
                    prompt=formatted_prompt,
                    callback_fn=slack_stream_callback,
                    images=file_images
                )
                
                # After the AI finishes typing, check if we need to start image/music watchers
                if self.llm_service.comfy_image_tool.is_generating:
                    threading.Thread(target=self._image_watcher_thread, args=(conv_id, client, thread_ts), daemon=True).start()
                if self.llm_service.music_generation_tool.is_generating:
                    threading.Thread(target=self._music_watcher_thread, args=(conv_id, client, thread_ts), daemon=True).start()
            
            except Exception as e:
                print(f"Generation Error: {e}")
                client.chat_update(channel=conv_id, ts=msg_ts, text="Sorry, I hit an error.")

        threading.Thread(target=run_streaming_worker, daemon=True).start()
    
    def _image_watcher_thread(self, channel, client, thread_ts):
        path = self.llm_service.config.COMFYUI_IMAGE_PATH
        api_url = self.llm_service.comfy_image_tool.api_url
        prompt_id = getattr(self.llm_service.comfy_image_tool, "latest_prompt_id", None)
        initial_files = set(os.listdir(path))
        total_nodes = 11 

        progress_msg = client.chat_postMessage(
            channel = channel, thread_ts = thread_ts, text="⏳ *ComfyUI:* Initializing..."
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

            # Calculate simulated/real percentage
            display_pct = percent_complete if percent_complete > 0 else min(i * 3, 95)
    
            # Build the visual bar
            bar_length = 10
            filled = int((display_pct / 100) * bar_length)
            bar = "■" * filled + "□" * (bar_length - filled)
    
            try:
                client.chat_update(
                    channel = channel,
                    ts = progress_ts,
                    text=f"🎨 *ComfyUI Progress:* `[{bar}]` *{display_pct}%*)"
                )
            except Exception:
                pass

            # --- FILE CHECKING ---
            current_files = set(os.listdir(path))
            new_files = current_files - initial_files
            if new_files:
                png_files = [os.path.join(path, f) for f in new_files if f.endswith('.png')]
                if png_files:
                    time.sleep(1) 
                    latest_image = max(png_files, key=os.path.getctime)
                    try:
                        # Final 100% update
                        client.chat_update(
                            channel = channel, ts = progress_ts, 
                            text = f"🎨 *ComfyUI Progress:* `[■■■■■■■■■■]` *100%* (Done!)"
                        )
                        time.sleep(0.5)
                        client.chat_delete(channel = channel, ts = progress_ts)
                
                        client.files_upload_v2(
                            channel = channel, thread_ts=thread_ts,
                            file = latest_image, title="AI Generated Image",
                            initial_comment = "🎨 *Image ready:*"
                        )
                    except Exception as e:
                        print(f"Upload failed: {e}")
                    return # Exit successfully

        # If the loop finishes without finding a file
        client.chat_update(channel = channel, ts = progress_ts, text = "*ComfyUI:* Timed out. Didn't find the generated image.")

    def _process_files(self, files, client):
        extracted_text = []
        extracted_images = []
        token = client.token

        for file_info in files:
            file_url = file_info.get("url_private_download")
            file_name = file_info.get("name", "unknown_file")
            
            if not file_url:
                continue

            # Create a unique temp path
            temp_path = f"temp_{int(time.time())}_{file_name}"
            extension = os.path.splitext(file_name)[1].lower()

            try:
                resp = requests.get(
                    file_url,
                    headers={"Authorization": f"Bearer {token}"},
                    stream=True
                )

                if resp.status_code != 200:
                    print(f"DEBUG: Failed to download {file_name}. Status: {resp.status_code}")
                    continue

                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Ensure OS has released the file handle
                time.sleep(0.5) 

                content = ""
                # TEXT EXTRACTION
                if extension == ".pdf":
                    loader = PyPDFLoader(temp_path)
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                elif extension in [".docx", ".doc"]:
                    loader = Docx2txtLoader(temp_path)
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                elif extension in [".txt", ".md", ".py", ".json", ".csv"]:
                    loader = TextLoader(temp_path, encoding="utf-8")
                    docs = loader.load()
                    content = "\n".join([d.page_content for d in docs])
                
                # If text was found, add it
                if content.strip():
                    extracted_text.append(f"--- FILE: {file_name} ---\n{content}")

                # IMAGE HANDLING
                if extension in [".png", ".jpg", ".jpeg"]:
                    with open(temp_path, "rb") as img_file:
                        encoded = base64.b64encode(img_file.read()).decode("utf-8")
                        extracted_images.append({
                            "filename": file_name,
                            "base64": encoded
                        })

            except Exception as e:
                print(f"Error processing {file_name}: {e}")

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        # Join all text blocks into one string for the prompt
        final_text_context = "\n\n".join(extracted_text)
        return final_text_context, extracted_images
    
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
        "🚀 *Welcome to your Local AI Assistant!* 🚀\n"
        "I am a multi-functional bot running locally to ensure your data stays private.\n\n"
        "✨ *Repo:* <https://github.com/RafiBG/L.A.M.S.|View Source Code>\n\n"
        
        "*🛠️ CORE COMMANDS IN PRIVATE CHAT*\n"
        "• `!forget` - Wipes my current memory of this thread.\n"
        "• `!help`  - Shows this menu.\n\n"

        "*🛠️ CORE COMMANDS IN GROUP CHATS*\n"
        "• `/clear_memory` - Wipes my current memory in group chat thread (This command must be set and can be used in group chats only).\n\n"
        "• `/help` - Shows this menu.\n\n"
        
        "*🌐 SMART TOOLS*\n"
        "• *Web Search:* I can browse the internet (via SearXNG/Serper) for real-time info.\n"
        "  _Example: \"What is the current stock price of NVIDIA?\"_\n"
        "• *RAG Memory:* I can save specific facts to a private database for this channel.\n"
        "  _Example: \"Remember for long time that our server password is 'Admin123'\"_\n"
        "  _Example: \"Do you remmeber our server password?\"_\n"
        "• *Python Runner:* I can execute Python code snippets for math solving.\n"
        "  _Example: \"12345 * 67890 = ?\"_\n\n"
        
        "*📂 FILE & VISION ANALYSIS*\n"
        "• *Documents:* Upload *PDF, DOCX, TXT, MD, PY, JSON, or CSV* for analysis, summaries or Q&A.\n"
        "• *Vision:* Upload **IMAGES** (*.PNG, .JPG, .JPEG*) to describe or analyze content.\n\n"
        
        "*🎨 CREATIVE GENERATION*\n"
        "• *Images:* I can generate art locally via *ComfyUI*.\n"
        "  _Example: \"Generate an image of a cybernetic owl in a library.\"_\n"
        "• *Music:* I can create original audio tracks.\n"
        "  _Example: \"Create a 30-second futuristic synth-wave melody.\"_\n\n"
        
        "*🕒 UTILITY*\n"
        "• Ask me for my current local time or date anytime.\n\n"
        
        "💡 *Tip:* You don't need special commands for most tasks. Just talk to me naturally!"
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
