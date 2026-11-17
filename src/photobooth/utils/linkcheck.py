"""check if the server behind a share link answers, so QR codes are only shown if the link can be opened"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.parse import urldefrag

import requests

logger = logging.getLogger(__name__)

_CACHE_TTL_OK = 30.0  # seconds a successful check is trusted
_CACHE_TTL_FAIL = 5.0  # a failed check is repeated soon, so a server coming back is noticed quickly
_cache: dict[str, tuple[bool, float]] = {}
_cache_lock = Lock()


def _check_url(url: str, timeout: float) -> bool:
    """any HTTP answer below 500 proves the server is reachable (a 404 for a file that is not uploaded yet still means the server is there)."""
    for method in ("HEAD", "GET"):
        try:
            with requests.request(
                method,
                url,
                headers={"User-Agent": "photobooth-app-linkcheck"},
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            ) as response:
                if response.status_code == 405 and method == "HEAD":  # server does not allow HEAD, try GET
                    continue
                return response.status_code < 500
        except requests.RequestException as exc:
            logger.debug(f"link check failed for {url}: {exc}")
            return False
    return False


def is_reachable(url: str, timeout: float = 2.0) -> bool:
    """true if the server of the url answers. the fragment (#...) is never sent to the server and is removed. results are cached shortly."""
    if not url.lower().startswith(("http://", "https://")):
        return True  # not a web link, nothing to check

    target, _ = urldefrag(url)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(target)
        if cached and cached[1] > now:
            return cached[0]

    ok = _check_url(target, timeout)
    with _cache_lock:
        _cache[target] = (ok, now + (_CACHE_TTL_OK if ok else _CACHE_TTL_FAIL))
    return ok


def filter_reachable(urls: list[str], timeout: float = 2.0) -> list[str]:
    """returns only the urls whose server answers, checked in parallel and in the original order"""
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        results = list(pool.map(lambda u: is_reachable(u, timeout), urls))

    for url, ok in zip(urls, results, strict=True):
        if not ok:
            logger.warning(f"share link not shown because the server does not answer: {urldefrag(url)[0]}")
    return [url for url, ok in zip(urls, results, strict=True) if ok]
