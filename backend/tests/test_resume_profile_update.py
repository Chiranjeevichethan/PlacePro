"""Owned resume previews and explicit confirmation on isolated production ASGI."""
from copy import deepcopy
from io import BytesIO
import sqlite3
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.tests.test_profile_ownership import pair, encoded_password, create, snapshot, identity
from backend.tests.test_resume import make_pdf, make_docx, DOCX_MIME
from backend.tests.test_session_security import BASE
from backend.app.services import profile_service as profiles, resume_service
from backend.app.services.resume_parser import ExtractionError

TEXT = "Synthetic Resume Student\nresume@example.test\nEDUCATION\nB.Tech Computer Science\nCGPA: 8.4/10\nSKILLS\nPython, SQL\nPROJECTS\nStudy Tracker\nTechnologies: Python, Flask"

def preview(client, headers, profile, filename="resume.docx", content=None, mime=DOCX_MIME, **kwargs):
    return client.post('/api/profile/'+profile['profile_id']+'/resume-preview',
        files={'file':(filename, make_docx(TEXT) if content is None else content, mime)},
        data={'revision':str(profile['revision'])}, headers=headers, **kwargs)

@pytest.mark.parametrize('kind',['pdf','docx'])
def test_readable_preview_is_owned_revision_bound_and_never_saved(pair,isolated_storage,kind):
    _,a,_,ha,_=pair
    original=create(a,ha)
    before=snapshot(isolated_storage)
    content=make_pdf(TEXT.splitlines()) if kind=='pdf' else make_docx(TEXT)
    result=preview(a,ha,original,'resume.'+kind,content,'application/pdf' if kind=='pdf' else DOCX_MIME)
    assert result.status_code==200,result.text
    data=result.json()
    assert data['profile']['profile_id']==original['profile_id']
    assert data['profile']['revision']==original['revision']
    assert data['profile']['verified'] is False
    assert data['profile']['education']['cgpa']==8.4
    assert 'Python' in data['profile']['skills']['programming_languages']
    assert all(value is None for value in data['profile']['ml_inputs'].values())
    assert data['diagnostics']['word_count']>0 and data['provenance']
    assert result.headers['cache-control']=='private, no-store'
    assert snapshot(isolated_storage)==before
    assert a.get('/api/profile/'+original['profile_id']).json()['profile']==original

@pytest.mark.parametrize('filename,content,mime,status',[
    ('resume.exe',b'MZtest','application/octet-stream',415),
    ('resume.pdf',b'','application/pdf',400),
    ('resume.pdf',b'not a pdf','application/pdf',422),
    ('resume.pdf',b'%PDF-truncated','application/pdf',422),
    ('resume.docx',b'PK\x03\x04broken',DOCX_MIME,422),
    ('resume.pdf',b'%PDF'+b'x'*(5*1024*1024),'application/pdf',413),
    ('resume.pdf',b'%PDF'+b'x'*(6*1024*1024),'application/pdf',413),
],ids=['unsupported','empty','bad-magic','truncated-pdf','damaged-docx','oversized-file','oversized-request'])
def test_bad_uploads_preserve_profile_and_do_not_disclose_parser_details(pair,isolated_storage,filename,content,mime,status):
    _,a,_,ha,_=pair
    original=create(a,ha); before=snapshot(isolated_storage)
    response=preview(a,ha,original,filename,content,mime)
    assert response.status_code==status,response.text
    assert 'Traceback' not in response.text and str(isolated_storage.root) not in response.text
    assert snapshot(isolated_storage)==before

@pytest.mark.parametrize('kind',['anonymous','csrf','origin'])
def test_security_gate_runs_before_extraction(pair,isolated_storage,monkeypatch,kind):
    app,a,_,ha,_=pair
    original=create(a,ha)
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',lambda *args,**kwargs: pytest.fail('Unauthorized extraction'))
    before=snapshot(isolated_storage)
    if kind=='anonymous':
        with TestClient(app,base_url=BASE) as anonymous:
            response=preview(anonymous,{},original)
        expected=401
    else:
        headers=ha|({'X-CSRF-Token':'invalid'} if kind=='csrf' else {'Origin':'https://foreign.invalid'})
        response=preview(a,headers,original)
        expected=403
    assert response.status_code==expected
    assert snapshot(isolated_storage)==before

