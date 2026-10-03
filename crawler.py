from collections import deque
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests

from search import is_allowed_domain


SKIP_CLASS_KEYWORDS = (
    "dw-toc",
    "hidden-print",
    "page-icons",
    "secedit",
    "socialite",
    "tools",
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text_parts = []
        self._skip_depth = 0
        self._content_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "")

        if tag == "a":
            href = attrs_dict.get("href")
            if href:
                self.links.append(href)

        if self._skip_depth:
            self._skip_depth += 1
            return

        if tag in {"script", "style", "noscript"} or should_skip_class(class_name):
            self._skip_depth += 1
            return

        if "dw-content" in class_name.split():
            self._content_depth = 1
            return

        if self._content_depth:
            self._content_depth += 1
            if tag in {"h1", "h2", "h3", "h4", "p", "li", "br", "tr"}:
                self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if self._skip_depth:
            self._skip_depth -= 1
            return

        if self._content_depth:
            if tag in {"h1", "h2", "h3", "h4", "p", "li", "tr", "table", "ul", "ol"}:
                self.text_parts.append("\n")
            self._content_depth -= 1

    def handle_data(self, data):
        if self._skip_depth or not self._content_depth:
            return

        text = " ".join(data.split())
        if text:
            self.text_parts.append(text)


def should_skip_class(class_name: str) -> bool:
    return any(keyword in class_name for keyword in SKIP_CLASS_KEYWORDS)


def normalize_text(parts: list[str]) -> str:
    lines = []
    current = []

    for part in parts:
        if part == "\n":
            line = " ".join(current).strip()
            if line:
                lines.append(line)
            current = []
        else:
            current.append(part)

    line = " ".join(current).strip()
    if line:
        lines.append(line)

    cleaned_lines = []
    previous = None
    for line in lines:
        if line != previous:
            cleaned_lines.append(line)
        previous = line

    return "\n".join(cleaned_lines)


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)

    path = parsed.path or "/"
    last_segment = path.rsplit("/", 1)[-1]
    is_dokuwiki_id = ":" in last_segment
    if "." not in last_segment and not path.endswith("/") and not is_dokuwiki_id:
        path = f"{path}/"

    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


def is_error_page(title: str, text: str) -> bool:
    normalized_title = title.lower()
    normalized_text = text.lower()
    return "404 not found" in normalized_title or normalized_text.startswith("404 not found")


def crawl_pages(seed_urls: list[str], max_pages: int) -> list[dict[str, str]]:
    queue = deque(normalize_url(url) for url in seed_urls)
    visited = set()
    pages = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in visited or not is_allowed_domain(url):
            continue

        visited.add(url)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Crawler Skip: {url} ({exc})")
            continue

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            continue

        parser = PageParser()
        parser.feed(response.text)

        title = extract_title(response.text) or urlparse(url).hostname or url
        text = normalize_text(parser.text_parts)
        if text and not is_error_page(title, text):
            pages.append({"url": url, "title": title, "text": text})

        for link in parser.links:
            absolute_url = normalize_url(urljoin(url, link))
            if absolute_url not in visited and is_allowed_domain(absolute_url):
                queue.append(absolute_url)

    return pages


def extract_title(html: str) -> str:
    lower_html = html.lower()
    start = lower_html.find("<title>")
    end = lower_html.find("</title>")
    if start == -1 or end == -1 or end <= start:
        return ""

    return " ".join(html[start + len("<title>"):end].split())
