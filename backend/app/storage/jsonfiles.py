"""Persistenza su file JSON: zero dipendenze esterne, perfetta per lo sviluppo locale."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from .base import COLLECTIONS


def _default(obj: object) -> str:
    # datetime/date non sono serializzabili nativamente: li salviamo ISO-8601.
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Tipo non serializzabile: {type(obj)!r}")


class JsonFileRepository:
    """Un file per documento, una cartella per collezione.

    La scrittura e' atomica (file temporaneo + rename) per non lasciare
    documenti troncati se il processo muore a meta'.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()
        for collection in COLLECTIONS:
            (self.root / collection).mkdir(parents=True, exist_ok=True)

    def _path(self, collection: str, key: str) -> Path:
        safe = "".join(ch for ch in key if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError(f"Chiave non valida: {key!r}")
        return self.root / collection / f"{safe}.json"

    def get(self, collection: str, key: str) -> dict | None:
        path = self._path(collection, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def put(self, collection: str, key: str, value: dict) -> None:
        path = self._path(collection, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, default=_default, indent=2)
        with self._lock:
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise

    def list(self, collection: str, limit: int = 100) -> list[dict]:
        folder = self.root / collection
        if not folder.exists():
            return []
        files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[dict] = []
        for path in files[:limit]:
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return out

    def delete(self, collection: str, key: str) -> bool:
        path = self._path(collection, key)
        if path.exists():
            path.unlink()
            return True
        return False


class LocalBlobStore:
    """Salva gli upload sul filesystem, accanto ai documenti JSON."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "blobs"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, path: str) -> Path:
        safe = path.replace("..", "_").lstrip("/")
        return self.root / safe

    def put_bytes(self, path: str, data: bytes, content_type: str) -> str:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def get_bytes(self, path: str) -> bytes | None:
        target = self._path(path)
        return target.read_bytes() if target.exists() else None

    def delete(self, path: str) -> bool:
        target = self._path(path)
        if target.exists():
            target.unlink()
            return True
        return False
