import os
import random
import requests
import json
from langchain_core.tools import tool

class ComfyUIImageTool:
    def __init__(self, config):
        self.config = config
        # .rstrip("/") prevents double slashes in the URL if the config has one
        self.api_url = getattr(config, "COMFYUI_API", "http://127.0.0.1:8000").rstrip("/")
        
        # Fallback logic: if config value is 0, None, or missing, default to safe values
        self.width = int(getattr(config, "COMFYUI_IMAGE_WIDTH", 1024) or 1024)
        self.height = int(getattr(config, "COMFYUI_IMAGE_HEIGHT", 1024) or 1024)
        self.steps = int(getattr(config, "COMFYUI_STEPS", 20) or 20)
        
        self.is_generating = False
        self.generation_failed = False

        print(f"DEBUG: ComfyUI Tool Loaded -> API: {self.api_url}, Dim: {self.width}x{self.height}, Steps: {self.steps}")

    def get_tool(self):
        @tool
        def generate_image(user_prompt: str):
            """Generate an image using the ComfyUI Lumina 2 workflow from a given text prompt. 
            It may take some time to finish."""
            self.is_generating = True
            self.current_prompt_id = None
            
            try:
                target_url = f"{self.api_url}/prompt"
                print(f"DEBUG: Sending POST to: {target_url}")
                
                random_seed = random.randint(10000, 999999999)
                gen_text = (
                    "You are an assistant designed to generate superior images with a "
                    "superior degree of text-image alignment based on the following prompt: "
                    f"<Prompt Start> {user_prompt}"
                )

                workflow = {
                    "prompt": {
                        "4": {
                            "inputs": {"ckpt_name": "lumina_2.safetensors"},
                            "class_type": "CheckpointLoaderSimple"
                        },
                        "6": {
                            "inputs": {"text": gen_text, "clip": ["4", 1]},
                            "class_type": "CLIPTextEncode"
                        },
                        "7": {
                            "inputs": {
                                "text": "low quality, blurry, distorted, bad hands, bad anatomy", 
                                "clip": ["4", 1]
                            },
                            "class_type": "CLIPTextEncode"
                        },
                        "13": {
                            "inputs": {"width": self.width, "height": self.height, "batch_size": 1},
                            "class_type": "EmptySD3LatentImage"
                        },
                        "11": {
                            "inputs": {"shift": 4, "model": ["4", 0]},
                            "class_type": "ModelSamplingAuraFlow"
                        },
                        "3": {
                            "inputs": {
                                "seed": random_seed,
                                "steps": self.steps,
                                "cfg": 4,
                                "sampler_name": "res_multistep",
                                "scheduler": "simple",
                                "denoise": 1,
                                "model": ["11", 0],
                                "positive": ["6", 0],
                                "negative": ["7", 0],
                                "latent_image": ["13", 0]
                            },
                            "class_type": "KSampler"
                        },
                        "8": {
                            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                            "class_type": "VAEDecode"
                        },
                        "9": {
                            "inputs": {"filename_prefix": "Lumina2_Num_", "images": ["8", 0]},
                            "class_type": "SaveImage"
                        }
                    }
                }

                # Using a session to avoid some local loopback issues on Windows
                with requests.Session() as session:
                    session.trust_env = False # Ignore system proxies that might block 127.0.0.1
                    response = session.post(
                        target_url, 
                        json=workflow,
                        timeout=15
                    )

                if response.status_code != 200:
                    self.is_generating = False
                    print(f"[ComfyUI] Failed: {response.status_code} - {response.text}")
                    return f"ComfyUI error: {response.status_code}"
                
                data = response.json()
                self.latest_prompt_id = data.get("prompt_id")

                print("[ComfyUI] Image generation started successfull.")
                return "Image generation started successfully. I will post it here as soon as it is ready."

            except Exception as e:
                self.generation_failed = True
                self.is_generating = False
                print(f"[ComfyUI] Error: {str(e)}")
                return f"Error connecting to ComfyUI: {str(e)}"

        return generate_image