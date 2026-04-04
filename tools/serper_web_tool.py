import requests
import json
from langchain_core.tools import tool

class SerperSearchTool:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.latest_links = []

    def get_web_tool(self):
        @tool
        def serper_search(query: str):
            """Search the web for current events, news, or factual information that you don't know."""
            self.latest_links.clear() # Clear previous links
            
            endpoint = "https://google.serper.dev/news" if "news" in query.lower() else "https://google.serper.dev/search"
            
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            payload = json.dumps({"q": query})
            
            print(f"\n[Tool] Serper search starting: {query}")
            
            try:
                response = requests.post(endpoint, headers=headers, data=payload)
                response.raise_for_status()
                data = response.json()
                
                results = []
                # Serper returns results in the 'organic' (or 'news') key
                search_results = data.get("organic") or data.get("news") or []
                
                for item in search_results[:5]: # Take top 5
                    title = item.get("title")
                    link = item.get("link")
                    snippet = item.get("snippet")
                    
                    results.append(f"Title: {title}\nSnippet: {snippet}\nSource: {link}\n")
                    self.latest_links.append(link) # Get links
                
                return "\n".join(results) if results else "No results found."
            
            except Exception as e:
                print(f"[Tool Error] Serper: {e}")
                return f"Error performing search: {e}"

        return serper_search