# LocalAISlackBot

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-4A154B?style=flat&logo=slack&logoColor=white)

LocalAISlackBot is a local AI powered Slack bot built with Python.
It integrates local LLMs via Ollama/LM Studio/Cloud, web search, vision, file analysis,
image generation, music generation, and Python execution directly
inside your Slack workspace.

## ✨ Features
**What can this local AI do in Slack?**

* 💬 **Chat:** Natural conversation with context awareness.
* 🧠 **On-Demand RAG Memory:** A specialized tool that allows users to explicitly save information to a channel-specific vector database. The bot only accesses this memory for the specific channel where it was saved, ensuring privacy and context relevance.
* 📄 **File Analysis:** Upload **PDF, TXT, or DOCX** files, and the bot will read and answer questions based on them.
* 👁️ **Vision:** Upload images and ask the bot to describe or analyze them (requires a Vision model).
* 🕒 **Local Time and Date** Retrieve current system time and date.
* 🌐 **Web Search:** The bot can search the internet for the latest news and real-time information (requires Serper web api key).
* 🎨 **Image Generation:** The bot can generate images locally using **ComfyUI** (requires installed ComfyUI).
* 🎵 **Music Generation:** Create original audio and music (requires separate Music Gen Python program running).
* 🐍 **Python Execution:** Write and execute Python code snippets (requires separate Python Execution environment/program running).

  
## 🛠️ Tech Stack & Libraries

* Python 3.11.9
* Slack Bolt
* Ollama
* LangChain
* FastAPI for optional services
* ComfyUI for image generation


## ⚙️ Installation & Setup

1 Create the Slack App

1. Go to the Slack API Dashboard
https://api.slack.com/apps
2. Click Create New App
3. Choose From Scratch
4. Enter your app name (example: AI-Bot)
5. Select your workspace

Configure Bot Token Scopes

Go to
OAuth & Permissions → Bot Token Scopes

Add the following scopes:
Scope	Description
app_mentions:read	View messages that mention @AI-Bot
assistant:write	Allow AI-Bot to act as an App Agent
channels:history	View messages in public channels
chat:write	Send messages as AI-Bot
commands	Enable slash commands
files:read	View files shared in conversations
files:write	Upload and manage files
groups:history	View messages in private channels
im:history	View direct messages
users:read	View users in workspace

2 Configure Bot Token Scopes

Go to:

OAuth & Permissions → Bot Token Scopes

Add the following scopes:
| Scope | Description |
| :--- | :--- |
| `app_mentions:read` |  View messages that mention @AI-Bot |
| `assistant:write` |	   Allow AI-Bot to act as an App Agent |
| `channels:history` |	 View messages in public channels |
| `chat:write` |	       Send messages as AI-Bot |
| `commands` |	         Enable slash commands |
| `files:read` |         View files shared in conversations |
| `files:write`	|        Upload and manage files |
| `groups:history` |     View messages in private channels |
| `im:history` |         View direct messages |
| `users:read` |         View users in workspace |

After adding scopes:
* Click Install to Workspace
* Authorize the app

Copy your:
* Bot User OAuth Token (xoxb-...)

You will need this in your configuration panel.

3 Enable Slash Command
Go to:
Slash Commands → Create New Command

Configure:
Name:
```
/clear_memory
```

Description:
```
Clears the conversation with the user that uses this command.
```
Save the command.

4 Enable Socket Mode
Go to:
Settings → Socket Mode
Turn ON:
```
Enable Socket Mode
```
Then:
Click Generate App-Level Token
Add scope:
```
connections:write
```
Copy your:
* App Level Token (xapp-...)
This token is required for WebSocket connection.

5️ Event Subscriptions

Go to:
Event Subscriptions
Enable Events.
Subscribe to the following bot events:
```
app_mention
message.channels
message.groups
message.im
```
Save changes.

6️ Configure Tokens in Web Interface
After generating both tokens:
You must enter them inside the bot’s web configuration interface:
* Bot Token → xoxb-...
* App Token → xapp-...
Without both tokens, the bot cannot connect.

7️ Install Dependencies
Inside your project directory:
```
pip install -r requirements.txt
```
8️ Run the Bot
```
python main.py
```

## 2. Local Model Setup - Ollama / LM Studio (The Brain)
Your bot can connect to:
* Ollama
* LM Studio
* Any OpenAI compatible local server running on your network
You can even run the model on another PC inside the same router network.


### Option A - Ollama Setup
1. Download and install Ollama
  https://ollama.com/

2. Start the server:
```
ollama serve
```
3. Default API endpoint:
```
http://localhost:11434
```
If running on another machine in your local network:
```
http://192.168.X.X:11434
```
Replace 192.168.X.X with the IP of the PC running Ollama.

Download a Model

Example recommended lightweight model:
```
ollama pull qwen3:4b
```
You can also use any other supported model.
List installed models:
```
ollama list
```
Copy the exact model name into your bot configuration.


### Option B - LM Studio Setup

1. Download LM Studio
 https://lmstudio.ai/

2. Download a model inside LM Studio
Example:
* Qwen 3 4B Instruct

3. Start the Local Server inside LM Studio:
* Go to Developer tab
* Enable OpenAI Compatible API
* Note the port (usually 1234)

