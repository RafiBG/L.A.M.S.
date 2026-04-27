from langchain.agents import tool
import httpx
import time
import random
from bs4 import BeautifulSoup

try:
    from readability import Document
except ImportError:
    Document = None


class WebsiteReaderTool:
    def __init__(self):
        # State flags
        self.website_read_success = False
        self.website_read_failed = False

    def get_tool(self):
        @tool
        def read_website(url: str):
            """
            Read useful text content from a website URL when search snippets are too short.
            Best for documentation pages, blogs, articles, and product pages.
            """

            try:
                # Clean Slack formatting if needed
                clean_url = url.strip("<>").split("|")[0]

                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,image/webp,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/",
                    "Connection": "keep-alive",
                }

                # Small delay to avoid rapid-fire requests
                time.sleep(random.uniform(0.8, 1.8))

                with httpx.Client(
                    headers=headers,
                    follow_redirects=True,
                    timeout=15.0,
                    http2=True
                ) as client:
                    response = client.get(clean_url)
                    response.raise_for_status()

                clean_text = self._clean_html_content(response.text)

                # Check if content is too short (e.g., under 250 characters)
                if not clean_text or len(clean_text) < 250:
                    self.website_read_success = False
                    self.website_read_failed = True
                    print(f"[Website Tool] Content too short ({len(clean_text) if clean_text else 0} chars). Marking as failed.")
                    return f"Error: Managed to reach the site, but could not extract meaningful body text. It might be a protected page or JavaScript-heavy site."

                # If we got enough content, mark as success
                self.website_read_success = True
                self.website_read_failed = False

                print(f"\n[Tool] Website read success: {clean_url}\n")
                return f"CONTENT FROM {clean_url}:\n\n{clean_text[:4000]}"

            except httpx.HTTPStatusError as e:
                self.website_read_success = False
                self.website_read_failed = True

                error_msg = f"HTTP error: {e.response.status_code}"
                print(f"[Website Reader Tool Error] {error_msg}")

                return error_msg

            except Exception as e:
                self.website_read_success = False
                self.website_read_failed = True
                print(f"[Website Reader Tool Error] Read failed: {e}")

                return f"Error: Could not read website content. (Detail: {str(e)})"

        return [read_website]
    
    def _clean_html_content(self, html: str) -> str:
        """Extract cleaner main content with a fallback if Readability fails."""
        main_html = html
        extracted_with_readability = False

        # Try Readability first
        if Document:
            try:
                doc = Document(html)
                summary = doc.summary()
                if len(summary) > 200:  # Only use it if it actually found content
                    main_html = summary
                    extracted_with_readability = True
            except Exception:
                pass

        soup = BeautifulSoup(main_html, "html.parser")

        # If Readability failed, try to find the 'main' or 'article' tags manually
        if not extracted_with_readability:
            # Common tags for blog content
            for selector in ["article", "main", ".post-content", ".blog-post", ".entry-content"]:
                found = soup.select_one(selector)
                if found:
                    soup = found
                    break

        # Clean the soup
        for element in soup(["script", "style", "nav", "footer", "noscript", "svg", "form"]):
            element.decompose()

        # Get text and normalize whitespace
        text = soup.get_text(separator=" ")
        clean_text = " ".join(text.split())

        # If still empty, use the original HTML's body
        if len(clean_text) < 100 and not extracted_with_readability:
            # Prevents the "only title" problem on some sites
            raw_soup = BeautifulSoup(html, "html.parser")
            return " ".join(raw_soup.body.get_text(separator=" ").split())

        return clean_text