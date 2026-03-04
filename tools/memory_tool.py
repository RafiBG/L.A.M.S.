from langchain.tools import tool


class MemoryTool:
    def __init__(self, memory_service):
        self.memory_service = memory_service

    def get_tools(self, conversation_id: str):

        @tool
        def remember_information(info: str) -> str:
            """
            Save important information for this conversation.
            Use when user says to remember something.
            """
            self.memory_service.save(conversation_id, info)
            return "Saved to long term memory."

        @tool
        def recall_information(query: str) -> str:
            """
            Search long term memory for relevant information.
            Use when user asks about something from the past.
            """
            results = self.memory_service.search(conversation_id, query)

            if not results:
                return "No relevant long term memory found."

            formatted = "\n".join(f"- {r}" for r in results)
            return f"Found in memory:\n{formatted}"

        return [remember_information, recall_information]