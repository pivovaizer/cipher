import json
import pytest

from services.storage import JsonFileStore


class TestJsonFileStore:
    def test_read_nonexistent_returns_default(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "missing.json"))
        assert store.read("fallback") == "fallback"

    def test_write_and_read(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "data.json"))
        store.write({"key": "value"})
        assert store.read({}) == {"key": "value"}

    def test_write_list(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "data.json"))
        store.write([1, 2, 3])
        assert store.read([]) == [1, 2, 3]

    def test_overwrite(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "data.json"))
        store.write({"a": 1})
        store.write({"b": 2})
        assert store.read({}) == {"b": 2}

    def test_update(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "data.json"))
        store.write([1, 2])
        result = store.update([], lambda data: data + [3])
        assert result == [1, 2, 3]
        assert store.read([]) == [1, 2, 3]

    def test_update_nonexistent(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "new.json"))
        result = store.update([], lambda data: data + [42])
        assert result == [42]

    def test_read_corrupted_returns_default(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json!!!")
        store = JsonFileStore(str(path))
        assert store.read("default") == "default"

    def test_creates_parent_dirs(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "sub" / "dir" / "data.json"))
        store.write({"nested": True})
        assert store.read({}) == {"nested": True}

    def test_unicode(self, tmp_path):
        store = JsonFileStore(str(tmp_path / "data.json"))
        store.write({"text": "привет мир"})
        assert store.read({})["text"] == "привет мир"