def test_foreign_missing_legacy_pending_suspended_and_corrupt_share_404_before_parsing(pair,isolated_storage,monkeypatch):
    app,a,b,ha,hb=pair
    foreign=create(a,ha)['profile_id']
    legacy=str(uuid.uuid4()); profiles.verify_profile({'profile_id':legacy,'personal':{'name':'Legacy Fixture','email':'legacy@example.test'}})
    pending=str(uuid.uuid4()); app.state.owned_profiles.store.reserve(identity(app,b),pending,'0'*64)
    suspended=create(b,hb)['profile_id']
    with sqlite3.connect(isolated_storage.auth_db) as connection:
        connection.execute("UPDATE profile_ownership SET status='SUSPENDED' WHERE profile_id=?",(suspended,))
    corrupt=create(b,hb)['profile_id']
    (isolated_storage.profiles/(corrupt+'.json')).write_text('broken synthetic record')
    before=snapshot(isolated_storage)
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',lambda *args,**kwargs: pytest.fail('Denied extraction'))
    for target in (foreign,legacy,pending,suspended,corrupt,str(uuid.uuid4())):
        response=b.post('/api/profile/'+target+'/resume-preview',content='invalid multipart',headers=hb)
        assert response.status_code==404 and response.json()=={'detail':'Profile not found.'}
    assert snapshot(isolated_storage)==before

def test_stale_revision_rejected_before_extraction_and_extra_form_owner_rejected(pair,monkeypatch):
    _,a,_,ha,_=pair
    original=create(a,ha)
    edited=deepcopy(original); edited['education']['cgpa']=9.0
    assert a.put('/api/profile/'+original['profile_id'],json=edited,headers=ha).status_code==200
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',lambda *args,**kwargs: pytest.fail('Stale extraction'))
    assert preview(a,ha,original).status_code==409
    response=a.post('/api/profile/'+original['profile_id']+'/resume-preview',
        files={'file':('resume.docx',make_docx(TEXT),DOCX_MIME)},
        data={'revision':'1','account_id':'attacker'},headers=ha)
    assert response.status_code==422 and 'attacker' not in response.text

@pytest.mark.parametrize('change',['revision','session','ownership'])
def test_changes_during_extraction_rechecked_before_preview_disclosure(pair,monkeypatch,change):
    app,a,_,ha,_=pair
    original=create(a,ha); prepare=profiles.prepare_draft_with_analysis
    def interrupted(*args,**kwargs):
        result=prepare(*args,**kwargs)
        if change=='revision':
            edited=deepcopy(original); edited['education']['cgpa']=9.0
            app.state.owned_profiles.update(identity(app,a),original['profile_id'],edited)
        elif change=='session':
            app.state.sessions.revoke_account(identity(app,a).account_id)
        else:
            with sqlite3.connect(app.state.accounts.store.path) as connection:
                connection.execute("UPDATE profile_ownership SET status='SUSPENDED' WHERE profile_id=?",(original['profile_id'],))
        return result
    monkeypatch.setattr(profiles,'prepare_draft_with_analysis',interrupted)
    response=preview(a,ha,original)
    assert response.status_code=={'revision':409,'session':401,'ownership':404}[change]
    assert 'resume@example.test' not in response.text

def test_missing_fields_and_extraction_failure_do_not_invent_or_save(pair,isolated_storage,monkeypatch):
    _,a,_,ha,_=pair
    original=create(a,ha); before=snapshot(isolated_storage)
    response=preview(a,ha,original,content=make_docx('SKILLS\nSQL'))
    assert response.status_code==200,response.text
    extracted=response.json()['profile']
    assert extracted['personal']['email'] is None and extracted['education']['cgpa'] is None
    def fail(*args,**kwargs): raise ExtractionError('PRIVATE parser details')
    monkeypatch.setattr(resume_service,'extract_text',fail)
    response=preview(a,ha,original)
    assert response.status_code==422 and 'PRIVATE' not in response.text
    assert snapshot(isolated_storage)==before

