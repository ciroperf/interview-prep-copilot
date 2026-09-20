"""Sceglie l'implementazione di storage in base alla configurazione."""

from __future__ import annotations

import logging
from functools import lru_cache

from ..config import Settings, get_settings
from .base import BlobStore, Repository
from .jsonfiles import JsonFileRepository, LocalBlobStore

logger = logging.getLogger(__name__)


def build_repository(settings: Settings) -> Repository:
    if settings.storage_backend == "azure_tables":
        from .azure_tables import TableStorageRepository

        return TableStorageRepository(
            account_name=settings.azure_storage_account_name,
            connection_string=settings.azure_storage_connection_string,
            table_prefix=settings.azure_table_prefix,
        )
    return JsonFileRepository(settings.data_dir)


def build_blob_store(settings: Settings) -> BlobStore:
    if settings.storage_backend == "azure_tables":
        from .azure_tables import AzureBlobStore

        return AzureBlobStore(
            account_name=settings.azure_storage_account_name,
            connection_string=settings.azure_storage_connection_string,
            container=settings.azure_blob_container,
        )
    return LocalBlobStore(settings.data_dir)


@lru_cache
def get_repository() -> Repository:
    settings = get_settings()
    repo = build_repository(settings)
    logger.info("Storage attivo: %s", settings.storage_backend)
    return repo


@lru_cache
def get_blob_store() -> BlobStore:
    return build_blob_store(get_settings())
