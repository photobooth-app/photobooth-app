import time


class MetricsTimer:
    def __init__(self, name: str):
        self.name = name
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self.start
        duration = time.perf_counter() - self.start

        if duration > 0.01:
            print(f"⏱️  {self.name} took {duration:.3f}s")
