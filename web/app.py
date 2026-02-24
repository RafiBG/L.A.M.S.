from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from services.env_service import EnvService

app = FastAPI()
env_service = EnvService()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # We pull the live bot status from app.state
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
            "local_host": env_data.get("LOCAL_HOST", ""),
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
            "music_generation": env_data.get("MUSIC_GENERATION_PATH"),
        },
    )


@app.post("/config")
async def save_config(
    bot_token: str = Form(...),
    app_token: str = Form(...),
    api_key: str = Form(...),
    local_host: str = Form(...),
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
    music_generation: str = Form(...),
    
    
):
    updates = {
        "BOT_TOKEN": bot_token,
        "APP_TOKEN": app_token,
        "API_KEY": api_key,
        "LOCAL_HOST": local_host,
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
        "MUSIC_GENERATION_PATH": music_generation,
    }

    env_service.write_selected(updates)

    return RedirectResponse("/config", status_code=303)