Default endpoint:
```
http://localhost:1234/v1
```
Place this endpoint and model name inside your configuration.


## 🌐 3. Web Search - Optional

To enable internet search capability:

1. Get API key from:
 https://serper.dev

2. Add the API key to your configuration.
This enables:
* Live web results
* News lookup
* Research assistance


## 🎨 4. ComfyUI - Image Generation (Optional)

The bot supports local image generation through ComfyUI.
You can download and use any template inside ComfyUI, but it is strongly recommended to use the tested workflow included with this project.
Recommended Setup (Tested and Working)
Inside the project folder:
```
LocalAISlackBot/comfy resources/lumina-2-text2img-comfyui-wiki.com.json
```
You will find a .json workflow file.
Setup Steps

1. Install ComfyUI
https://www.comfy.org/download
2. Start ComfyUI.
3. Drag and drop the provided .json workflow file into the ComfyUI interface.
4. ComfyUI will automatically show which models are missing.
5. Download the required models directly inside ComfyUI.

⚙ Important Settings in ComfyUI
Inside ComfyUI:

1. Open Settings
2. Enable Dev Mode
3. Check:
* Host
* Port

Default example:
```
http://localhost:8188
```
If running on another PC in your local network:
```
http://192.168.X.X:8188
```
You must place the exact host and port in the bot configuration page.
Without Dev Mode enabled, API access will not work.


## 🎵 5. Music Generation - Optional

Repository:
https://github.com/RafiBG/AIMusicGenerator

Role:
* Separate Python API
* Receives prompt
* Generates audio file
* Returns .wav to Slack

Runs independently from the main bot.

## 🐍 6. Python Execution - Optional

Repository:
https://github.com/RafiBG/AIPythonRun

Role:
Sandboxed Python execution API
* AI writes code
* Code is executed safely
* Returns:
** stdout
** stderr
** execution result

This keeps the main Slack bot secure and isolated.
---
Architecture Overview 
```
                     ┌────────────────────┐
                     │       Slack        │
                     └─────────┬──────────┘
                               │
                       Socket Mode (WS)
                               │
                     ┌─────────▼──────────┐
                     │  Slack Bolt App    │
                     │     Python Core    │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │    Agent Layer     │
                     │ Tool Orchestrator  │
                     └─────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌────────▼────────┐   ┌─────────▼────────┐
│ Ollama /       │   │   ComfyUI       │   │ Music Generator  │
│ LM Studio      │   │ Image Server    │   │ Python API       │
│ Local LLM      │   │ Dev Mode On     │   │ Returns .wav     │
└────────────────┘   └─────────────────┘   └──────────────────┘
                               │
                     ┌─────────▼──────────┐
                     │ Python Exec Server │
                     │ Sandboxed API      │
                     │ Returns stdout     │
                     └────────────────────┘

                     + Local Time / Date Tool
```
---
🎮 Slash Commands
In Slack Channels (Group Chat)
| Commands | Description |
| :--- | :--- |
| `/clear_memory` |  Clears conversation memory for the entire channel |

🎮 Commands
In Direct Messages (Private Chat)
| Commands | Description |
| :--- | :--- |
| `!forget` |  Clears AI memory for your private conversation |
| `!help` | Shows usage instructions |

## 📸 Gallery & Examples

**Web Interface (Adaptive OS Light/Dark Mode)**
<p float="left">
 <img src="https://github.com/user-attachments/assets/38a539fe-c788-4968-91a8-ce5e9a2c987a" width="30%" />
 <img src="https://github.com/user-attachments/assets/4fa8cb34-0e2a-4282-acf7-78d589bb0a3a" width="30%" />
</p>

<p float="left">
  <img src="https://github.com/user-attachments/assets/d7b99887-6f05-45ef-8ea2-8e66d49b570c" width="30%" />
  <img src="https://github.com/user-attachments/assets/51e89cd7-b7c0-4b11-933c-380f53111987" width="30%" />
</p>

**Chat & Vision Capabilities**
<p float="left">
 <img src="https://github.com/user-attachments/assets/ab45716e-6e53-47ec-9a7c-5656de4d02ef" width="30%" />
 <img src="https://github.com/user-attachments/assets/c1d07285-868e-4345-bfed-c91caa24373b" width="30%" />
</p>

**File Analysis & Web Search**
<p float="left">
   <img src="https://github.com/user-attachments/assets/f1ce5096-2ded-4085-b62c-e10f0d7fe493" width="30%" />
   <img src="https://github.com/user-attachments/assets/b3c2aec3-7b6a-4595-952d-ec0198f5a05d" width="30%" />
</p>

**Image Generation & Music Generation**
<p float="left">
  <img src="https://github.com/user-attachments/assets/7be243d6-9bf1-45ad-ba78-9d776555863e" width="30%" />
  <img src="https://github.com/user-attachments/assets/ff7280f4-9204-4798-a9c8-77b4744122bd" width="30%" />
</p>

**Python Code Execution**
<p float="left">
  <img src="https://github.com/user-attachments/assets/4564afd3-52c8-42e3-8d83-7425e4069aa3" width="30%" />
</p>

**RAG/Vector Memory**
<p float="left">
  <img src="https://github.com/user-attachments/assets/6e994d4a-8513-4eb3-a8a7-359bbc087745" width="30%" />
</p>
