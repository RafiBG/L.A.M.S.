import os
from dotenv import load_dotenv

class Config:
    def __init__(self) -> None:
        load_dotenv()

        # Use os.getenv with defaults so the app doesn't crash on startup
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "xoxb-placeholder")
        self.APP_TOKEN = os.getenv("APP_TOKEN", "xapp-placeholder")
        self.API_KEY = os.getenv("API_KEY", "")
        self.LOCAL_HOST = os.getenv("LOCAL_HOST", "http://localhost:11434/v1")
        self.MODEL = os.getenv("MODEL", "qwen3-vl:2b-instruct-q4_K_M")
        self.SYSTEM_MESSAGE = os.getenv("SYSTEM_MESSAGE", "You are a helpful assistant.")
        self.SHORT_MEMORY = int(os.getenv("SHORT_MEMORY", "10"))
        
        self.ALLOWED_GROUP_CHANNEL_IDS = self._parse_channel_ids(
            os.getenv("ALLOWED_GROUP_CHANNEL_IDS", "")
        )
        
        self.SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
        self.COMFYUI_API = os.getenv("COMFYUI_API", "http://127.0.0.1:8188")
        self.COMFYUI_IMAGE_PATH = os.getenv("COMFYUI_IMAGE_PATH", "")
        self.COMFYUI_IMAGE_WIDTH = os.getenv("COMFYUI_IMAGE_WIDTH", "512")
        self.COMFYUI_IMAGE_HEIGHT = os.getenv("COMFYUI_IMAGE_HEIGHT", "512")
        self.COMFYUI_STEPS = os.getenv("COMFYUI_STEPS", "20")
        self.VISION_MODEL = os.getenv("VISION_MODEL", "qwen3")
        self.MUSIC_GENERATION_PATH = os.getenv("MUSIC_GENERATION_PATH", "")

    def _get_required(self, name: str) -> str:
        # Changed to return empty string instead of crashing
        value = os.getenv(name)
        return value if value else ""

    def _parse_channel_ids(self, raw_value: str) -> set[str] | None:
        if not raw_value or not raw_value.strip():
            return None
        return {v.strip() for v in raw_value.split(",") if v.strip()}