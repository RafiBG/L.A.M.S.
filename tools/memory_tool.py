from langchain.agents import tool


class MemoryTool:
    def __init__(self, memory_service, conversation_id: str):
        self.memory_service = memory_service
        self.conversation_id = conversation_id
        # State flags
        self.memory_saved = False
        self.memory_saved_failed = False
        self.memory_recalled = False
        self.memory_recalled_failed = False

    def get_tools(self):
        @tool
        def save_to_memory(text: str):
            """Save important information to long-term memory."""
            try:
                self.memory_service.save(self.conversation_id, text)
                self.memory_saved = True
                self.memory_saved_failed = False
                print(f"\n[Tool] Memory saved: {text}\n")
                return "Saved to memory successfully."
            
            except Exception as e:
                self.memory_saved = False
                self.memory_saved_failed = True
                print(f"[Memory Tool Error] Save failed: {e}")
                return f"Error: Could not save to memory. (Technical detail: {str(e)})"

        @tool
        def search_memory(query: str):
            """Search long-term memory for relevant past facts."""
            try:
                results = self.memory_service.search(self.conversation_id, query)
                self.memory_recalled = True
                self.memory_recalled_failed = False
                print(f"\n[Tool] Memory recall: {query}\n")
                return results if results else "No relevant memories found."
            
            except Exception as e:
                self.memory_recalled = False
                self.memory_recalled_failed = True
                print(f"[Memory Tool Error] Search failed: {e}")
                return "Error: Memory database is currently unavailable."

        return [save_to_memory, search_memory]