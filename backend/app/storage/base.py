"""Contratto di persistenza: una sola interfaccia, due implementazioni."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Le collezioni sono volutamente poche e piatte: l'app e' mono-utente.
COLLECTIONS = ("jobs", "plans", "quizzes", "reviews", "cv_reviews", "custom_topics")


@runtime_checkable
class Repository(Protocol):
    """Store documentale chiave-valore. I valori sono dict serializzabili in JSON."""

    def get(self, collection: str, key: str) -> dict | None: ...

    def put(self, collection: str, key: str, value: dict) -> None: ...

    def list(self, collection: str, limit: int = 100) -> list[dict]: ...

    def delete(self, collection: str, key: str) -> bool: ...


@runtime_checkable
class BlobStore(Protocol):
    """Archiviazione dei file caricati (CV). Opzionale: di default non salviamo nulla."""

    def put_bytes(self, path: str, data: bytes, content_type: str) -> str: ...

    def get_bytes(self, path: str) -> bytes | None: ...

    def delete(self, path: str) -> bool: ...
