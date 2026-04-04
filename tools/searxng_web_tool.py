import httpx
from langchain.tools import tool

class SearXNGTool:
    def __init__(self, host: str = "http://localhost:8080"):
        self.host = host
        self.latest_links = []

    def get_tool(self):
        @tool("searxng_search")
        def search(query: str) -> str:
            """Search the web using a local SearXNG instance for real-time information."""
            try:
                params = {
                    "q": query,
                    "format": "json",
                    "engines": "google,brave,duckduckgo,bing" # Top custom engines
                }
                # Increase timeout as local search can take a few seconds
                response = httpx.get(f"{self.host}/search", params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    return "No results found."

                print(f"\n[Tool] SearXNG search starting: {query}")

                # Format the top 5 results for the LLM
                formatted_results = []
                for res in results[:5]:
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