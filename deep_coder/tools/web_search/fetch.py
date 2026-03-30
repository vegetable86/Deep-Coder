import re

from bs4 import BeautifulSoup, Comment
import httpx


def fetch_and_clean(url: str) -> str:
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
    except httpx.TimeoutException:
        return "fetch failed: timeout"
    except httpx.HTTPStatusError as exc:
        return f"fetch failed: HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return f"fetch failed: {_request_error_reason(exc)}"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag_name in ("script", "style", "head"):
        for tag in soup.find_all(tag_name):
            tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    return _normalize_whitespace(soup.get_text(separator=" ", strip=True))


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _request_error_reason(exc: httpx.RequestError) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__.lower()
