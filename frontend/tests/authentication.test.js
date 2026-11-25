import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { API_BASE_URL, authenticatedFetch, clearRequestIdentity, setRequestIdentity, rememberCSRF } from '../src/services/apiTransport.js';
import { authSession, login, logout, register, isAuthenticated, googleAuthorizationUrl,
  consumeAuthReturn } from '../src/services/auth.js';
import { createOwnedProfilesController } from '../src/services/ownedProfiles.js';
import { assessmentStorageKey } from '../src/services/assessmentSession.js';
import { predictPlacement } from '../src/services/api.js';

const idA='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', idB='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const token='a'.repeat(64);
const session=(id=idA) => ({ account: { account_id:id, email:'synthetic@example.org' },
  idle_expires_at:'2026-11-10T00:00:00+00:00', absolute_expires_at:'2026-11-10T01:00:00+00:00' });
const response=(body,status=200) => new Response(status===204 ? null : JSON.stringify(body), {status});
beforeEach(() => clearRequestIdentity());

test('login uses challenge, exact password and credential cookies without browser storage', async (t) => {
  t.mock.method(globalThis,'fetch',async (url,options) => {
    assert.equal(options.credentials,'include'); assert.equal(options.cache,'no-store');
    if (url.endsWith('/login-challenge')) return response({csrf_token:token});
    assert.ok(url.endsWith('/login'));
    assert.deepEqual(JSON.parse(options.body),{email:'synthetic@example.org',password:'  Exact password 42!  '});
    assert.equal(options.headers['X-CSRF-Token'],token);
    return response(session());
  });
  assert.equal(await login(' synthetic@example.org ','  Exact password 42!  '),true);
  assert.equal(isAuthenticated(),true);
});

test('registration restriction is an error and cannot activate a session', async (t) => {
  const original=authSession.getSnapshot();
  t.mock.method(globalThis,'fetch',async () => response({detail:'unavailable'},503));
  await assert.rejects(register('synthetic@example.org','Long synthetic password 42!'), /No account was activated/);
  assert.equal(authSession.getSnapshot(),original);
});
test('registration validates email/password before network access', async (t) => {
  t.mock.method(globalThis,'fetch',() => assert.fail('Invalid registration reached network'));
  await assert.rejects(register('invalid','short'), /valid email/);
});
test('google sign-in follows only a validated Google authorization URL', async (t) => {
  const url='https://accounts.google.com/o/oauth2/v2/auth?client_id=synthetic&state='+'a'.repeat(43);
  t.mock.method(globalThis,'fetch',async (request) => {
    assert.ok(request.endsWith('/api/auth/google/start'));
    return response({authorization_url:url});
  });
  assert.equal(await googleAuthorizationUrl(),url);
});

test('google start rejects missing, insecure or foreign authorization URLs', async (t) => {
  let payload;
  t.mock.method(globalThis,'fetch',async () => response(payload));
  for (const value of [undefined,'not-a-url','http://accounts.google.com/o/oauth2/v2/auth?state=x',
    'https://evil.example.test/auth?state=x','https://accounts.google.com/o/oauth2/v2/auth',
    'https://accounts.google.com.evil.test/o/oauth2/v2/auth?state=x']) {
    payload = {authorization_url: value};
    await assert.rejects(googleAuthorizationUrl(), /invalid response/);
  }
});

test('unconfigured Google sign-in reports a configuration error', async (t) => {
  t.mock.method(globalThis,'fetch',async () => response({detail:'not configured'},503));
  await assert.rejects(googleAuthorizationUrl(), /not configured/);
});

test('OAuth redirect results are ignored without a browser location', () => {
  assert.equal(consumeAuthReturn(),null);
});

