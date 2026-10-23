"""Private local storage for uploaded CV files (API spec 25.5, S-10, S-33).

* Files are saved as <random uuid>.<ext>; the original name lives only in the DB.
* The directory is never served over HTTP and is git-ignored.
* Every path is resolved and checked to stay inside the storage directory.
A future S3 backend only needs the same three methods.
"""

import logging
import os
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _storage_error() -> AppError:
    return AppError(
        "STORAGE_UNAVAILABLE", "File storage is temporarily unavailable. Please try again.", 503,
        retryable=True,
    )


class LocalStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()

    def _ensure_dir(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)  # owner only, where the OS supports it
        except OSError:
            pass

    def _path_for(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if path.parent != self.base_dir:
            raise ValueError("storage key escapes the storage directory")
        return path

    def save(self, data: bytes, extension: str) -> str:
        key = f"{uuid.uuid4().hex}.{extension}"
        try:
            self._ensure_dir()
            path = self._path_for(key)
            with open(path, "xb") as handle:  # "x": never overwrite an existing file
                handle.write(data)
        except OSError as exc:
            logger.error("Could not save CV file: %s", type(exc).__name__)
            raise _storage_error() from exc
        return key

    def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            logger.warning("Could not delete CV file: %s", type(exc).__name__)

    def is_writable(self) -> bool:
        try:
            self._ensure_dir()
            probe = self.base_dir / f".probe-{uuid.uuid4().hex}"
            probe.write_bytes(b"")
            probe.unlink()
            return True
        except OSError:
            return False


def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().cv_storage_dir)
