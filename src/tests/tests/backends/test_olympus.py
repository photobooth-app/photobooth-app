import threading
import time
from unittest.mock import patch

import pytest
from olympuswifi.liveview import LiveViewReceiver

from photobooth.services.backends.abstractbackend import StillRequest
from photobooth.services.backends.olympus import OlympusBackend, SupersededError, _CameraCallPool
from photobooth.services.config.groups.cameras import GroupCameraOlympus


def test_still_wait_uses_capture_budget_and_cancels_timed_out_request(monkeypatch):
    backend = OlympusBackend(GroupCameraOlympus(capture_timeout=50.0, download_timeout=40.0))
    timeouts = []

    def wait_for(condition, predicate, timeout=None):
        timeouts.append(timeout)
        return False

    monkeypatch.setattr(threading.Condition, "wait_for", wait_for)

    with pytest.raises(TimeoutError, match="timeout waiting for hires frame"):
        backend.wait_for_still_file()

    request = backend._hires_queue[-1]
    assert isinstance(request, StillRequest)
    assert timeouts == [120.0]
    assert request.cancelled


def test_still_wait_surfaces_capture_errors(monkeypatch):
    backend = OlympusBackend(GroupCameraOlympus())
    failure = RuntimeError("camera download failed")

    def wait_for(condition, predicate, timeout=None):
        request = backend._hires_queue[-1]
        assert isinstance(request, StillRequest)
        request.error = failure
        return True

    monkeypatch.setattr(threading.Condition, "wait_for", wait_for)

    with pytest.raises(RuntimeError, match="camera download failed"):
        backend.wait_for_still_file()


def test_orphaned_receiver_is_not_replaced():
    ready = threading.Event()
    release = threading.Event()

    backend = OlympusBackend(GroupCameraOlympus())
    old_receiver = LiveViewReceiver(backend._frame_queue)

    def wait():
        ready.set()
        release.wait(timeout=5.0)

    old_thread = threading.Thread(target=wait)
    backend._receiver_thread = old_thread
    backend._receiver = old_receiver
    backend._receiver_orphaned = True

    try:
        old_thread.start()
        assert ready.wait(timeout=2.0)
        with patch.object(old_thread, "join") as join:
            assert not backend._ensure_receiver()
            join.assert_called_once_with(timeout=2.0)
        assert backend._receiver_thread is old_thread
        assert backend._receiver is old_receiver
        assert backend._receiver_orphaned
    finally:
        release.set()
        if old_thread.ident is not None:
            old_thread.join(timeout=2.0)


def test_camera_workers_are_isolated_between_backends():
    backend_a = OlympusBackend(GroupCameraOlympus())
    backend_b = OlympusBackend(GroupCameraOlympus())
    release = threading.Event()
    started = [threading.Event() for _ in range(4)]

    def block(index):
        started[index].set()
        release.wait(timeout=5.0)

    workers = [threading.Thread(target=backend_a._run_bounded, args=(block, i), kwargs={"timeout": 5.0}) for i in range(len(started))]
    try:
        for worker in workers:
            worker.start()
        assert all(event.wait(timeout=2.0) for event in started)
        assert backend_b._run_bounded(lambda: "ready", timeout=1.0) == "ready"
    finally:
        release.set()
        for worker in workers:
            if worker.ident is not None:
                worker.join(timeout=6.0)
        backend_a.stop()
        backend_b.stop()


def test_invalidated_camera_call_does_not_run():
    pool = _CameraCallPool(max_workers=1)
    release = threading.Event()
    started = threading.Event()
    results = {}

    def block():
        started.set()
        release.wait(timeout=5.0)

    def submit_result():
        try:
            results["queued"] = pool.submit(lambda: "unexpected", (), {}, 5.0, "test result")
        except Exception as exc:
            results["queued"] = exc

    blocker = threading.Thread(target=pool.submit, args=(block, (), {}, 5.0, "test blocker"))
    queued = threading.Thread(target=submit_result)

    try:
        blocker.start()
        assert started.wait(timeout=2.0)
        queued.start()
        with pool._condition:
            assert pool._condition.wait_for(lambda: len(pool._q) == 1, timeout=2.0)
        pool.invalidate()
    finally:
        release.set()
        for thread in (blocker, queued):
            if thread.ident is not None:
                thread.join(timeout=6.0)
        pool.close()

    assert isinstance(results["queued"], SupersededError)


def test_camera_call_pool_stops_and_reopens(monkeypatch):
    backend = OlympusBackend(GroupCameraOlympus(camera_standby_when_inactive=False))
    monkeypatch.setattr(backend, "setup_resource", lambda: None)
    monkeypatch.setattr(backend, "run_service", lambda: backend._stop_event.wait())
    monkeypatch.setattr(backend, "teardown_resource", lambda: None)

    try:
        backend.start()
        assert backend._run_bounded(lambda: "first", timeout=1.0) == "first"
        workers = tuple(backend._camera_call_pool._workers)
        assert workers
        backend.stop()
        assert all(not worker.is_alive() for worker in workers)
        with pytest.raises(RuntimeError, match="pool is closed"):
            backend._run_bounded(lambda: None)

        backend.start()
        assert backend._run_bounded(lambda: "second", timeout=1.0) == "second"
    finally:
        backend.stop()


def test_reopening_pool_does_not_replace_a_blocked_worker():
    pool = _CameraCallPool(max_workers=1)
    started = threading.Event()
    release = threading.Event()
    errors = []

    def block():
        started.set()
        release.wait(timeout=5.0)

    def submit_queued():
        try:
            pool.submit(lambda: None, (), {}, 5.0, "test pending call")
        except Exception as exc:
            errors.append(exc)

    caller = threading.Thread(target=pool.submit, args=(block, (), {}, 5.0, "test blocker"))
    queued = threading.Thread(target=submit_queued)
    try:
        caller.start()
        assert started.wait(timeout=2.0)
        queued.start()
        with pool._condition:
            assert pool._condition.wait_for(lambda: len(pool._q) == 1, timeout=2.0)
        before_close = time.monotonic()
        pool.close()
        assert time.monotonic() - before_close < 2.0
        queued.join(timeout=1.0)
        assert not queued.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], SupersededError)

        pool.reopen()
        with pytest.raises(TimeoutError):
            pool.submit(lambda: None, (), {}, 0.05, "test queued call")
        assert sum(worker.is_alive() for worker in pool._workers) == 1
        pool.invalidate()
    finally:
        release.set()
        for thread in (caller, queued):
            if thread.ident is not None:
                thread.join(timeout=6.0)
        pool.close()


def test_camera_call_queue_remains_bounded():
    pool = _CameraCallPool(max_workers=1)
    started = threading.Event()
    release = threading.Event()
    pending = [{"done": threading.Event(), "error": None} for _ in range(64)]

    def block():
        started.set()
        release.wait(timeout=5.0)

    caller = threading.Thread(target=pool.submit, args=(block, (), {}, 5.0, "test blocker"))
    try:
        caller.start()
        assert started.wait(timeout=2.0)
        with pool._condition:
            pool._q.extend(pending)
        with pytest.raises(TimeoutError, match="queue full"):
            pool.submit(lambda: None, (), {}, 0.1, "test overflow")
    finally:
        pool.close()
        release.set()
        if caller.ident is not None:
            caller.join(timeout=6.0)
        pool.close()

    assert all(box["done"].is_set() and isinstance(box["error"], SupersededError) for box in pending)