def test_corrected_confirmation_preserves_history_and_refreshes_downstream_source(pair,isolated_storage):
    _,a,b,ha,hb=pair
    original=create(a,ha)
    original['ml_inputs']={'college_tier':'Tier-2','backlogs':0,'coding_skills':7,'dsa_score':7,
        'aptitude_score':75,'communication_skills':7,'ml_knowledge':5,'system_design':4,
        'open_source_contributions':0,'extracurriculars':1}
    original=a.post('/api/profile/verify',json=original,headers=ha).json()['profile']
    path=isolated_storage.profiles/(original['profile_id']+'.json')
    predicted=a.post('/api/profile/'+original['profile_id']+'/predict',headers=ha|{'Idempotency-Key':'before-resume'})
    assert predicted.status_code==200,predicted.text
    history=deepcopy(profiles._load(original['profile_id'])['prediction_history'])
    extracted=preview(a,ha,original).json()['profile']
    # The student chooses CGPA/skills, corrects the parser's CGPA, keeps all unrelated sections.
    selected=deepcopy(original); selected['education']['cgpa']=8.7; selected['skills']=extracted['skills']
    assert b.post('/api/profile/verify',json=selected,headers=hb).status_code==404
    result=a.post('/api/profile/verify',json=selected,headers=ha|{'Idempotency-Key':'confirm-resume'})
    assert result.status_code==200,result.text
    updated=result.json()['profile']
    assert updated['revision']==original['revision']+1 and updated['verified'] is True
    assert updated['education']['cgpa']==8.7 and updated['ml_inputs']==original['ml_inputs']
    assert profiles._load(original['profile_id'])['prediction_history']==history
    before=path.read_bytes()
    assert a.post('/api/profile/verify',json=selected,headers=ha|{'Idempotency-Key':'confirm-resume'}).status_code==200
    assert path.read_bytes()==before
    stale=deepcopy(original); stale['education']['cgpa']=6
    assert a.post('/api/profile/verify',json=stale,headers=ha).status_code==409
    for suffix in ('readiness','recommendations','placement-summary'):
        response=a.get('/api/profile/'+original['profile_id']+'/'+suffix)
        assert response.status_code==200,response.text
        assert response.json()['source_revision']==updated['revision']
    assert a.post('/api/profile/'+original['profile_id']+'/predict',headers=ha|{'Idempotency-Key':'before-resume'}).status_code==409
    assert a.post('/api/profile/'+original['profile_id']+'/predict',headers=ha|{'Idempotency-Key':'after-resume'}).status_code==200
    assert len(profiles._load(original['profile_id'])['prediction_history'])==len(history)+1

def test_archive_mime_page_and_text_limits(pair):
    _,a,_,ha,_=pair
    original=create(a,ha)
    assert preview(a,ha,original,mime='application/pdf').status_code==415
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w') as archive: archive.writestr('fake.txt','not a document')
    assert preview(a,ha,original,content=stream.getvalue()).status_code==422
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','dummy')
        archive.writestr('word/document.xml','x'*(25*1024*1024+1))
    assert preview(a,ha,original,content=stream.getvalue()).status_code==422
    writer=PdfWriter()
    for _ in range(51): writer.add_blank_page(width=72,height=72)
    stream=BytesIO(); writer.write(stream)
    assert preview(a,ha,original,'resume.pdf',stream.getvalue(),'application/pdf').status_code==422
    assert preview(a,ha,original,content=make_docx('x'*200001)).status_code==422

def test_empty_docx_and_encrypted_pdf_require_readable_text_without_storage_writes(pair,isolated_storage):
    _,a,_,ha,_=pair
    original=create(a,ha); before=snapshot(isolated_storage)
    blank=preview(a,ha,original,content=make_docx(''))
    assert blank.status_code==422 and 'OCR_REQUIRED' not in blank.text
    writer=PdfWriter(); writer.add_blank_page(width=72,height=72); writer.encrypt('synthetic-document-password')
    stream=BytesIO(); writer.write(stream)
    assert preview(a,ha,original,'resume.pdf',stream.getvalue(),'application/pdf').status_code==422
    assert snapshot(isolated_storage)==before

@pytest.mark.parametrize('field,value',[('cgpa',99),('cgpa','not-a-number'),('graduation_year','invalid')])
def test_invalid_corrected_information_rejected_without_profile_update(pair,isolated_storage,field,value):
    _,a,_,ha,_=pair
    original=create(a,ha); corrected=deepcopy(original); corrected['education'][field]=value
    before=snapshot(isolated_storage)
    response=a.post('/api/profile/verify',json=corrected,headers=ha)
    assert response.status_code==422
    assert snapshot(isolated_storage)==before

def test_malformed_and_ambiguous_multipart_rejected(pair,isolated_storage):
    _,a,_,ha,_=pair
    original=create(a,ha); before=snapshot(isolated_storage)
    path='/api/profile/'+original['profile_id']+'/resume-preview'
    response=a.post(path,content='broken',headers=ha|{'Content-Type':'multipart/form-data'})
    assert response.status_code==400
    response=a.post(path,files=[('file',('one.docx',make_docx(TEXT),DOCX_MIME)),
        ('file',('two.docx',make_docx(TEXT),DOCX_MIME))],data={'revision':'1'},headers=ha)
    assert response.status_code==422
    assert snapshot(isolated_storage)==before
