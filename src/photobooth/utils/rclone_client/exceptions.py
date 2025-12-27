class RcloneConnectionException(Exception): ...


class RcloneProcessException(Exception):
    def __init__(self, error: str, input: dict | None, status: int | None, path: str | None):
        super().__init__(error)
        self.error = error
        self.input = input
        self.status = status
        self.path = path

    @staticmethod
    def from_dict(d: dict):
        return RcloneProcessException(
            error=d.get("error", "Unknown error"),
            input=d.get("input", None),
            status=d.get("status", None),
            path=d.get("path", None),
        )

    def __str__(self):
        return f"RcloneProcessException(status={self.status}, path='{self.path}', error='{self.error}', input={self.input})"
