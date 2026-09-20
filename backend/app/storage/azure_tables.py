"""Persistenza su Azure Table Storage: il backend piu' economico disponibile su Azure.

Costo indicativo: ~0,05 EUR/GB/mese piu' frazioni di centesimo per transazione.
Per un'app mono-utente significa pochi centesimi l'anno.
"""

from __future__ import annotations

import json
import logging

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .base import COLLECTIONS
from .jsonfiles import _default

logger = logging.getLogger(__name__)

# Table Storage limita ogni proprieta' stringa a 64 KB (32k caratteri UTF-16) e
# l'entita' intera a 1 MB. Spezziamo il payload in blocchi per stare al sicuro.
_CHUNK_CHARS = 30_000
_MAX_CHUNKS = 28


class TableStorageRepository:
    """Una tabella per collezione, PartitionKey fissa (dataset piccolo e mono-utente)."""

    def __init__(
        self,
        account_name: str = "",
        connection_string: str = "",
        table_prefix: str = "ipc",
    ) -> None:
        self.prefix = table_prefix
        if connection_string:
            self._service = TableServiceClient.from_connection_string(connection_string)
        elif account_name:
            # Nessun segreto: in Azure ci autentichiamo con la managed identity.
            self._service = TableServiceClient(
                endpoint=f"https://{account_name}.table.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        else:
            raise ValueError(
                "Serve azure_storage_connection_string oppure azure_storage_account_name"
            )
        self._ensured: set[str] = set()

    def _table_name(self, collection: str) -> str:
        if collection not in COLLECTIONS:
            raise ValueError(f"Collezione sconosciuta: {collection}")
        # I nomi di tabella ammettono solo caratteri alfanumerici.
        return f"{self.prefix}{collection.replace('_', '')}"

    def _client(self, collection: str):
        name = self._table_name(collection)
        client = self._service.get_table_client(name)
        if name not in self._ensured:
            try:
                client.create_table()
            except ResourceExistsError:
                pass
            except Exception as exc:  # pragma: no cover - dipende dai permessi reali
                logger.warning("Impossibile creare la tabella %s: %s", name, exc)
            self._ensured.add(name)
        return client

    @staticmethod
    def _encode(value: dict) -> dict:
        payload = json.dumps(value, ensure_ascii=False, default=_default)
        chunks = [payload[i : i + _CHUNK_CHARS] for i in range(0, len(payload), _CHUNK_CHARS)]
        if len(chunks) > _MAX_CHUNKS:
            raise ValueError(
                f"Documento troppo grande per Table Storage: {len(payload)} caratteri"
            )
        entity: dict = {"chunks": len(chunks)}
        for index, chunk in enumerate(chunks):
            entity[f"p{index}"] = chunk
        return entity

    @staticmethod
    def _decode(entity: dict) -> dict | None:
        count = int(entity.get("chunks", 0))
        if not count:
            return None
        payload = "".join(entity.get(f"p{i}", "") for i in range(count))
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Payload non decodificabile per RowKey=%s", entity.get("RowKey"))
            return None

    def get(self, collection: str, key: str) -> dict | None:
        try:
            entity = self._client(collection).get_entity(partition_key=collection, row_key=key)
        except ResourceNotFoundError:
            return None
        return self._decode(dict(entity))

    def put(self, collection: str, key: str, value: dict) -> None:
        entity = self._encode(value)
        entity["PartitionKey"] = collection
        entity["RowKey"] = key
        self._client(collection).upsert_entity(entity)

    def list(self, collection: str, limit: int = 100) -> list[dict]:
        client = self._client(collection)
        out: list[dict] = []
        for entity in client.query_entities(
            f"PartitionKey eq '{collection}'", results_per_page=min(limit, 100)
        ):
            decoded = self._decode(dict(entity))
            if decoded is not None:
                out.append(decoded)
            if len(out) >= limit:
                break
        # Table Storage ordina per RowKey: riordiniamo noi per data di creazione.
        out.sort(key=lambda doc: str(doc.get("created_at", "")), reverse=True)
        return out

    def delete(self, collection: str, key: str) -> bool:
        try:
            self._client(collection).delete_entity(partition_key=collection, row_key=key)
            return True
        except ResourceNotFoundError:
            return False


class AzureBlobStore:
    """Container privato per i CV caricati. Usato solo se store_cv_files=true."""

    def __init__(
        self,
        account_name: str = "",
        connection_string: str = "",
        container: str = "cv-uploads",
    ) -> None:
        if connection_string:
            self._service = BlobServiceClient.from_connection_string(connection_string)
        elif account_name:
            self._service = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        else:
            raise ValueError("Serve una connection string o il nome dello storage account")
        self.container = container
        try:
            self._service.create_container(container)
        except ResourceExistsError:
            pass
        except Exception as exc:  # pragma: no cover - dipende dai permessi reali
            logger.warning("Impossibile creare il container %s: %s", container, exc)

    def put_bytes(self, path: str, data: bytes, content_type: str) -> str:
        from azure.storage.blob import ContentSettings

        client = self._service.get_blob_client(self.container, path)
        client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return f"{self.container}/{path}"

    def get_bytes(self, path: str) -> bytes | None:
        try:
            return self._service.get_blob_client(self.container, path).download_blob().readall()
        except ResourceNotFoundError:
            return None

    def delete(self, path: str) -> bool:
        try:
            self._service.get_blob_client(self.container, path).delete_blob()
            return True
        except ResourceNotFoundError:
            return False
