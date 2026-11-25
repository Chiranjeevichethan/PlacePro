"""Real production-mode ownership contracts; all accounts/storage are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Barrier
import uuid

from docx import Document
from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.services.security_config import SecurityConfig
from backend.app.services.password_service import PasswordService
from backend.app.services import profile_service as profiles
from backend.app.services.ownership_store import OwnershipUnavailable
from backend.tests.test_session_security import login,csrf,ORIGIN,BASE,DEFERRED
from backend.tests.test_sessions import PASSWORD


@pytest.fixture(scope='module')
def encoded_password():
    return PasswordService().hash_password(PASSWORD)


@pytest.fixture
def pair(isolated_storage,encoded_password):
    app=create_app(SecurityConfig(origins=(ORIGIN,)))
    for email in ('one@example.org','two@example.org'):
        app.state.accounts.store.create_account(email,encoded_password)
    with sqlite3.connect(isolated_storage.auth_db) as connection:
        connection.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09T00:00:00+00:00'")
    with TestClient(app,base_url=BASE) as a,TestClient(app,base_url=BASE) as b:
        assert login(a).status_code==200 and login(b,email='two@example.org').status_code==200
        yield app,a,b,csrf(a),csrf(b)


def body():
    return {'personal':{'name':'Synthetic Owned Student','email':'one@example.org'},
            'education':{'cgpa':8.0,'branch':'CSE'},'skills':{'programming_languages':['Python']}}


def create(a,headers):
    response=a.post('/api/profile/verify',json=body(),headers=headers)
    assert response.status_code==200,response.text
    return response.json()['profile']


def identity(app,client):
    return app.state.sessions.resolve(client.cookies.get(app.state.security_config.cookie_name))


def ownership_rows(app):
    with sqlite3.connect(app.state.accounts.store.path) as c:
        return c.execute('SELECT * FROM profile_ownership').fetchall()


def snapshot(storage):
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in (storage.profiles,storage.assessments)
            for p in directory.rglob('*') if p.is_file()}


def resume():
    document=Document()
    for line in ('Synthetic Owned Resume','one@example.org','EDUCATION','B.Tech Computer Science','CGPA: 8.0','SKILLS','Python'):
        document.add_paragraph(line)
    stream=BytesIO()
    document.save(stream)
    return ('synthetic.docx',stream.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')


def test_account_bound_creation_server_uuid_multiple_profiles_and_persistent_associations(pair):
    app,a,b,ha,hb=pair
    first,second=create(a,ha),create(a,ha)
    assert uuid.UUID(first['profile_id']).version==4 and first['profile_id']!=second['profile_id']
    assert first['revision']==1 and first['verified'] is True
    assert a.get('/api/account/profiles').json()=={'profiles':[{'profile_id':r[0]} for r in ownership_rows(app)]}
    assert b.get('/api/account/profiles').json()=={'profiles':[]}
    records=ownership_rows(app)
    assert all(r[1]==identity(app,a).account_id and r[2]=='ACTIVE' and r[3]==2 for r in records)
    assert a.get('/api/profile/'+first['profile_id']).status_code==200
    restarted=create_app(SecurityConfig(origins=(ORIGIN,)))
    with TestClient(restarted,base_url=BASE) as restored:
        restored.cookies.set(app.state.security_config.cookie_name,a.cookies.get(app.state.security_config.cookie_name))
        assert restored.get('/api/profile/'+first['profile_id']).status_code==200


@pytest.mark.parametrize('operation',['get','put','verify'])
def test_missing_foreign_legacy_and_pending_targets_have_identical_404_before_validation(pair,isolated_storage,operation):
    app,a,b,ha,hb=pair
    owned=create(a,ha)
    legacy=str(uuid.uuid4())
    profiles.verify_profile({**body(),'profile_id':legacy})
    pending=str(uuid.uuid4())
    app.state.owned_profiles.store.reserve(identity(app,b),pending,'0'*64)
    targets=[owned['profile_id'],legacy,pending,str(uuid.uuid4()),'invalid-profile-id']
    before=snapshot(isolated_storage)
    responses=[]
    for target in targets:
        if operation=='get':
            response=b.get('/api/profile/'+target)
        elif operation=='put':
            response=b.put('/api/profile/'+target,content='not-json',headers=hb)
        else:
            response=b.post('/api/profile/verify',json={'profile_id':target,'personal':'invalid-sensitive-marker'},headers=hb)
        assert response.status_code==404,response.text
        responses.append(response.json())
    assert all(r=={'detail':'Profile not found.'} for r in responses)
    assert snapshot(isolated_storage)==before


def test_two_accounts_are_isolated_despite_matching_contact_emails(pair,isolated_storage):
    app,a,b,ha,hb=pair
    first,second=create(a,ha),create(b,hb)
    assert first['personal']['email']==second['personal']['email']
    before=snapshot(isolated_storage)
    assert a.get('/api/profile/'+second['profile_id']).status_code==404
    assert b.get('/api/profile/'+first['profile_id']).status_code==404
    for client,headers,target in ((a,ha,second),(b,hb,first)):
        assert client.put('/api/profile/'+target['profile_id'],json=target,headers=headers).status_code==404
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('field',['account_id','owner_id','owner_account_id','ownership','association_id'])
def test_client_owner_fields_are_rejected_without_profile_publication(pair,isolated_storage,field):
    app,a,b,ha,hb=pair
    response=a.post('/api/profile/verify',json=body()|{field:identity(app,b).account_id},headers=ha)
    assert response.status_code==422 and identity(app,b).account_id not in response.text
    assert not list(isolated_storage.profiles.glob('*.json'))


@pytest.mark.parametrize('target',['missing','foreign','legacy','empty'])
def test_client_selected_profile_id_never_creates_or_claims(pair,isolated_storage,target):
    app,a,b,ha,hb=pair
    selected=create(b,hb)['profile_id'] if target=='foreign' else str(uuid.uuid4())
    if target=='legacy':
        profiles.verify_profile(body()|{'profile_id':selected})
    if target=='empty':
        selected=''
    before=snapshot(isolated_storage)
    response=a.post('/api/profile/verify',json=body()|{'profile_id':selected},headers=ha)
    assert response.status_code==404
    assert snapshot(isolated_storage)==before


def test_owned_edit_confirmation_exact_retry_stale_conflict_and_revision_requirement(pair,isolated_storage):
    _,a,_,ha,_=pair
    initial=create(a,ha)
    edited=deepcopy(initial)
    edited['education']['cgpa']=7.0
    changed=a.put('/api/profile/'+initial['profile_id'],json=edited,headers=ha)
    assert changed.status_code==200,changed.text
    changed=changed.json()['profile']
    assert changed['revision']==2 and changed['verified'] is False
    assert a.put('/api/profile/'+initial['profile_id'],json=edited,headers=ha).json()['profile']==changed
    confirmed=a.post('/api/profile/verify',json=changed,headers=ha).json()['profile']
    assert confirmed['revision']==3 and confirmed['verified'] is True
    assert a.post('/api/profile/verify',json=changed,headers=ha).json()['profile']==confirmed
    before=snapshot(isolated_storage)
    assert a.put('/api/profile/'+initial['profile_id'],json=initial,headers=ha).status_code==409
    assert a.post('/api/profile/verify',json=initial,headers=ha).status_code==409
    no_revision=deepcopy(confirmed)
    no_revision.pop('revision')
    assert a.put('/api/profile/'+initial['profile_id'],json=no_revision,headers=ha).status_code==422
    assert a.post('/api/profile/verify',json=no_revision,headers=ha).status_code==422
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('failure',['anonymous','csrf','origin','foreign'])
def test_failed_security_checks_preserve_profile_revisions_history_and_lock_artifacts(pair,isolated_storage,failure):
    app,a,b,ha,hb=pair
    profile=create(a,ha)
    profile['education']['cgpa']=6
    before=snapshot(isolated_storage)
    if failure=='anonymous':
        with TestClient(app,base_url=BASE) as anonymous:
            assert anonymous.put('/api/profile/'+profile['profile_id'],json=profile).status_code==401
    elif failure=='csrf':
        assert a.put('/api/profile/'+profile['profile_id'],json=profile,headers={'Origin':ORIGIN}).status_code==403
    elif failure=='origin':
        assert a.put('/api/profile/'+profile['profile_id'],json=profile,headers=ha|{'Origin':'https://evil.example.test'}).status_code==403
    else:
        assert b.put('/api/profile/'+profile['profile_id'],json=profile,headers=hb).status_code==404
    assert snapshot(isolated_storage)==before


def test_history_and_originals_are_preserved_but_deferred_history_is_omitted_from_responses(pair):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    stored=profiles._load(profile['profile_id'])
    stored['assessment_evidence']=[{'skill':'Python','assessment_id':'synthetic-history','score':80}]
    stored['prediction_history']=[{'timestamp':'2026-11-09T00:00:00+00:00','model_version':'synthetic','placement_probability':0.5,'prediction':'PLACED'}]
    stored['original_resume_values']={'personal.name':'Synthetic Original'}
    profiles._save(stored)
    read=a.get('/api/profile/'+profile['profile_id']).json()['profile']
    assert 'assessment_evidence' not in read and 'prediction_history' not in read
    read['education']['cgpa']=7
    response=a.put('/api/profile/'+profile['profile_id'],json=read|{'assessment_evidence':[],'prediction_history':[]},headers=ha)
    assert response.status_code==200,response.text
    saved=profiles._load(profile['profile_id'])
    for key in ('assessment_evidence','prediction_history','original_resume_values'):
        assert saved[key]==stored[key]


def test_resume_creation_is_owned_draft_with_stable_id_through_confirmation(pair):
    app,a,b,ha,hb=pair
    response=a.post('/api/profile/from-resume',files={'file':resume()},headers=ha)
    assert response.status_code==200,response.text
    draft=response.json()['profile']
    assert draft['verified'] is False and draft['revision']==1 and uuid.UUID(draft['profile_id']).version==4
    assert b.get('/api/profile/'+draft['profile_id']).status_code==404
    confirmed=a.post('/api/profile/verify',json=draft,headers=ha)
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['profile']['profile_id']==draft['profile_id']
    assert confirmed.json()['profile']['verified'] and confirmed.json()['profile']['revision']==2


@pytest.mark.parametrize('extra',['profile_id','account_id','owner_id'])
def test_resume_extra_identity_fields_are_rejected(pair,isolated_storage,extra):
    _,a,_,ha,_=pair
    response=a.post('/api/profile/from-resume',files={'file':resume()},data={extra:str(uuid.uuid4())},headers=ha)
    assert response.status_code==422
    assert not list(isolated_storage.profiles.glob('*.json'))


@pytest.mark.parametrize('failure',['profile-write','activation','reservation','partial-write','changed-file'])
def test_creation_failures_never_publish_unowned_or_incomplete_profiles(pair,isolated_storage,monkeypatch,failure):
    app,a,_,ha,_=pair
    service=app.state.owned_profiles
    if failure=='reservation':
        def fail(*args):
            raise OwnershipUnavailable()
        monkeypatch.setattr(service.store,'reserve',fail)
    elif failure=='activation':
        def fail(*args):
            raise OwnershipUnavailable()
        monkeypatch.setattr(service.store,'activate',fail)
    else:
        original=profiles.persist_new_profile
        def fail(profile,encoded):
            if failure=='partial-write':
                Path(profiles._profile_path(profile['profile_id'])).write_bytes(b'{')
            raise profiles.ProfilePersistenceError('Synthetic unavailable.')
        if failure=='changed-file':
            def fail(profile,encoded):
                original(profile,encoded)
                Path(profiles._profile_path(profile['profile_id'])).write_text('{}')
        monkeypatch.setattr(profiles,'persist_new_profile',fail)
    response=a.post('/api/profile/verify',json=body(),headers=ha)
    assert response.status_code in {503,409},response.text
    assert a.get('/api/account/profiles').json()=={'profiles':[]}
    if failure!='reservation':
        records=ownership_rows(app)
        assert len(records)==1 and records[0][2]=='PENDING'
        assert a.get('/api/profile/'+records[0][0]).status_code==404
        assert a.post('/api/profile/verify',json=body()|{'profile_id':records[0][0]},headers=ha).status_code==404


def test_profile_uuid_collision_cannot_overwrite_or_claim_legacy_record(pair,isolated_storage,monkeypatch):
    from backend.app.services import owned_profile_service
    app,a,_,ha,_=pair
    chosen=uuid.uuid4()
    profiles.verify_profile(body()|{'profile_id':str(chosen)})
    before=snapshot(isolated_storage)
    monkeypatch.setattr(owned_profile_service.uuid,'uuid4',lambda:chosen)
    assert a.post('/api/profile/verify',json=body(),headers=ha).status_code==409
    assert snapshot(isolated_storage)==before
    assert a.get('/api/profile/'+str(chosen)).status_code==404


def test_collision_after_reservation_is_exclusively_rejected_without_overwrite(pair,monkeypatch):
    app,a,_,ha,_=pair
    original=app.state.owned_profiles.store.reserve
    sentinel=b'{"synthetic-existing":"never replace"}'
    def race(ident,profile_id,content_hash):
        original(ident,profile_id,content_hash)
        Path(profiles._profile_path(profile_id)).write_bytes(sentinel)
    monkeypatch.setattr(app.state.owned_profiles.store,'reserve',race)
    assert a.post('/api/profile/verify',json=body(),headers=ha).status_code==409
    record=ownership_rows(app)[0]
    assert Path(profiles._profile_path(record[0])).read_bytes()==sentinel and record[2]=='PENDING'


def test_concurrent_creation_generates_distinct_profiles_without_idempotency(pair):
    app,a,_,ha,_=pair
    def create_one(_):
        # Phase 29.6.8 supports keys; unkeyed explicit creations remain distinct.
        response=a.post('/api/profile/verify',json=body(),headers=ha)
        assert response.status_code==200,response.text
        return response.json()['profile']['profile_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(create_one,range(4)))
    assert len(set(ids))==4 and len(ownership_rows(app))==4


@pytest.mark.parametrize('identical',[False,True])
def test_concurrent_owned_updates_preserve_revision_conflict_guarantees(pair,identical):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    barrier=Barrier(4)
    def update(index):
        submitted=deepcopy(profile)
        submitted['personal']['phone']='same' if identical else str(index)
        barrier.wait(timeout=10)
        return a.put('/api/profile/'+profile['profile_id'],json=submitted,headers=ha).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(update,range(4)))
    assert results.count(200)==(4 if identical else 1) and results.count(409)==(0 if identical else 3)
    assert profiles._load(profile['profile_id'])['revision']==2


def test_concurrent_owned_reads_do_not_rewrite_student_files(pair,isolated_storage):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    before=snapshot(isolated_storage)
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses=list(pool.map(lambda _:a.get('/api/profile/'+profile['profile_id']).status_code,range(8)))
    assert statuses==[200]*8 and snapshot(isolated_storage)==before


@pytest.mark.parametrize('method,path',DEFERRED)
def test_owned_profile_cannot_unlock_deferred_operations(pair,isolated_storage,method,path):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    before=snapshot(isolated_storage)
    endpoint=path.replace('{profile_id}',profile['profile_id']).replace('{assessment_id}','synthetic-assessment').replace('{company_id}','company_001')
    response=a.request(method,endpoint,headers=ha,json={'profile_id':profile['profile_id']})
    assert response.status_code==503,response.text
    assert snapshot(isolated_storage)==before


@pytest.mark.parametrize('failure',['missing-trigger','bad-status','bad-version'])
def test_corrupted_ownership_is_indistinguishable_from_not_found(pair,failure):
    app,a,_,ha,_=pair
    profile=create(a,ha)
    with sqlite3.connect(app.state.accounts.store.path) as c:
        if failure=='missing-trigger':
            c.execute('DROP TRIGGER profile_ownership_immutable')
        else:
            c.execute('PRAGMA ignore_check_constraints=ON')
            c.execute("UPDATE profile_ownership SET "+("status='BROKEN'" if failure=='bad-status' else 'association_version=0'))
    assert a.get('/api/profile/'+profile['profile_id']).status_code==404
    assert a.put('/api/profile/'+profile['profile_id'],json=profile,headers=ha).json()=={'detail':'Profile not found.'}


def test_revocation_between_gate_and_ownership_acceptance_prevents_update(pair,isolated_storage,monkeypatch):
    app,a,_,ha,_=pair
    profile=create(a,ha)
    before=snapshot(isolated_storage)
    original=app.state.owned_profiles.store.authorize
    def revoke(identity,profile_id,**kwargs):
        app.state.sessions.revoke_account(identity.account_id)
        return original(identity,profile_id,**kwargs)
    monkeypatch.setattr(app.state.owned_profiles.store,'authorize',revoke)
    response=a.put('/api/profile/'+profile['profile_id'],json=profile,headers=ha)
    assert response.status_code==401 and snapshot(isolated_storage)==before


def test_logout_between_file_write_and_activation_leaves_pending_inaccessible(pair,monkeypatch):
    app,a,_,ha,_=pair
    original=profiles.persist_new_profile
    def revoke(profile,encoded):
        original(profile,encoded)
        app.state.sessions.revoke_account(identity(app,a).account_id)
    monkeypatch.setattr(profiles,'persist_new_profile',revoke)
    assert a.post('/api/profile/verify',json=body(),headers=ha).status_code==401
    assert ownership_rows(app)[0][2]=='PENDING'


def test_invalid_profile_request_and_storage_failure_have_safe_errors(pair,isolated_storage,monkeypatch,caplog):
    _,a,_,ha,_=pair
    response=a.post('/api/profile/verify',json={'personal':{'email':['SYNTHETIC-PRIVATE-MARKER']}},headers=ha)
    assert response.status_code==422 and 'SYNTHETIC-PRIVATE-MARKER' not in response.text
    assert not list(isolated_storage.profiles.glob('*.json'))
    profile=create(a,ha)
    def fail(*args):
        raise OSError('Synthetic internal private path')
    monkeypatch.setattr(profiles,'get_profile',fail)
    response=a.get('/api/profile/'+profile['profile_id'])
    assert response.status_code==503 and 'private path' not in response.text
    assert 'Synthetic internal private path' not in caplog.text


@pytest.mark.parametrize('corruption',['missing','bad-json','foreign-id','bad-schema','bad-revision'])
def test_active_association_never_authorizes_missing_or_corrupted_profile_json(pair,isolated_storage,corruption):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    target=Path(profiles._profile_path(profile['profile_id']))
    # The missing case uses a synthetic association to an absent file, without deletion.
    if corruption=='missing':
        app=pair[0]
        absent=str(uuid.uuid4())
        ident=identity(app,a)
        app.state.owned_profiles.store.reserve(ident,absent,'a'*64)
        app.state.owned_profiles.store.activate(ident,absent,'a'*64)
        selected=absent
    else:
        selected=profile['profile_id']
        if corruption=='bad-json':
            target.write_bytes(b'{')
        else:
            stored=profiles._load(selected)
            if corruption=='foreign-id':
                stored['profile_id']=str(uuid.uuid4())
            elif corruption=='bad-schema':
                stored['personal']='synthetic corrupted private marker'
            else:
                stored['revision']='wrong'
            target.write_text(json.dumps(stored),encoding='utf-8')
    before=snapshot(isolated_storage)
    for response in (a.get('/api/profile/'+selected),
                     a.put('/api/profile/'+selected,json=profile|{'profile_id':selected},headers=ha),
                     a.post('/api/profile/verify',json=profile|{'profile_id':selected},headers=ha)):
        assert response.status_code==404 and response.json()=={'detail':'Profile not found.'}
    assert snapshot(isolated_storage)==before


def test_owned_update_write_failure_preserves_profile_and_revision(pair,isolated_storage,monkeypatch):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    before=snapshot(isolated_storage)
    def fail(source,target):
        raise OSError('synthetic internal path')
    monkeypatch.setattr(profiles.os,'replace',fail)
    response=a.put('/api/profile/'+profile['profile_id'],json=profile|{'personal':profile['personal']|{'phone':'Synthetic edit'}},headers=ha)
    assert response.status_code==503 and 'internal path' not in response.text
    # Existing _save retains its scratch file on failure; persisted profile bytes stay intact.
    assert Path(profiles._profile_path(profile['profile_id'])).read_bytes()
    for path,digest in before.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    assert profiles._load(profile['profile_id'])['revision']==profile['revision']


@pytest.mark.parametrize('section,fields',[('education',{'cgpa':11}),('ml_inputs',{'dsa_score':11}),
                                        ('additional_info',{'attendance':101})])
def test_owned_numeric_validation_preserves_existing_profile(pair,isolated_storage,section,fields):
    _,a,_,ha,_=pair
    profile=create(a,ha)
    before=snapshot(isolated_storage)
    submitted=profile|{section:profile[section]|fields}
    assert a.put('/api/profile/'+profile['profile_id'],json=submitted,headers=ha).status_code==422
    assert snapshot(isolated_storage)==before


def test_anonymous_resume_is_denied_before_multipart_or_extraction(pair,isolated_storage,monkeypatch):
    app,_,_,_,_=pair
    def fail(*args,**kwargs):
        pytest.fail('Extraction must not run for an anonymous request')
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',fail)
    with TestClient(app,base_url=BASE) as anonymous:
        response=anonymous.post('/api/profile/from-resume',content=b'not multipart')
    assert response.status_code==401 and not list(isolated_storage.profiles.glob('*.json'))


@pytest.mark.parametrize('failure',['extension','empty','magic','truncated','oversize','internal-extraction'])
def test_resume_failures_are_redacted_and_do_not_reserve_or_publish_profiles(pair,isolated_storage,monkeypatch,failure):
    from backend.app.services.resume_service import CorruptedFileError,MAX_FILE_SIZE
    app,a,_,ha,_=pair
    marker='SYNTHETIC-PRIVATE-PARSER-PATH'
    cases={'extension':('synthetic.'+marker,b'data','application/octet-stream',415),
           'empty':('synthetic.pdf',b'','application/pdf',400),
           'magic':('synthetic.pdf',b'not a pdf','application/pdf',422),
           'truncated':('synthetic.pdf',b'%PDF broken','application/pdf',422),
           'oversize':('synthetic.pdf',b'x'*(MAX_FILE_SIZE+1),'application/pdf',413)}
    if failure=='internal-extraction':
        def fail(*args,**kwargs):
            raise CorruptedFileError(marker)
        monkeypatch.setattr(profiles,'prepare_draft_with_analysis',fail)
        filename,content,mime,expected='synthetic.pdf',b'%PDF', 'application/pdf',422
    else:
        filename,content,mime,expected=cases[failure]
    before=snapshot(isolated_storage)
    response=a.post('/api/profile/from-resume',files={'file':(filename,content,mime)},headers=ha)
    assert response.status_code==expected and marker not in response.text
    assert snapshot(isolated_storage)==before
    assert app.state.owned_profiles.store.list_owned(identity(app,a))==[]
    with sqlite3.connect(app.state.accounts.store.path) as connection:
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='profile_ownership'").fetchone()
