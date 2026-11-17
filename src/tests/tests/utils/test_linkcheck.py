import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from photobooth.utils import linkcheck


class _Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(404 if self.path == "/missing" else 200)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def clear_cache():
    linkcheck._cache.clear()


def test_reachable_server_and_fragment_ignored(server):
    assert linkcheck.is_reachable(f"{server}/sharepage/#?url=http://example.invalid/x")


def test_404_still_means_server_is_there(server):
    assert linkcheck.is_reachable(f"{server}/missing")


def test_unreachable_server():
    assert not linkcheck.is_reachable("http://127.0.0.1:1/", timeout=1)


def test_non_http_links_are_not_checked():
    assert linkcheck.is_reachable("mailto:test@example.com")


def test_filter_keeps_order_and_removes_dead(server):
    urls = ["http://127.0.0.1:1/", f"{server}/a", f"{server}/b"]
    assert linkcheck.filter_reachable(urls, timeout=1) == urls[1:]
