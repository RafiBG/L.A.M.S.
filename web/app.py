import os
import urllib.parse
import shutil
from services.memory_service import MemoryService
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from services.env_service import EnvService
from typing import List

app = FastAPI()
env_service = EnvService()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")
# Configuration for your local drag & drop directory for company files.
UPLOAD_FOLDER = "./company_files"
MEMORY_STORAGE_DIR = "./memory_storage"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Pull the live bot status from app.state
    manager = request.app.state.bot_manager
    is_running = manager.is_running
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status_text": "online" if is_running else "offline",
            "status_class": "online" if is_running else "offline",
            "button_text": "Stop bot" if is_running else "Start bot",
        },
    )

@app.post("/toggle_ajax")
def toggle_ajax(request: Request):
    manager = request.app.state.bot_manager
    
    if manager.is_running:
        manager.stop()
    else:
        manager.start()

    return JSONResponse(
        content={
            "status_text": "online" if manager.is_running else "offline",
            "status_class": "online" if manager.is_running else "offline",
            "button_text": "Stop bot" if manager.is_running else "Start bot"
        }
    )

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    env_data = env_service.read()

    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "bot_token": env_data.get("BOT_TOKEN", ""),
            "app_token": env_data.get("APP_TOKEN", ""),
            "api_key": env_data.get("API_KEY", ""),
            "ollama_host": env_data.get("OLLAMA_HOST", ""),
            "lm_studio_host": env_data.get("LM_STUDIO_HOST",""),
            "open_ai_host": env_data.get("OPEN_AI_HOST",""),
            "allowed_channels": env_data.get("ALLOWED_GROUP_CHANNEL_IDS", ""),
            "model": env_data.get("MODEL", ""),
            "system_message": env_data.get("SYSTEM_MESSAGE", "").replace("\\n", "\n"),
            "max_tokens": env_data.get("MAX_TOKENS", "4096"),
            "web_key": env_data.get("SERPER_API_KEY"),
            "comfy_api": env_data.get("COMFYUI_API"),
            "comfy_image_path": env_data.get("COMFYUI_IMAGE_PATH"),
            "comfy_image_width": env_data.get("COMFYUI_IMAGE_WIDTH"),
            "comfy_image_height": env_data.get("COMFYUI_IMAGE_HEIGHT"),
            "comfy_steps": env_data.get("COMFYUI_STEPS"),
            "vision_model": env_data.get("VISION_MODEL"),
            "vision_mode": env_data.get("VISION_MODE"),
            "music_generation": env_data.get("MUSIC_GENERATION_PATH"),
            "embedding_model": env_data.get("EMBEDDING_MODEL"),
            "provider": env_data.get("PROVIDER"),
            "show_thinking": env_data.get("SHOW_THINKING"),
            "search_provider": env_data.get("SEARCH_PROVIDER"),
            "searxng_host": env_data.get("SEARXNG_HOST", "http://localhost:8080"),
            "search_limit": env_data.get("SEARCH_LIMIT"),
            "searxng_engines": env_data.get("SEARXNG_ENGINES"),
            "company_rag_k": env_data.get("COMPANY_RAG_K", "4"),
            "agent_max_iterations": env_data.get("AGENT_MAX_ITERATIONS", "4"),
            "temperature": env_data.get("TEMPERATURE", "0.7")
        },
    )

@app.post("/config")
async def save_config(
    bot_token: str = Form(...),
    app_token: str = Form(...),
    api_key: str = Form(...),
    ollama_host: str = Form(...),
    lm_studio_host: str = Form(...),
    open_ai_host: str = Form(...),
    allowed_channels: str = Form(""),
    model: str = Form(...),
    system_message: str = Form(...),
    max_tokens: str = Form(...),
    web_key: str = Form(...),  # In html name = web_key
    comfy_api: str = Form(...),
    comfy_image_path: str = Form(...),
    comfy_image_width: str = Form(...),
    comfy_image_height: str = Form(...),
    comfy_steps: str = Form(...),
    vision_model: str = Form(...),
    vision_mode: str = Form(...),
    music_generation: str = Form(...),
    embedding_model: str = Form(...),
    provider: str = Form(...),
    show_thinking: str = Form(...),
    search_provider: str = Form(...),
    searxng_host: str = Form(...),
    search_limit: str = Form(...),
    searxng_engines: List[str] = Form([]),
    company_rag_k: str = Form("4"),
    agent_max_iterations: str = Form(...),
    temperature: str = Form(...)
    
    
):
    engines_str = ",".join(searxng_engines) if searxng_engines else "google"
    
    updates = {
        "BOT_TOKEN": bot_token,
        "APP_TOKEN": app_token,
        "API_KEY": api_key,
        "OLLAMA_HOST": ollama_host,
        "LM_STUDIO_HOST": lm_studio_host,
        "OPEN_AI_HOST": open_ai_host,
        "ALLOWED_GROUP_CHANNEL_IDS": allowed_channels,
        "MODEL": model,
        "SYSTEM_MESSAGE": system_message.replace("\n", "\\n"),
        "MAX_TOKENS": max_tokens,
        "SERPER_API_KEY": web_key,
        "COMFYUI_API": comfy_api,
        "COMFYUI_IMAGE_PATH": comfy_image_path,
        "COMFYUI_IMAGE_WIDTH": comfy_image_width,
        "COMFYUI_IMAGE_HEIGHT": comfy_image_height,
        "COMFYUI_STEPS": comfy_steps,
        "VISION_MODEL": vision_model,
        "VISION_MODE": vision_mode,
        "MUSIC_GENERATION_PATH": music_generation,
        "EMBEDDING_MODEL" : embedding_model,
        "PROVIDER": provider,
        "SHOW_THINKING": show_thinking,
        "SEARCH_PROVIDER": search_provider,
        "SEARXNG_HOST": searxng_host,
        "SEARCH_LIMIT": search_limit,
        "SEARXNG_ENGINES": engines_str,
        "COMPANY_RAG_K": company_rag_k,
        "AGENT_MAX_ITERATIONS": agent_max_iterations,
        "TEMPERATURE": temperature
    }

    env_service.write_selected(updates)

    return RedirectResponse("/config", status_code=303)

