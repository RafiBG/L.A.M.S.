from slack_bolt import App

class SlashClearMemoryHandler:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    def register_commands(self, app: App):
        # Clear user memory (works in private and group chats)
        @app.command("/clear_memory")
        def clear_user_memory_command(ack, body, client):
            ack()
            self._clear_user_memory(body, client)

    # Internal Methods
    def _clear_user_memory(self, body, client):
        channel_id = body["channel_id"]

        if channel_id in self.llm_service.history_db:
            del self.llm_service.history_db[channel_id]

        client.chat_postMessage(
            channel=channel_id,
            text="AI memory for this conversation has been cleared."
    )