import time
import ssl
from slack_bolt import App
from slack_sdk import WebClient
from slack_bolt.adapter.socket_mode import SocketModeHandler
from services.llm_service import LLMService
from handlers.group_chat import GroupChatHandler
from handlers.private_chat import PrivateChatHandler
from handlers.slash_clear_memory import SlashClearMemoryHandler

class SlackBotService:
    def __init__(
        self,
        llm_service: LLMService,
        bot_token: str,
        app_token: str,
        allowed_channel_ids: set[str] | None,
        max_memory: int = 10
    ) -> None:
        self.llm_service = llm_service
        self.app = App(token=bot_token)
        self.app_token = app_token
        
        # Handlers
        self.group_handler = GroupChatHandler(llm_service)
        self.private_handler = PrivateChatHandler(llm_service)

        # Slash Handlers
        self.slash_clear_handler = SlashClearMemoryHandler(llm_service)
        
        self.handler: SocketModeHandler | None = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.app.event("app_mention")
        def handle_mention(event, say, client):
            # This only fires in channels/groups when @bot is tagged
            thread_ts = event.get("thread_ts") or event.get("ts")
            self.group_handler.handle(event, say, client, thread_ts)

        @self.app.event("message")
        def handle_message(event, say, client):
            # Check if this is a Direct Message (IM)
            # This prevents the bot from replying twice in groups
            if event.get("channel_type") == "im":
                self.private_handler.handle(event, say, client)

        # Register slash commands
        self.slash_clear_handler.register_commands(self.app)

    def run_sync(self) -> None:
        """Starts the bot synchronously. This blocks the thread it is called in."""
        # SocketModeHandler also needs to be told not to hang on SSL
        self.handler = SocketModeHandler(self.app, self.app_token)
        
        # .connect() starts the websocket
        self.handler.connect()
        
        while self.handler is not None:
            time.sleep(1)

    def stop(self) -> None:
        """Gracefully shuts down the connection."""
        if self.handler:
            try:
                self.handler.close()
            except Exception:
                pass
            self.handler = None