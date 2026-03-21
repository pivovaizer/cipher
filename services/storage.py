import json
import os
import threading
from pathlib import Path
from typing import Any


class JsonFileStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def read(self, default: Any) -> Any:
        with self._lock:
            if not self.path.exists():
                return default
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return default

    def write(self, payload: Any) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.path)

    def update(self, default: Any, updater):
        with self._lock:
            current = self.read(default)
            updated = updater(current)
            self.write(updated)
            return updated

