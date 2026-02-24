import requests
from langchain_core.tools import tool

class MusicGenerationTool:
    def __init__(self, config):
        self.config = config
        # Target the Flask server we built earlier
        self.api_url = getattr(config, "MUSIC_API_URL", "http://127.0.0.1:5001").rstrip("/")
        self.is_generating = False 

        print(f"DEBUG: MusicGen Tool Loaded -> API: {self.api_url}")

    def get_tool(self):
        @tool
        def generate_music(prompt: str, duration: int = 10):
            """
            Triggers the music engine to create an audio file (.wav). 
            Use this if the user wants a song, a beat, or any musical melody.
            'prompt' should be a description of the music style.
            'duration' is in seconds (max 20).
            """
            self.is_generating = True
            
            # Safety check on duration
            if duration > 20:
                duration = 20
            
            try:
                target_url = f"{self.api_url}/generate"
                payload = {
                    "prompt": prompt,
                    "duration": duration
                }
                
                print(f"DEBUG: Sending Music Request to: {target_url} with prompt: {prompt}")
                
                # We use a short timeout because the Flask server 
                # returns immediately after starting the thread
                response = requests.post(
                    target_url, 
                    json=payload,
                    timeout=10
                )

                if response.status_code != 200:
                    self.is_generating = False
                    return f"Music Engine error: {response.status_code}"

                return (
                    f"Music generation for '{prompt}' has started ({duration} seconds). "
                    "I will upload the .wav file here as soon as it's ready!"
                )

            except Exception as e:
                self.is_generating = False
                print(f"[MusicTool] Error: {str(e)}")
                return f"Error connecting to Music Engine: {str(e)}"

        return generate_music