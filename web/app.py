from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from services.env_service import EnvService
from typing import List

app = FastAPI()
env_service = EnvService()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

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
            "short_memory": env_data.get("SHORT_MEMORY", "10"),
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
    short_memory: str = Form(...),
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
        "SHORT_MEMORY": short_memory,
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
    }

    env_service.write_selected(updates)

    return RedirectResponse("/config", status_code=303)
