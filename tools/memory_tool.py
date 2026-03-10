from langchain.agents import tool


class MemoryTool:
    def __init__(self, memory_service, conversation_id: str):
        self.memory_service = memory_service
        self.conversation_id = conversation_id

    def get_tools(self):

        @tool
        def save_to_memory(text: str):
            """Save important information to long-term memory."""
            self.memory_service.save(self.conversation_id, text)
            print(f"\n[Tool] Memory saved: {text}\n")
            return "Saved to memory."

        @tool
        def search_memory(query: str):
            """Search long-term memory for relevant past facts."""
            results = self.memory_service.search(self.conversation_id, query)
            print(f"\n[Tool] Memory recall: {query}\n")
            return results if results else "No relevant memories found."

        return [save_to_memory, search_memory]