test('session restoration uses the real safe response', async (t) => {
  t.mock.method(globalThis,'fetch',async (url) => { assert.ok(url.endsWith('/session')); return response(session()); });
  await authSession.restore();
  assert.equal(authSession.getSnapshot().status,'authenticated');
  assert.deepEqual(authSession.getSnapshot().account,session().account);
});
test('expired/revoked sessions clear authentication', async (t) => {
  t.mock.method(globalThis,'fetch',async () => response({},401));
  await authSession.restore();
  assert.equal(authSession.getSnapshot().status,'anonymous');
  assert.equal(isAuthenticated(),false);
});
test('unavailable and malformed session responses never authenticate', async (t) => {
  t.mock.method(globalThis,'fetch',async () => response({account:{account_id:idA}},200));
  await authSession.restore(); assert.equal(authSession.getSnapshot().status,'unavailable');
});
test('logout revokes server session before clearing account state', async (t) => {
  setRequestIdentity(idA); rememberCSRF(token);
  t.mock.method(globalThis,'fetch',async (url,options) => {
    assert.ok(url.endsWith('/logout')); assert.equal(options.headers['x-csrf-token'],token);
    return response(null,204);
  });
  await logout(); assert.equal(authSession.getSnapshot().status,'anonymous');
});
test('failed logout stays visible and does not falsely announce success', async (t) => {
  setRequestIdentity(idA); rememberCSRF(token);
  t.mock.method(globalThis,'fetch',async () => response({},503));
  await assert.rejects(logout(), /temporarily unavailable/);
});
for (const path of ['/api/assessment/'+idA,'/api/profile/'+idA+'/assessments']) {
  test('lifecycle GET sends session-bound CSRF: '+path,async (t) => {
    setRequestIdentity(idA); rememberCSRF(token);
    t.mock.method(globalThis,'fetch',async (_,options) => {assert.equal(options.headers['x-csrf-token'],token); return response({});});
    await authenticatedFetch(API_BASE_URL+path);
  });
}
test('concurrent mutations share CSRF retrieval but each mutation is delivered once', async (t) => {
  setRequestIdentity(idA);
  let tokens=0,mutations=0;
  t.mock.method(globalThis,'fetch',async (url) => {
    if(url.endsWith('/csrf')){tokens++; return response({csrf_token:token});}
    mutations++; return response({});
  });
  await Promise.all([authenticatedFetch(API_BASE_URL+'/api/predict',{method:'POST'}),authenticatedFetch(API_BASE_URL+'/api/salary-predict',{method:'POST'})]);
  assert.equal(tokens,1); assert.equal(mutations,2);
});
test('CSRF rejection is visible without automatic mutation replay', async (t) => {
  setRequestIdentity(idA); rememberCSRF(token); let count=0;
  t.mock.method(globalThis,'fetch',async () => {count++;return response({},403);});
  assert.equal((await authenticatedFetch(API_BASE_URL+'/api/predict',{method:'POST'})).status,403);
  assert.equal(count,1);
});
test('token retrieval rejection remains a security error in the form API', async (t) => {
  setRequestIdentity(idA);
  t.mock.method(globalThis,'fetch',async () => response({},403));
  const form={branch:'CSE',collegeTier:'Tier-3',cgpa:'8',backlogs:'0',codingSkill:'7',dsaScore:'7',aptitudeScore:'80',
    communicationSkill:'7',mlKnowledge:'5',systemDesign:'5',internships:'1',projects:'1',certifications:'1',
    hackathons:'0',openSourceContributions:'0',extracurricular:'0'};
  await assert.rejects(predictPlacement(form), (error) => error.status===403 && /Security check/.test(error.message));
});
test('late account response is rejected after an account switch', async (t) => {
  setRequestIdentity(idA); let finish;
  t.mock.method(globalThis,'fetch',() => new Promise((resolve) => {finish=resolve;}));
  const pending=authenticatedFetch(API_BASE_URL+'/api/profile/'+idA);
  setRequestIdentity(idB); finish(response({private:'old account'}));
  await assert.rejects(pending,/session changed/);
});
test('CSRF secrets cannot be forwarded to an arbitrary destination', async () => {
  setRequestIdentity(idA); rememberCSRF(token);
  await assert.rejects(authenticatedFetch('https://foreign.example.test/api/predict',{method:'POST'}),/Untrusted/);
});
test('owned profile selection excludes foreign IDs and immediately clears a previous profile', async () => {
  let finish;
  const controller=createOwnedProfilesController({listProfiles:async()=>[idA,idB],
    fetchProfile:async(id)=>id===idA ? {profile:{profile_id:id,revision:1}} : new Promise((resolve)=>{finish=resolve;})});
  await controller.reload();
  assert.equal(controller.getSnapshot().data.profile.profile_id,idA);
  assert.throws(()=>controller.select('foreign'),/available profiles/);
  const pending=controller.select(idB);
  assert.equal(controller.getSnapshot().data,null);
  finish({profile:{profile_id:idB,revision:1}}); await pending;
  assert.equal(controller.getSnapshot().data.profile.profile_id,idB);
});
test('empty accounts do not fetch a demo or legacy profile', async () => {
  const controller=createOwnedProfilesController({listProfiles:async()=>[],fetchProfile:()=>assert.fail('Legacy lookup')});
  await controller.reload(); assert.equal(controller.getSnapshot().status,'empty');
});
test('refresh restores an owned selection reference and ignores a foreign hint', async () => {
  for (const initialProfile of [idB, 'foreign']) {
    const calls=[];
    const controller=createOwnedProfilesController({initialProfile,listProfiles:async()=>[idA,idB],
      fetchProfile:async(id)=>{calls.push(id);return {profile:{profile_id:id,revision:1}};}});
    await controller.reload();
    assert.deepEqual(calls,[initialProfile===idB ? idB : idA]);
  }
});
test('assessment drafts are scoped by account and profile without session secrets', () => {
  assert.notEqual(assessmentStorageKey(idA,API_BASE_URL,idA),assessmentStorageKey(idA,API_BASE_URL,idB));
  assert.notEqual(assessmentStorageKey(idA,API_BASE_URL,idA),assessmentStorageKey(idB,API_BASE_URL,idA));
});
