from slack_bolt import App

class SlashHelpHandler:
    def __init__(self):
        pass

    def register_commands(self, app: App):
        @app.command("/help")
        def help_command(ack, body, client):
            # Acknowledge the command request immediately
            ack()
            self._send_help_menu(body, client)

    def _send_help_menu(self, body, client):
        user_id = body["user_id"]
        channel_id = body["channel_id"]

        help_text = (
            "🚀 *Welcome to your Local AI Assistant!* 🚀\n"
            "I am a multi-functional bot running locally to ensure your data stays private.\n\n"
            "✨ *Repo:* <https://github.com/RafiBG/L.A.M.S.|View Source Code>\n\n"
            
            "*🛠️ CORE COMMANDS IN GROUP CHAT*\n"
            "• `/clear_memory` - Wipes my current memory in this channel.\n"
            "• `/help` - Shows this menu.\n\n"
            
            "*🛠️ CORE COMMANDS IN PRIVATE CHAT*\n"
            "• `!forget` - Wipes my current memory of this thread.\n"
            "• `!help`  - Shows this menu.\n\n"

            "*🌐 SMART TOOLS*\n"
            "• *Web Search:* I can browse the internet (via SearXNG/Serper) for real-time info.\n"
            "  _Example: \"What is the current stock price of NVIDIA?\"_\n"
            "• *Read URL:* Provide a link, and I will extract and analyze its raw web text content. *Tip:* Can be combined with Web Search to deeply analyze discovered links.\n"
            "  _Example: \"Can you read this website and tell me what it is about: https://example.com\"_\n"
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
            
            "💡 *Tip 1:* Mention me (@MyBotName) in group chats to get started!\n"
            "💡 *Tip 2:* You don't need special commands for most tasks. Just talk to me naturally!"
        )

        # postEphemeral so only the user who asked sees the help text
        client.chat_postEphemeral(
            channel = channel_id,
            user = user_id,
            text = help_text
        )