# Ensure these point to your correct system folder configurations
UPLOAD_FOLDER = "./company_files"
MEMORY_STORAGE_DIR = "./memory_storage"

@app.post("/api/upload-company-files")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Handles incoming file uploads from the Drag & Drop frontend zone.
    1. Checks if the raw files folder exists (creates it if missing).
    2. Iterates through dropped files, scrubbing out malicious path sequences.
    3. Streams the binary payload down to the local file system storage.
    """
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        for file in files:
            if file.filename:
                # Basic validation to strip path traversals safely
                safe_name = os.path.basename(file.filename)
                target_path = os.path.join(UPLOAD_FOLDER, safe_name)
                
                # Stream file buffer from memory directly to your storage disk
                with open(target_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                    
        return JSONResponse(content={"status": "success", "message": "Files saved successfully."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/list-company-files")
def list_files():
    """
    Supplies data for the 'Currently Uploaded Files' dashboard UI list.
    1. Looks at the upload folder directory.
    2. Loops through files while filtering out hidden system metadata objects (like .DS_Store).
    3. Sends a clean array of strings (filenames) back to the client interface.
    """

    if not os.path.exists(UPLOAD_FOLDER):
        return JSONResponse(content=[])
        
    # Read files, filtering out dynamic system components (e.g. .DS_Store, .gitignore)
    files = [
        f for f in os.listdir(UPLOAD_FOLDER) 
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and not f.startswith('.')
    ]
    return JSONResponse(content=files)


@app.delete("/api/delete-company-file/{filename}")
def delete_file(filename: str):
    """
    Deletes an uploaded raw file when a user clicks the '✕' button.
    1. Decodes web URL formatting characters (like converting %20 back to spaces).
    2. Strips directory paths for safety.
    3. Deletes the physical file off the system drive so it won't be picked up during the next sync.
    """
    # Unquote URL text string conversion if spaces are evaluated as '%20'
    decoded_name = urllib.parse.unquote(filename)
    safe_name = os.path.basename(decoded_name)
    target_path = os.path.join(UPLOAD_FOLDER, safe_name)
    
    if os.path.exists(target_path):
        os.remove(target_path)
        return JSONResponse(content={"status": "success"})
        
    return JSONResponse(status_code=404, content={"status": "error", "message": "File context target not found."})


@app.post("/api/reindex-company-files")
def reindex_files(request: Request):
    """
    Re-chunks and embeds uploaded documents into the vector database (Chroma).
    1. Triggers when the user hits the 'Sync & Reindex Files' dashboard button.
    2. Dynamically finds your memory system helper inside your global application state.
    3. Calls your text chunking processor to split text and build vector memory spaces.
    """
    try:
        manager = request.app.state.bot_manager
        
        # Smart detection loop to find where the memory service is hiding inside BotManager
        memory_worker = None
        for attr in ['memory_service', 'memory', 'memory_manager', 'storage']:
            if hasattr(manager, attr):
                memory_worker = getattr(manager, attr)
                break
                
        # If the manager doesn't have it attached, initialize a clean instance directly
        if not memory_worker:
            from services.memory_service import MemoryService
            memory_worker = MemoryService(manager.config)
            
        status_msg = memory_worker.index_company_directory() 
        
        return JSONResponse(content={"status": "success", "message": status_msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Sync failed: {str(e)}"})


@app.get("/api/list-memory-folders")
def list_memory_folders():
    """
    Supplies data for the 'Active Memory Storage Folders' UI list.
    """
    try:
        if not os.path.exists(MEMORY_STORAGE_DIR):
            os.makedirs(MEMORY_STORAGE_DIR, exist_ok=True)
            
        subdirectories = [
            d for d in os.listdir(MEMORY_STORAGE_DIR) 
            if os.path.isdir(os.path.join(MEMORY_STORAGE_DIR, d)) and not d.startswith('.')
        ]
        return JSONResponse(content={"status": "success", "folders": sorted(subdirectories)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.delete("/api/delete-memory-folder/{folder_name}")
def delete_memory_folder(request: Request, folder_name: str):
    """
    Validates user path input parameters, strips active memory hooks,
    and drops only the selected subdirectory completely from disk storage.
    """
    try:
        # Secure the path context input parameter to stop directory traversal tricks
        safe_folder_name = os.path.basename(folder_name)
        target_path = os.path.join(MEMORY_STORAGE_DIR, safe_folder_name)
        
        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            raise HTTPException(status_code=404, detail="Target storage subdirectory not found.")

        # Wipe active cache structures inside memory service if running live
        manager = request.app.state.bot_manager
        if hasattr(manager, 'memory_service'):
            manager.memory_service.collections = {}

        # Delete the target folder from disk
        shutil.rmtree(target_path)
        
        return JSONResponse(content={
            "status": "success", 
            "message": f"Storage directory [{safe_folder_name}] completely erased."
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Failed to securely erase directory: {str(e)}"})