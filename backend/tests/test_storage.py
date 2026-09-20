"""Il repository su file deve comportarsi come un normale store documentale."""

from __future__ import annotations

from app.storage.jsonfiles import JsonFileRepository, LocalBlobStore


def test_scrittura_e_rilettura(data_dir):
    repo = JsonFileRepository(data_dir)
    repo.put("jobs", "job_1", {"id": "job_1", "role_title": "Backend"})
    assert repo.get("jobs", "job_1")["role_title"] == "Backend"


def test_get_su_chiave_assente_restituisce_none(data_dir):
    assert JsonFileRepository(data_dir).get("jobs", "inesistente") is None


def test_list_ordina_dal_piu_recente(data_dir):
    repo = JsonFileRepository(data_dir)
    for index in range(3):
        repo.put("jobs", f"job_{index}", {"id": f"job_{index}"})
    rows = repo.list("jobs")
    assert len(rows) == 3
    assert rows[0]["id"] == "job_2"


def test_delete(data_dir):
    repo = JsonFileRepository(data_dir)
    repo.put("jobs", "job_1", {"id": "job_1"})
    assert repo.delete("jobs", "job_1") is True
    assert repo.delete("jobs", "job_1") is False


def test_serializza_i_datetime(data_dir):
    from app.domain.models import JobPosting

    repo = JsonFileRepository(data_dir)
    posting = JobPosting(role_title="Backend")
    repo.put("jobs", posting.id, posting.model_dump())
    assert isinstance(repo.get("jobs", posting.id)["created_at"], str)


def test_blob_store_locale(data_dir):
    store = LocalBlobStore(data_dir)
    store.put_bytes("cv/test.txt", b"contenuto", "text/plain")
    assert store.get_bytes("cv/test.txt") == b"contenuto"
    assert store.delete("cv/test.txt") is True
    assert store.get_bytes("cv/test.txt") is None
