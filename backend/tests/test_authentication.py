"""Account foundation contracts, not a simulated authenticated student session."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import sqlite3

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import HashingError
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app as production_app
from backend.app.routes.auth import create_auth_router, UNAVAILABLE
from backend.app.schemas_auth import RegistrationRequest
from backend.app.services.account_service import AccountService, InvalidCredentials
from backend.app.services.account_store import AccountStore
from backend.app.services.account_validation import normalize_account_email
from backend.app.services import password_service as passwords

PASSWORD = "Synthetic private passphrase 2026"


@pytest.fixture(scope="module")
def password_service():
    return passwords.PasswordService()


@pytest.fixture
def service(isolated_storage, password_service):
    return AccountService(AccountStore(), password_service)


@pytest.fixture
def client(service):
    application = FastAPI()
    application.include_router(create_auth_router(service))
    with TestClient(application) as c:
        yield c


def activate_synthetic(service, email="person@example.org", status="ACTIVE"):
    # No production activation function or endpoint. Only this test database.
    with sqlite3.connect(service.store.path) as c:
        c.execute("UPDATE accounts SET status=?,email_verified_at=? WHERE email_normalized=?",
                  (status,"2026-11-08T00:00:00+00:00",email))


@pytest.mark.parametrize("raw,expected", [
    (" Student@EXAMPLE.ORG ","student@example.org"),
    ("first.last+tag@example.org","first.last+tag@example.org"),
    ("Name@b\u00fccher.de","name@xn--bcher-kva.de"),
    ("O'Connor@EXAMPLE.ORG","o'connor@example.org"),
])
def test_email_normalization_is_consistent(raw,expected):
    assert normalize_account_email(raw) == expected
    assert normalize_account_email(expected) == expected


@pytest.mark.parametrize("email", ["", "a", "a@@example.org", ".a@example.org", "a..b@example.org",
    "a@example", "a@-example.org", "a@ex_ample.org", "a@example.org.", '"a"@example.org',
    "Name <a@example.org>", "\u00e9@example.org", "a@例子。com", "a\n@example.org", "a(comment)@example.org",
    "a"*65+"@example.org", None, 12])
def test_malformed_or_unsupported_email_rejected(email):
    with pytest.raises(ValueError):
        normalize_account_email(email)


def test_argon2id_operational_unique_salts_and_parameters(password_service):
    first = password_service.hash_password(PASSWORD)
    second = password_service.hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    p = extract_parameters(first)
    assert (p.type,p.time_cost,p.memory_cost,p.parallelism,p.hash_len,p.salt_len)==(Type.ID,3,65536,1,32,16)
    assert password_service.verify_password(first,PASSWORD)
    assert not password_service.verify_password(first,"incorrect passphrase")
    assert not password_service.needs_rehash(first)


def test_password_text_is_preserved_without_trimming_or_normalization(password_service):
    value = "  synthetic cafe\u0301 password  "
    encoded = password_service.hash_password(value)
    assert password_service.verify_password(encoded,value)
    assert not password_service.verify_password(encoded,value.strip())
    assert not password_service.verify_password(encoded,value.replace("e\u0301","\u00e9"))


@pytest.mark.parametrize("encoded", [None,"plaintext","$argon2id$garbage","$argon2id$v=19$m=999999999,t=3,p=1$bad$bad"])
def test_corrupt_hash_fails_safely(password_service,encoded):
    assert password_service.verify_password(encoded,PASSWORD) is False


def test_unknown_account_uses_argon2_dummy_hash(service,monkeypatch):
    calls=[]
    original=PasswordHasher.verify
    monkeypatch.setattr(PasswordHasher,"verify",lambda self,h,p: calls.append(h) or original(self,h,p))
    with pytest.raises(InvalidCredentials):
        service.verify_credentials("unknown@example.org",PASSWORD)
    assert calls == [service.passwords._dummy_hash]


def test_registration_minimal_response_duplicate_and_pending(client,service):
    body={"email":" Person@EXAMPLE.ORG ","password":PASSWORD}
    first=client.post("/api/auth/register",json=body)
    second=client.post("/api/auth/register",json=body)
    assert first.status_code == second.status_code == 202 and first.json()==second.json()
    assert first.json()["status"]=="accepted"
    account=service.store.get_by_email("person@example.org")
    assert account.status=="PENDING_EMAIL" and account.email_verified_at is None
    assert account.password_hash not in first.text and account.account_id not in first.text
    assert PASSWORD not in first.text and not first.cookies


@pytest.mark.parametrize("body", [
    {}, {"email":"a@example.org"}, {"password":PASSWORD},
    {"email":"invalid","password":PASSWORD},
    {"email":"a@example.org","password":"weak"},
    {"email":"a@example.org","password":"x"*129},
    {"email":"a@example.org","password":"\ud800"*15},
    {"email":"a@example.org","password":False},
    {"email":"a@example.org","password":PASSWORD,"account_id":"client-selected"},
    {"email":"a@example.org","password":PASSWORD,"status":"ACTIVE","email_verified_at":"now"},
])
def test_invalid_registration_redacts_inputs_and_does_not_persist(client,service,body):
    response=client.post("/api/auth/register",content=json.dumps(body, ensure_ascii=True),headers={"Content-Type":"application/json"})
    assert response.status_code==422
    assert response.json()=={"detail":"Invalid authentication request. Check the email and password requirements."}
    assert PASSWORD not in response.text and "input" not in response.text
    assert not service.store.path.exists()


def test_malformed_json_redacts_body(client):
    response=client.post("/api/auth/register",content='{"password":"'+PASSWORD+'",',headers={"Content-Type":"application/json"})
    assert response.status_code==422 and PASSWORD not in response.text


def test_concurrent_duplicate_registration_requests(service):
    def register(_):
        service.register("parallel@example.org",PASSWORD)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(register,range(4)))
    with sqlite3.connect(service.store.path) as c:
        assert c.execute("SELECT count(*) FROM accounts").fetchone()[0]==1


def test_disabled_duplicate_registration_preserves_hash_and_status(client,service):
    service.register("person@example.org",PASSWORD)
    activate_synthetic(service,status="DISABLED")
    before=service.store.get_by_email("person@example.org")
    assert client.post("/api/auth/register",json={"email":"PERSON@example.org","password":"Different synthetic password"}).status_code==202
    assert service.store.get_by_email("person@example.org")==before


@pytest.mark.parametrize("case",["unknown","wrong","pending","disabled","deactivated","malformed"])
def test_login_failures_have_identical_content_and_no_session(client,service,case):
    if case!="unknown":
        service.register("person@example.org",PASSWORD)
    if case in {"wrong","disabled","deactivated"}:
        activate_synthetic(service,status={"disabled":"DISABLED","deactivated":"DEACTIVATED"}.get(case,"ACTIVE"))
    if case=="malformed":
        with sqlite3.connect(service.store.path) as c:
            c.execute("UPDATE accounts SET password_hash='$argon2id$garbage'")
    response=client.post("/api/auth/login",json={"email":"PERSON@example.org","password":"Wrong synthetic phrase" if case=="wrong" else PASSWORD})
    assert response.status_code==401 and response.json()=={"detail":"Invalid credentials."}
    assert "set-cookie" not in response.headers and not response.cookies
    assert response.headers["Cache-Control"]=="private, no-store"


def test_active_credentials_return_internal_identity_but_endpoint_never_session(client,service):
    service.register("person@example.org",PASSWORD)
    activate_synthetic(service)
    verified=service.verify_credentials(" PERSON@EXAMPLE.ORG ",PASSWORD)
    assert verified.account_id==service.store.get_by_email("person@example.org").account_id
    response=client.post("/api/auth/login",json={"email":"person@example.org","password":PASSWORD})
    assert response.status_code==503 and response.json()=={"detail":UNAVAILABLE}
    assert verified.account_id not in response.text and "set-cookie" not in response.headers
    with sqlite3.connect(service.store.path) as c:
        assert [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]==["accounts"]


def test_active_but_unverified_corrupt_record_is_rejected(service,monkeypatch):
    service.register("person@example.org",PASSWORD)
    activate_synthetic(service)
    bad=replace(service.store.get_by_email("person@example.org"),email_verified_at=None)
    monkeypatch.setattr(service.store,"get_by_email",lambda _:bad)
    with pytest.raises(InvalidCredentials):
        service.verify_credentials("person@example.org",PASSWORD)


def test_parameter_upgrade_preserves_identity_and_password_timestamp(service):
    old=PasswordHasher(type=Type.ID,time_cost=1,memory_cost=8192,parallelism=1).hash(PASSWORD)
    service.store.create_account("person@example.org",old)
    activate_synthetic(service)
    before=service.store.get_by_email("person@example.org")
    assert service.verify_credentials("person@example.org",PASSWORD).account_id==before.account_id
    after=service.store.get_by_email("person@example.org")
    assert not service.passwords.needs_rehash(after.password_hash)
    assert after.password_changed_at==before.password_changed_at and after.auth_version==before.auth_version


def test_conflicting_hash_upgrade_fails_closed(service,monkeypatch):
    old=PasswordHasher(type=Type.ID,time_cost=1,memory_cost=8192,parallelism=1).hash(PASSWORD)
    service.store.create_account("person@example.org",old)
    activate_synthetic(service)
    monkeypatch.setattr(service.store,"upgrade_hash",lambda *a:False)
    with pytest.raises(InvalidCredentials):
        service.verify_credentials("person@example.org",PASSWORD)


def test_hashing_failure_is_safe_and_does_not_create_account(client,service,monkeypatch):
    def fail(*args):
        raise HashingError("synthetic internal secret")
    monkeypatch.setattr(PasswordHasher,"hash",fail)
    response=client.post("/api/auth/register",json={"email":"person@example.org","password":PASSWORD})
    assert response.status_code==503 and "synthetic internal secret" not in response.text
    assert not service.store.path.exists()


def test_credentials_are_not_logged_or_in_model_repr(client,service,caplog):
    body={"email":"person@example.org","password":PASSWORD}
    request=RegistrationRequest(**body)
    assert PASSWORD not in repr(request)
    client.post("/api/auth/register",json=body)
    client.post("/api/auth/login",json=body)
    account=service.store.get_by_email(body["email"])
    assert PASSWORD not in caplog.text and account.password_hash not in caplog.text and body["email"] not in caplog.text


@pytest.mark.parametrize("endpoint",["register","login"])
def test_production_router_disabled_before_body_parsing(endpoint,isolated_storage,monkeypatch):
    monkeypatch.setenv("PLACEPRO_AUTH_FOUNDATION_ENABLED","true")  # Unsupported; never an enable switch.
    with TestClient(production_app, base_url='https://testserver') as client:
        response=client.post("/api/auth/"+endpoint,content="not-json")
    assert response.status_code == (503 if endpoint == 'register' else 403)
    assert response.json()=={"detail": ('Registration is unavailable until approved email verification is implemented.'
                                         if endpoint == 'register' else 'Request origin is not allowed.')}
    assert not isolated_storage.auth_db.exists() and "set-cookie" not in response.headers


def test_registration_and_verification_never_touch_legacy_records(service,isolated_storage):
    legacy=isolated_storage.profiles/"synthetic-legacy.json"
    history=isolated_storage.assessments/"synthetic-history.json"
    legacy.write_text('{"profile_id":"synthetic-legacy","email":"person@example.org","prediction_history":[{"legacy":true}]}')
    history.write_text('{"profile_id":"synthetic-legacy","score":80}')
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (legacy,history)]
    service.register("person@example.org",PASSWORD)
    with pytest.raises(InvalidCredentials):
        service.verify_credentials("person@example.org",PASSWORD)
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (legacy,history)]==before
    assert not isolated_storage.companies_db.exists()


def test_stronger_hash_parameters_are_not_downgraded(service):
    stronger=PasswordHasher(type=Type.ID,time_cost=4,memory_cost=65536,parallelism=1).hash(PASSWORD)
    service.store.create_account("person@example.org",stronger)
    activate_synthetic(service)
    before=service.store.get_by_email("person@example.org")
    assert not service.passwords.needs_rehash(stronger)
    service.verify_credentials("person@example.org",PASSWORD)
    assert service.store.get_by_email("person@example.org")==before


@pytest.mark.parametrize("operation",["register","login"])
def test_endpoint_database_failure_is_generic(client,service,monkeypatch,operation):
    from backend.app.services import account_store
    def fail(*args,**kwargs):
        raise sqlite3.OperationalError("synthetic private database path")
    monkeypatch.setattr(account_store.sqlite3,"connect",fail)
    response=client.post("/api/auth/"+operation,json={"email":"person@example.org","password":PASSWORD})
    assert response.status_code==503
    assert response.json()=={"detail":"Account processing is temporarily unavailable."}
    assert "set-cookie" not in response.headers and "private database" not in response.text


def test_bounded_password_work_rejects_overload_without_persistence(client,service,monkeypatch):
    class Busy:
        def acquire(self,timeout):
            return False
    monkeypatch.setattr(passwords,"_WORK",Busy())
    response=client.post("/api/auth/register",json={"email":"person@example.org","password":PASSWORD})
    assert response.status_code==503 and response.headers["Retry-After"]=="1"
    assert not service.store.path.exists()


def test_status_change_during_verification_fails_closed(service,monkeypatch):
    service.register("person@example.org",PASSWORD)
    activate_synthetic(service)
    original=service.passwords.verify_password
    def verify(encoded,password):
        result=original(encoded,password)
        activate_synthetic(service,status="DISABLED")
        return result
    monkeypatch.setattr(service.passwords,"verify_password",verify)
    with pytest.raises(InvalidCredentials):
        service.verify_credentials("person@example.org",PASSWORD)


@pytest.mark.parametrize("email",["", "a@@example.org", "a@example.org."])
def test_parser_exceptions_are_api_validation_errors(client,email):
    response=client.post("/api/auth/register",json={"email":email,"password":PASSWORD})
    assert response.status_code==422 and PASSWORD not in response.text
