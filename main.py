import uvicorn
import webbrowser
import time
import sys
from threading import Timer
from web.app import app  
from config import Config
from services.llm_service import LLMService
from services.bot_manager import BotManager

def open_browser():
    try:
        print("Opening dashboard...")
        webbrowser.open("http://127.0.0.1:5000")
    except Exception as e:
        print(f"Browser error: {e}")

def main():
    try:
        config = Config()
        llm_service = LLMService(config)
        
        # Initialize the manager
        bot_manager = BotManager(config, llm_service)

        # Attach to app state so the web routes can see it
        app.state.bot_manager = bot_manager
        app.state.llm_service = llm_service

        browser_timer = Timer(1.5, open_browser)
        browser_timer.daemon = True
        browser_timer.start()

        print("--- Starting Server ---")
        
        server_config = uvicorn.Config(
            app, 
            host="127.0.0.1", 
            port=5000, 
            log_level="info",
        )
        server = uvicorn.Server(server_config)
        
        server.run()

    except KeyboardInterrupt:
        print("\nStopping server...")
    except Exception as e:
        print(f"Critical Startup Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()