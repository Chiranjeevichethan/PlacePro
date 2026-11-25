"""Real TCP startup/shutdown and production TLS session contracts, synthetic only."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

import pytest

from backend.tests.support import PROJECT_ROOT,create_test_storage,stop_owned_process
from backend.tests.test_sessions import PASSWORD
from backend.tests.tls_support import openssl_executable

pytestmark=pytest.mark.live_http


def request(opener,url,method='GET',body=None,headers=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,method=method,headers=headers or {})
    if body is not None:
        req.add_header('Content-Type','application/json')
    try:
        response=opener.open(req,timeout=3)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        data=response.read()
        return response.code,dict(response.headers),json.loads(data) if data else None


@pytest.mark.parametrize('tls',[False,True])
def test_actual_production_server_security_and_reliable_shutdown(isolated_storage,tls):
    storage=create_test_storage(isolated_storage.root)
    env=os.environ.copy()
    env.update(storage.environment(),PLACEPRO_TEST_STORAGE_ROOT=str(storage.root),
               PLACEPRO_TEST_RUN_ID=uuid.uuid4().hex,PLACEPRO_SECURITY_MODE='production',
               PLACEPRO_ALLOWED_ORIGINS='https://frontend.example.test',PYTHONDONTWRITEBYTECODE='1')
    # Provision only the synthetic database; no production activation implementation.
    from backend.app.services.account_service import AccountService
    from backend.app.services.account_store import AccountStore
    accounts=AccountService(AccountStore(storage.auth_db))
    accounts.register('http-synthetic@example.org',PASSWORD)
    with sqlite3.connect(storage.auth_db) as c:
        c.execute("UPDATE accounts SET status='ACTIVE',email_verified_at='2026-11-09T00:00:00+00:00'")
    sentinel=storage.profiles/'synthetic-legacy.json'
    sentinel.write_text('{"profile_id":"synthetic-legacy","history":[{"historical":true}]}')
    before=hashlib.sha256(sentinel.read_bytes()).hexdigest()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port=probe.getsockname()[1]
    command=[sys.executable,'-B','-m','backend.tests.secure_http_server',str(port)]
    if tls:
        # Standalone repeatability: generate a new trusted test certificate when needed.
        try:
            openssl=openssl_executable()
        except RuntimeError as error:
            pytest.fail(str(error))
        cert,key=storage.root/'test.crt',storage.root/'test.key'
        result=subprocess.run([str(openssl),'req','-x509','-newkey','rsa:2048','-noenc','-keyout',str(key),
                               '-out',str(cert),'-days','1','-subj','/CN=localhost',
                               '-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],capture_output=True)
        assert result.returncode==0,'Could not create isolated TLS certificate.'
        command.extend([str(key),str(cert)])
        context=ssl.create_default_context(cafile=str(cert))  # Validate own certificate; never disable TLS checking.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    else:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base=('https' if tls else 'http')+'://127.0.0.1:'+str(port)
    process,server_pid=None,None
    log_path=storage.root/'secured-server.log'
    with log_path.open('w',encoding='utf-8') as log:
        try:
            process=subprocess.Popen(command,cwd=PROJECT_ROOT,env=env,stdin=subprocess.PIPE,text=True,
                                     stdout=log,stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                assert process.poll() is None,'Owned production server exited before readiness.'
                try:
                    code,headers,_=request(opener,base+'/health')
                    assert code==200 and headers['x-placepro-test-run-id']==env['PLACEPRO_TEST_RUN_ID']
                    server_pid=int(headers['x-placepro-test-process-id'])
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else:
                pytest.fail('Owned production server startup timed out.')
            origin={'Origin':'https://frontend.example.test'}
            assert request(opener,base+'/api/profile/synthetic-legacy')[0]==401
            assert request(opener,base+'/docs')[0]==404
            assert request(opener,base+'/api/auth/register','POST',{})[0] == (503 if tls else 403)
            code,_,challenge=request(opener,base+'/api/auth/login-challenge',headers=origin)
            if tls:
                assert code==200
                code,headers,body=request(opener,base+'/api/auth/login','POST',
                                         {'email':'http-synthetic@example.org','password':PASSWORD},
                                         origin|{'X-CSRF-Token':challenge['csrf_token']})
                assert code==200 and 'HttpOnly' in headers['set-cookie'] and 'Secure' in headers['set-cookie']
                assert set(body)=={'account','idle_expires_at','absolute_expires_at'}
                assert request(opener,base+'/api/auth/session')[0]==200
                token=request(opener,base+'/api/auth/csrf',headers=origin)[2]['csrf_token']
                assert request(opener,base+'/api/assessment/synthetic-assessment',headers=origin)[0]==403
                assert request(opener,base+'/api/profile/synthetic-legacy',headers=origin)[0]==404
                from backend.tests.test_integration import student
                owned_body=student()
                owned_body.pop('profile_id')
                owned_body['personal']={'name':'Synthetic HTTP Owned Student','email':'http-synthetic@example.org'}
                created=request(opener,base+'/api/profile/verify','POST',owned_body,origin|{'X-CSRF-Token':token})
                assert created[0]==200,created[2]
                owned_id=created[2]['profile']['profile_id']
                assert request(opener,base+'/api/profile/'+owned_id,headers=origin)[0]==200
                readiness=request(opener,base+'/api/profile/'+owned_id+'/readiness',headers=origin)
                assert readiness[0]==200 and readiness[2]['profile_id']==owned_id
                assert request(opener,base+'/api/account/profiles')[2]=={'profiles':[{'profile_id':owned_id}]}
                assert request(opener,base+'/api/assessment/synthetic-assessment',headers=origin|{'X-CSRF-Token':token})[0]==404
                auth_headers=origin|{'X-CSRF-Token':token}
                from backend.tests.test_predict import SAMPLE_STUDENT
                from backend.tests.test_salary_prediction import VALID_PAYLOAD
                placement=request(opener,base+'/api/predict','POST',SAMPLE_STUDENT,auth_headers)
                salary=request(opener,base+'/api/salary-predict','POST',VALID_PAYLOAD,auth_headers)
                assert placement[0]==200 and set(placement[2])=={'placement_probability','prediction','confidence','model_version'}
                assert salary[0]==200 and set(salary[2])=={'predicted_salary_lpa','model_version'}
                prediction_headers=auth_headers|{'Idempotency-Key':'synthetic-http-intent'}
                recorded=request(opener,base+'/api/profile/'+owned_id+'/predict','POST',headers=prediction_headers)
                assert recorded[0]==200 and recorded[2]['ready_for_prediction'] is True and len(recorded[2]['prediction_history'])==1
                assert request(opener,base+'/api/profile/'+owned_id+'/predict','POST',headers=prediction_headers)[2]==recorded[2]
                started=request(opener,base+'/api/assessment/start','POST',
                                {'profile_id':owned_id,'skill':'Python','num_questions':3},auth_headers)
                assert started[0]==200,started[2]
                session=started[2]
                assert request(opener,base+'/api/assessment/'+session['assessment_id'],headers=auth_headers)[0]==200
                from backend.app.services.question_bank import get_questions
                keys={q['id']:q['correct_answer'] for q in get_questions('Python')}
                submitted=request(opener,base+'/api/assessment/'+session['assessment_id']+'/submit','POST',
                                  {'profile_id':owned_id,'answers':{q['question_id']:keys[q['question_id']] for q in session['questions']}},auth_headers)
                assert submitted[0]==200 and submitted[2]['skill_score']==100
                history=request(opener,base+'/api/profile/'+owned_id+'/assessments',headers=auth_headers)
                assert history[0]==200 and len(history[2]['assessments'])==1
                performance=request(opener,base+'/api/profile/'+owned_id+'/performance',headers=origin)
                assert performance[0]==200 and performance[2]['summary']['assessments']['assessments_count']==1
                assert performance[2]['summary']['predictions']['predictions_count']==1
                assert performance[2]['summary']['predictions']['latest_is_current'] is False
                assert request(opener,base+'/api/auth/logout','POST',headers=origin|{'X-CSRF-Token':token})[0]==204
                assert request(opener,base+'/api/auth/session')[0]==401
            else:
                assert code==403
            assert hashlib.sha256(sentinel.read_bytes()).hexdigest()==before
            if not tls:
                assert not list(storage.assessments.iterdir())
            assert not storage.companies_db.exists()
        finally:
            if process:
                try:
                    if process.poll() is None:
                        process.stdin.write('stop\n')
                        process.stdin.flush()
                    process.wait(timeout=10)
                except (OSError,subprocess.TimeoutExpired):
                    stop_owned_process(process,server_pid)
                finally:
                    process.stdin.close()
    assert process.returncode==0,log_path.read_text(encoding='utf-8')
    assert 'Application shutdown complete' in log_path.read_text(encoding='utf-8')
    with socket.socket() as connection:
        connection.settimeout(0.3)
        assert connection.connect_ex(('127.0.0.1',port))!=0
    with socket.socket() as released:
        released.bind(('127.0.0.1',port))
