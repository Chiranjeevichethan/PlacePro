import './authFixtures.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRetryIntent } from '../src/services/retryIntent.js';
import { createAssessmentController } from '../src/services/assessmentSession.js';
import { startAssessment, submitAssessment } from '../src/services/api.js';
import { saveProfilePrediction } from '../src/services/ownedProfiles.js';

test('retry intent keeps the same reviewed payload and changes for revision/profile', () => {
  const intent=createRetryIntent();
  const key=intent(['profile-a',{revision:1,name:'Synthetic'}]);
  assert.equal(intent(['profile-a',{revision:1,name:'Synthetic'}]),key);
  assert.notEqual(intent(['profile-a',{revision:2,name:'Synthetic'}]),key);
  assert.notEqual(intent(['profile-b',{revision:1,name:'Synthetic'}]),key);
});

test('separate mounted account workspaces generate separate retry keys', () => {
  assert.notEqual(createRetryIntent()({revision:1}),createRetryIntent()({revision:1}));
});

test('uncertain assessment start persists and reuses its request before a response', async () => {
  const records=new Map();const keys=[];
  const storage={getItem:(k)=>records.get(k),setItem:(k,v)=>records.set(k,v)};
  const profileId='synthetic-profile';
  const session={assessment_id:'synthetic-attempt',profile_id:profileId,skill:'Python',status:'IN_PROGRESS',
    created_at:'2026-11-09T00:00:00Z',expires_at:'2026-11-09T00:05:00Z',server_now:'2026-11-09T00:00:00Z',
    questions:[{question_id:'q1',question:'Synthetic?',options:['A','B']}]};
  const api={async start(_,skill,count,key){keys.push(key);if(keys.length===1)throw new TypeError('Synthetic lost response');return session;}};
  const controller=createAssessmentController({profileId,api,storageKey:'synthetic-key',storage});
  await controller.startNew();
  assert.equal(JSON.parse(records.get('synthetic-key')).startIntent.key,keys[0]);
  await controller.startNew();
  assert.equal(keys[0],keys[1]);assert.equal(controller.getSnapshot().phase,'running');
});

for(const operation of ['start','submit']) {
  test('assessment '+operation+' forwards retry header without changing body',async(t)=>{
    t.mock.method(globalThis,'fetch',async(_,options)=>{
      assert.equal(options.headers['idempotency-key'],'synthetic-intent');
      const payload=JSON.parse(options.body);
      assert.equal(payload.profile_id,'synthetic-profile');
      assert.equal('account_id' in payload,false);assert.equal('request_id' in payload,false);
      return new Response('{}',{status:409});
    });
    const request=operation==='start' ? startAssessment('synthetic-profile','Python',3,'synthetic-intent')
      : submitAssessment('synthetic-attempt','synthetic-profile',{q:'A'},'synthetic-intent');
    await assert.rejects(request,(error)=>error.status===409);
  });
}

test('stored profile prediction uses scoped key and rejects a mismatched revision',async(t)=>{
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    assert.ok(url.endsWith('/api/profile/synthetic-profile/predict'));
    assert.equal(options.headers['idempotency-key'],'synthetic-intent');
    assert.equal(options.body,undefined);
    return new Response(JSON.stringify({profile_id:'synthetic-profile',source_revision:2,ready_for_prediction:true,prediction_history:[]}));
  });
  await assert.rejects(saveProfilePrediction('synthetic-profile',1,'synthetic-intent'),/Profile changed/);
  assert.equal((await saveProfilePrediction('synthetic-profile',2,'synthetic-intent')).source_revision,2);
});
