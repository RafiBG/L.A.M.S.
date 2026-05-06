from langchain.agents import tool
import httpx
import time
import random
from bs4 import BeautifulSoup, Tag
from typing import Optional

try:
    from readability import Document
except ImportError:
    Document = None


# Realistic browser profiles to rotate through
_USER_AGENTS = [
    # Chrome on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # Chrome on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Firefox on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
    # Safari on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4.1 Safari/605.1.15"
    ),
    # Edge on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    ),
]

_ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]

# CSS selectors tried in priority order for main content
_CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".post-content",
    ".article-content",
    ".entry-content",
    ".article-body",
    ".blog-post",
    ".story-body",
    ".post-body",
    ".content-body",
    "#content",
    "#main-content",
    ".main-content",
    ".page-content",
    ".site-content",
    ".body-content",
]

# Tags to always strip before extracting text
_NOISE_TAGS = [
    "script", "style", "nav", "footer", "header", "noscript",
    "svg", "form", "aside", "iframe", "figure", "figcaption",
    "button", "input", "select", "textarea", "label",
    "[class*='cookie']", "[class*='banner']", "[class*='popup']",
    "[class*='newsletter']", "[class*='subscribe']", "[id*='cookie']",
    "[id*='banner']",
]


def _build_headers(ua: str, referer: Optional[str] = None) -> dict:
    """Build a realistic browser-like header set."""
    headers = {
        "User-Agent": ua,
        "Accept": random.choice(_ACCEPT_HEADERS),
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9,en-US;q=0.8",
            "en-US,en;q=0.9,fr;q=0.8",
        ]),
        "Accept-Encoding": "gzip, deflate,",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "cross-site",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _text_density_extract(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Find the block element with the highest ratio of visible text to HTML tags.
    Useful for sites without semantic content tags like <article> or <main>.
    """
    best_tag = None
    best_score = 0.0

    for tag in soup.find_all(["div", "section", "td"], recursive=True):
        text = tag.get_text(separator=" ", strip=True)
        text_len = len(text)
        if text_len < 200:
            continue

        # Count descendant tags as a proxy for HTML noise
        child_tags = len(tag.find_all(True))
        if child_tags == 0:
            continue

        score = text_len / (child_tags + 1)

        # Penalise blocks that look like navigation or boilerplate
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        noise_words = ("nav", "menu", "sidebar", "footer", "header",
                       "comment", "widget", "ad", "promo", "cookie")
        if any(w in classes.lower() or w in tag_id.lower() for w in noise_words):
            score *= 0.2

        if score > best_score:
            best_score = score
            best_tag = tag

    return best_tag


def _clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove noisy elements in-place."""
    for selector in _NOISE_TAGS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            # Some selectors may not be valid for all versions of BS4
            pass
    return soup


def _extract_text(html: str) -> str:
    """
    Multi-strategy content extraction pipeline:
      1. Readability (best for articles / blogs)
      2. Semantic CSS selector sweep
      3. Text-density heuristic
      4. Cleaned full-body fallback
    """
    # Strategy 1 Readability
    if Document:
        try:
            doc = Document(html)
            summary = doc.summary()
            if len(summary) > 300:
                soup = BeautifulSoup(summary, "html.parser")
                _clean_soup(soup)
                text = " ".join(soup.get_text(separator=" ").split())
                if len(text) > 300:
                    return text
        except Exception:
            pass

    soup = BeautifulSoup(html, "html.parser")
    _clean_soup(soup)

    # Strategy 2 Semantic selectors 
    for selector in _CONTENT_SELECTORS:
        found = soup.select_one(selector)
        if found:
            text = " ".join(found.get_text(separator=" ").split())
            if len(text) > 300:
                return text

    # Strategy 3 Text density heuristic
    best = _text_density_extract(soup)
    if best:
        text = " ".join(best.get_text(separator=" ").split())
        if len(text) > 300:
            return text

    # Strategy 4 Cleaned body fallback
    body = soup.find("body")
    if body:
        text = " ".join(body.get_text(separator=" ").split())
        if len(text) > 100:
            return text

    return ""


class WebsiteReaderTool:
    def __init__(self):
        self.website_read_success = False
        self.website_read_failed = False

    # Internal fetch with retry / UA rotation
    def _fetch(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Try up to 3 times with different User-Agents and strategies.
        Returns (html_text, error_message).
        """
        attempts = [
            # Attempt 1 Chrome + Google referer (most common, bypasses many walls)
            (_USER_AGENTS[0], "https://www.google.com/"),
            # Attempt 2 Firefox, no referer (some sites block Google referrals)
            (_USER_AGENTS[2], None),
            # Attempt 3 Safari + Bing referer
            (_USER_AGENTS[3], "https://www.bing.com/"),
        ]

        last_error = None

        for i, (ua, referer) in enumerate(attempts):
            try:
                headers = _build_headers(ua, referer)

                # Progressive back-off between retries
                if i > 0:
                    time.sleep(random.uniform(1.5, 3.0) * i)
                else:
                    time.sleep(random.uniform(0.5, 1.2))

                with httpx.Client(
                    headers = headers,
                    follow_redirects = True,
                    timeout = 20.0,
                    http2 = True,
                    # Accept cookies so cookie-wall sites let us through
                    cookies = httpx.Cookies(),
                ) as client:
                    # Pre-warm: visit the homepage first for heavily guarded sites
                    # (only on the third attempt to avoid wasting time)
                    if i == 2:
                        try:
                            from urllib.parse import urlparse
                            origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                            client.get(origin, timeout = 8.0)
                            time.sleep(random.uniform(0.5, 1.0))
                        except Exception:
                            pass

                    response = client.get(url)

                    # Retry on rate-limit
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        time.sleep(min(retry_after, 10))
                        continue

                    response.raise_for_status()
                    return response.text, None

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                last_error = f"HTTP {status}"
                print(f"[WebsiteReader] Attempt {i+1} failed: HTTP {status} for {url}")

                # 403/401 try next UA; 404/410 pointless to retry
                if status in (404, 410, 400):
                    break

            except Exception as e:
                last_error = str(e)
                print(f"[WebsiteReader] Attempt {i+1} failed: {e}")

        return None, last_error

    def get_tool(self):
        reader = self  # capture self for use inside the nested function

        @tool
        def read_website(url: str) -> str:
            """
            Read useful text content from a website URL when search snippets are too short.
            Best for documentation pages, blogs, articles, and product pages.
            """
            # Clean Slack / markdown link formatting
            clean_url = url.strip("<>").split("|")[0].strip()

            html, error = reader._fetch(clean_url)

            if html is None:
                reader.website_read_success = False
                reader.website_read_failed = True
                msg = f"Error: Could not retrieve the page. ({error})"
                print(f"[WebsiteReader] {msg}")
                return msg

            clean_text = _extract_text(html)

            min_length = 250
            if not clean_text or len(clean_text) < min_length:
                reader.website_read_success = False
                reader.website_read_failed = True
                char_count = len(clean_text) if clean_text else 0
                msg = (
                    f"Error: Retrieved the page but could not extract meaningful content "
                    f"({char_count} chars). The site is likely JavaScript-rendered or "
                    f"requires authentication."
                )
                print(f"[WebsiteReader] {msg}")
                return msg

            reader.website_read_success = True
            reader.website_read_failed = False
            print(f"[WebsiteReader] Success — {len(clean_text)} chars from {clean_url}")

            return f"CONTENT FROM {clean_url}:\n\n{clean_text[:8000]}"

        return [read_website]