import httpx
from langchain.tools import tool

class SearXNGTool:
    def __init__(self, host: str, search_limit: int, allowed_engines: str):
        self.host = host
        self.search_limit = int(search_limit)
        self.allowed_engines = allowed_engines.split(",")
        self.latest_links = []

    def get_tool(self):
        @tool("searxng_search")
        def search(query: str) -> str:
            """Search the web using a local SearXNG instance for real-time information."""
            try:
                engines_query = ",".join(self.allowed_engines) if isinstance(self.allowed_engines, list) else self.allowed_engines
                params = {
                    "q": query,
                    "format": "json",
                    "engines": engines_query # Allowed engines from config that user configured, e.g. "google,bing,brave"
                }
                # Debug what is send to Docker SearXNG
                #print(f"DEBUG: URL: {self.host}/search?q={query}&engines={engines_query}")

                # Increase timeout as local search can take a few seconds
                response = httpx.get(f"{self.host}/search", params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    return "No results found."

                print(f"\n[Tool] SearXNG search starting: {query} with result limit: {self.search_limit} and allowed engines: {self.allowed_engines}\n")

                # Format the results for the LLM
                formatted_results = []
                for res in results[:self.search_limit]: # Limit results based on config
                    title = res.get("title")
                    link = res.get("url")
                    content = res.get("content", "")
                    formatted_results.append(f"Title: {res.get('title')}\nURL: {res.get('url')}\nContent: {res.get('content')}\n")

                    if link:
                        self.latest_links.append(link)
                        
                return "\n---\n".join(formatted_results)
            
            except Exception as e:
                return f"Error searching SearXNG: {str(e)}"
        
        return search