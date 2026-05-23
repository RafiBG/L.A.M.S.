import logging
from langchain_core.tools import tool
from services.memory_service import MemoryService

logger = logging.getLogger("CompanyKnowledgeTool")

class CompanyKnowledgeTool:
    def __init__(self, config):
        self.config = config
        self.company_collection_id = "global_company_rag"
        self.is_company_file_read = False 
        self.company_file_read_failed = False

    def get_tool(self):
        """
        Dynamically builds a LangChain-compatible functional tool object.
        """
        #Fetch the configuration attributes outside the wrapped block
        config_reference = self.config
        collection_id = self.company_collection_id
        k_val = int(getattr(self.config, "COMPANY_RAG_K", 4))

        @tool("query_company_knowledge_base")
        def query_company_knowledge_base(query: str) -> str:
            """Use this tool to search internal company documents, rules, guidelines, 
            corporate policies, workspace regulations, and HR information. 
            Input should be a specific search query string."""
            try:
                logger.info(f"AI invoked Company Knowledge Tool with query: '{query}'")
                self.is_company_file_read = True
                # Initialize memory service wrapper
                memory_service = MemoryService(config_reference)
                
                # Query the Chroma vector space database
                results = memory_service.search(
                    conversation_id=collection_id, 
                    query=query, 
                    k=k_val
                )
                
                if not results:
                    return f"Search completed for '{query}'. No matching company regulations or policies were found."
                
                # Format matched results cleanly
                context_output = "Found the following relevant excerpts from company documents:\n\n"
                for idx, text in enumerate(results, 1):
                    context_output += f"[Excerpt {idx}]:\n{text}\n\n"
                    
                return context_output

            except Exception as e:
                error_msg = f"Error executing company database lookup: {str(e)}"
                logger.error(error_msg)
                self.company_file_read_failed = True
                return error_msg

        return query_company_knowledge_base