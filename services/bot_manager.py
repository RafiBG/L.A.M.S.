import threading
from services.slack_bot_service import SlackBotService
from colorama import Fore

class BotManager:
    def __init__(self, config, llm_service) -> None:
        self.config = config
        self.llm_service = llm_service
        self.slack_bot = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if self.is_running:
            return "already_running"

        try:
            # Create the actual Slack service
            self.slack_bot = SlackBotService(
                llm_service=self.llm_service,
                bot_token=self.config.BOT_TOKEN,
                app_token=self.config.APP_TOKEN,
                allowed_channel_ids=self.config.ALLOWED_GROUP_CHANNEL_IDS
            )

            self._thread = threading.Thread(
                target=self.slack_bot.run_sync,
                daemon=True,
            )
            self._thread.start()
            print(f"\n{Fore.GREEN}Bot is online!{Fore.RESET}")
            return "success"

        except Exception as e:
            print(f"{Fore.RED}Failed to start bot: {e}{Fore.RESET}")
            self.slack_bot = None
            return f"Error: {str(e)}"

    def stop(self) -> None:
        if not self.is_running or not self.slack_bot:
            return

        self.slack_bot.stop()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.slack_bot = None # Clear it out
        print(f"\n===============\n{Fore.RED}Bot is offline!{Fore.RESET}\n===============")