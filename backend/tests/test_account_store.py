"""All accounts/status fixtures live exclusively in retained temporary stores."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import sqlite3
import uuid

import pytest

from backend.app.services import account_store as stores
from backend.app.services.account_store import AccountStore, AccountStorageError
from backend.app.services.password_service import PasswordService

PASSWORD = "Synthetic account phrase 2026"


@pytest.fixture(scope="module")
def encoded():
    return PasswordService().hash_password(PASSWORD)


def test_store_is_lazy_and_uses_precollection_isolated_environment(isolated_storage):
    store = AccountStore()
    assert store.path == isolated_storage.auth_db == Path(os.environ["PLACEPRO_AUTH_DB"])
    assert not store.path.exists()
    assert not store.path.is_relative_to(stores.PROJECT_ROOT / "data")


def test_persistence_uuid_status_and_no_plaintext(isolated_storage, encoded):
    store = AccountStore()
    first = store.create_account(" Person@EXAMPLE.ORG ", encoded)
    second = store.create_account("other@example.org", encoded)
    assert uuid.UUID(first.account_id).version == uuid.UUID(second.account_id).version == 4
    assert first.account_id != second.account_id
    assert first.email_normalized == "person@example.org"
    assert first.status == "PENDING_EMAIL" and first.email_verified_at is None and first.auth_version == 1
    assert first.created_at == first.updated_at == first.password_changed_at
    assert AccountStore(store.path).get_by_email("PERSON@example.org") == first
    assert PASSWORD.encode() not in store.path.read_bytes()
    with pytest.raises(FrozenInstanceError):
        first.account_id = "client-id"
    assert encoded not in repr(first) and first.email_normalized not in repr(first)


def test_duplicate_never_changes_existing_values(isolated_storage, encoded):
    store = AccountStore()
    first = store.create_account("a@example.org", encoded)
    assert store.create_account(" A@EXAMPLE.ORG ", encoded) is None
    assert store.get_by_email("a@example.org") == first


def test_database_enforces_uniqueness_independently(isolated_storage, encoded):
    store = AccountStore()
    first = store.create_account("a@example.org", encoded)
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO accounts SELECT ?,email_normalized,password_hash,status,email_verified_at,auth_version,created_at,updated_at,password_changed_at FROM accounts", (str(uuid.uuid4()),))
    assert store.get_by_email("a@example.org") == first


def test_concurrent_first_registration_has_one_record(isolated_storage, encoded):
    def create(_):
        return AccountStore().create_account("parallel@example.org", encoded)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(create, range(6)))
    assert sum(r is not None for r in results) == 1
    with sqlite3.connect(isolated_storage.auth_db) as c:
        assert c.execute("SELECT count(*) FROM accounts").fetchone()[0] == 1


@pytest.mark.parametrize("status,verified", [("UNKNOWN", None), ("ACTIVE", None)])
def test_invalid_account_states_rejected_by_database(isolated_storage, encoded, status, verified):
    store = AccountStore()
    first = store.create_account("a@example.org", encoded)
    with sqlite3.connect(store.path) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE accounts SET status=?,email_verified_at=?", (status,verified))
    assert store.get_by_email("a@example.org") == first


def test_company_database_path_is_refused(isolated_storage):
    with pytest.raises(AccountStorageError):
        AccountStore(isolated_storage.companies_db)
    assert not isolated_storage.companies_db.exists()


def test_unrelated_existing_database_is_not_changed(isolated_storage, encoded):
    target = isolated_storage.root / "unrelated.sqlite3"
    with sqlite3.connect(target) as c:
        c.execute("CREATE TABLE unrelated (value TEXT)")
        c.execute("INSERT INTO unrelated VALUES ('synthetic')")
    before = target.read_bytes()
    with pytest.raises(AccountStorageError):
        AccountStore(target).create_account("a@example.org",encoded)
    assert target.read_bytes() == before


def test_storage_connection_failure_is_sanitized(isolated_storage, monkeypatch, encoded):
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic-private-path")
    monkeypatch.setattr(stores.sqlite3,"connect",fail)
    with pytest.raises(AccountStorageError) as error:
        AccountStore().create_account("a@example.org",encoded)
    assert str(error.value) == "Account storage is temporarily unavailable."


def test_failed_insert_commit_rolls_back_and_preserves_account(isolated_storage, monkeypatch, encoded):
    store = AccountStore()
    first = store.create_account("a@example.org",encoded)
    real_connect = sqlite3.connect
    class FailingCommit(sqlite3.Connection):
        commits = 0
        def commit(self):
            self.commits += 1
            if self.commits == 2:
                raise sqlite3.OperationalError("synthetic failure before durable insert")
            return super().commit()
    with monkeypatch.context() as patch:
        patch.setattr(stores.sqlite3,"connect",lambda *a,**kw: real_connect(*a,**kw,factory=FailingCommit))
        with pytest.raises(AccountStorageError):
            store.create_account("b@example.org",encoded)
    assert store.get_by_email("a@example.org") == first
    assert store.get_by_email("b@example.org") is None
    assert store.create_account("b@example.org",encoded) is not None


def test_plaintext_cannot_be_stored(isolated_storage):
    with pytest.raises(ValueError):
        AccountStore().create_account("a@example.org",PASSWORD)
    assert not isolated_storage.auth_db.exists()
