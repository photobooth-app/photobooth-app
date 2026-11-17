import pytest
from pytest_httpserver import HTTPServer

from photobooth.utils import linkcheck


@pytest.fixture(autouse=True)
def clear_cache():
    linkcheck._cache.clear()


def test_reachable_server_and_fragment_ignored(httpserver: HTTPServer):
    httpserver.expect_request("/sharepage/", method="HEAD").respond_with_data("OK")

    assert linkcheck.is_reachable(f"{httpserver.url_for('/sharepage/')}#?url=http://example.invalid/x")


def test_404_still_means_server_is_there(httpserver: HTTPServer):
    httpserver.expect_request("/missing", method="HEAD").respond_with_data("Not found", status=404)

    assert linkcheck.is_reachable(httpserver.url_for("/missing"))


def test_get_fallback_when_head_is_not_supported(httpserver: HTTPServer):
    httpserver.expect_request("/get-only", method="HEAD").respond_with_data("", status=405)
    httpserver.expect_request("/get-only", method="GET").respond_with_data("OK")

    assert linkcheck.is_reachable(httpserver.url_for("/get-only"))
    httpserver.check_assertions()


def test_server_error_means_unreachable(httpserver: HTTPServer):
    httpserver.expect_request("/error", method="HEAD").respond_with_data("Error", status=503)

    assert not linkcheck.is_reachable(httpserver.url_for("/error"))


def test_unreachable_server():
    assert not linkcheck.is_reachable("http://127.0.0.1:1/", timeout=1)


def test_non_http_links_are_not_checked():
    assert linkcheck.is_reachable("mailto:test@example.com")


def test_filter_keeps_order_and_removes_dead(httpserver: HTTPServer):
    httpserver.expect_request("/a", method="HEAD").respond_with_data("OK")
    httpserver.expect_request("/b", method="HEAD").respond_with_data("OK")
    urls = ["http://127.0.0.1:1/", httpserver.url_for("/a"), httpserver.url_for("/b")]

    assert linkcheck.filter_reachable(urls, timeout=1) == urls[1:]
