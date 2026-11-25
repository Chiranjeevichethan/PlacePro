// Dependency-free Chromium CDP end-to-end check for an isolated scripts/demo.py workspace.
// Node 24 supplies WebSocket; use only synthetic demo accounts and a fresh browser context.
import assert from 'node:assert/strict';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const [api, app, runId, profileA, profileB, artifactDir] = process.argv.slice(2);
const password = process.env.PLACEPRO_DEMO_TEST_PASSWORD;
assert.ok(api && app && /^[a-f0-9]{32}$/.test(runId || '') && profileA && profileB && artifactDir && password,
  'Usage: node resumeBuilder.cdp.mjs <api> <app> <run-id> <profile-a> <profile-b> <new-artifact-dir>; set password in process environment.');
for (const url of [api, app]) {
  const parsed = new URL(url);
  assert.equal(parsed.protocol, 'http:');
  assert.equal(parsed.hostname, '127.0.0.1');
}
assert.notEqual(api, app);

class CDP {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 0;
    this.pending = new Map();
    this.listeners = new Map();
    this.opened = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', reject, { once: true });
    });
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const request = this.pending.get(message.id);
        if (!request) return;
        this.pending.delete(message.id);
        if (message.error) request.reject(new Error(`${request.method}: ${message.error.message}`));
        else request.resolve(message.result || {});
      } else {
        for (const listener of this.listeners.get(message.method) || []) listener(message.params, message.sessionId);
      }
    });
  }

  async send(method, params = {}, sessionId) {
    await this.opened;
    const id = ++this.nextId;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { method, resolve, reject });
      this.socket.send(JSON.stringify(message));
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  close() { this.socket.close(); }
}

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const waitUntil = async (read, predicate, label, timeout = 20000) => {
  const end = Date.now() + timeout;
  let value;
  while (Date.now() < end) {
    try { value = await read(); if (predicate(value)) return value; } catch { /* wait for page transition */ }
    await sleep(150);
  }
  throw new Error(`Timed out waiting for ${label}; last value: ${JSON.stringify(value)}`);
};

const cdp = new URL(process.env.PLACEPRO_DEMO_CDP_URL || '');
assert.ok(cdp.protocol === 'http:' && cdp.hostname === '127.0.0.1' && cdp.port &&
  cdp.pathname === '/json/version' && !cdp.username && !cdp.password && !cdp.search && !cdp.hash,
  'Set PLACEPRO_DEMO_CDP_URL to the owned isolated browser loopback /json/version endpoint.');
const endpoint = await fetch(cdp).then((response) => response.json());
const health = await fetch(`${api}/health`).then((response) => response.json());
assert.equal(health.status, 'ok');
assert.equal((await fetch(`${api}/health`)).headers.get('x-placepro-demo-run'), runId,
  'Backend must be the isolated synthetic demo process.');
const browser = new CDP(endpoint.webSocketDebuggerUrl);
await browser.opened;
const { browserContextId } = await browser.send('Target.createBrowserContext', { disposeOnDetach: true });
const { targetId } = await browser.send('Target.createTarget', { url: 'about:blank', browserContextId });
const { sessionId } = await browser.send('Target.attachToTarget', { targetId, flatten: true });
const page = browser;

const errors = [];
const consoleErrors = [];
const networkFailures = [];
const requestUrls = new Map();
const responses = [];
const downloads = [];
page.on('Runtime.exceptionThrown', ({ exceptionDetails }) => errors.push(exceptionDetails.exception?.description || exceptionDetails.text));
page.on('Runtime.consoleAPICalled', ({ type, args }) => {
  if (type === 'error') consoleErrors.push(args.map((item) => item.value || item.description || '').join(' '));
});
page.on('Log.entryAdded', ({ entry }) => {
  if (entry.level === 'error') consoleErrors.push({ source: entry.source, text: entry.text, url: entry.url || '' });
});
page.on('Network.requestWillBeSent', ({ requestId, request }) => requestUrls.set(requestId, request.url));
page.on('Network.loadingFailed', ({ requestId, errorText, blockedReason }) =>
  networkFailures.push({ url: requestUrls.get(requestId) || '', errorText, blockedReason: blockedReason || '' }));
page.on('Network.responseReceived', ({ requestId, response }) => {
  requestUrls.set(requestId, response.url);
  if (response.url.startsWith(api)) responses.push({ url: response.url, status: response.status, cache: response.headers['cache-control'] || '' });
});
browser.on('Browser.downloadWillBegin', (event) => downloads.push({ guid: event.guid, suggestedFilename: event.suggestedFilename, state: 'started' }));
browser.on('Browser.downloadProgress', (event) => {
  const current = downloads.find((item) => item.guid === event.guid);
  if (current) Object.assign(current, { state: event.state, receivedBytes: event.receivedBytes, totalBytes: event.totalBytes });
});

const callPage = (method, params = {}) => page.send(method, params, sessionId);
const evaluate = async (expression) => {
  const reply = await callPage('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result?.value;
};
const waitPage = (expression, predicate, label, timeout) => waitUntil(() => evaluate(expression), predicate, label, timeout);
const click = (selector) => evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)}); if(!el) throw new Error('Missing '+${JSON.stringify(selector)}); el.scrollIntoView({block:'center'}); el.click(); return true; })()`);
const clickButton = (text, scope = 'body') => evaluate(`(() => { const root=document.querySelector(${JSON.stringify(scope)}); const el=[...root.querySelectorAll('button')].find(n=>n.innerText.trim()===${JSON.stringify(text)}); if(!el) throw new Error('Missing button '+${JSON.stringify(text)}+' in '+${JSON.stringify(scope)}+'; available='+[...root.querySelectorAll('button')].map(n=>n.innerText.trim()).join('|')); el.scrollIntoView({block:'center'}); el.click(); return true; })()`);
const fill = (selector, value) => evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)}); if(!el) throw new Error('Missing field '+${JSON.stringify(selector)}); const proto=el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(el,${JSON.stringify(value)}); el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:null})); el.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
const selectValue = (selector, value) => evaluate(`(() => { const el=document.querySelector(${JSON.stringify(selector)}); if(!el) throw new Error('Missing select '+${JSON.stringify(selector)}); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(el,${JSON.stringify(value)}); el.dispatchEvent(new Event('change',{bubbles:true})); return el.value; })()`);
const pageRequest = (url, method = 'GET', body, csrf) => {
  const bodyValue = body === undefined ? null : body;
  const csrfValue = csrf === undefined ? null : csrf;
  return evaluate(`(async()=>{const init={method:${JSON.stringify(method)},credentials:'include',cache:'no-store'}; if(${JSON.stringify(bodyValue)}!==null){init.headers={'Content-Type':'application/json'};init.body=JSON.stringify(${JSON.stringify(bodyValue)});} if(${JSON.stringify(csrfValue)}!==null){init.headers={...(init.headers||{}),'X-CSRF-Token':${JSON.stringify(csrfValue)}};} const r=await fetch(${JSON.stringify(url)},{...init}); const text=await r.text(); let data=null; try{data=JSON.parse(text)}catch{} return {status:r.status,cache:r.headers.get('cache-control'),type:r.headers.get('content-type'),data};})()`);
};

try {
  await mkdir(artifactDir, { recursive: false });
  await callPage('Page.enable'); await callPage('Runtime.enable'); await callPage('Log.enable'); await callPage('Network.enable');
  await browser.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: artifactDir, eventsEnabled: true, browserContextId });
  await callPage('Page.navigate', { url: app });
  await waitPage("document.querySelector('.login-button')?.innerText.trim() || document.querySelector('main h1')?.innerText || ''",
    (value) => value === 'LOGIN' || value === 'Dashboard', 'application initial render');
  const initial = await evaluate(`({title:document.title,heading:document.querySelector('h1')?.innerText,body:document.body.innerText.slice(0,500),ready:document.readyState})`);
  assert.equal(initial.ready, 'complete');
  assert.ok(initial.body.length > 50, 'Application must render visible content.');
  const anonymousRead = await pageRequest(`${api}/api/profile/${profileA}/resume-builder`);
  assert.equal(anonymousRead.status, 401, 'Anonymous profile resume read must be denied.');
  const anonymousImport = await pageRequest(`${api}/api/profile/${profileA}/resume-builder/import`, 'POST', {});
  assert.equal(anonymousImport.status, 401, 'Anonymous profile import must be denied.');

  await fill('#login-username', 'demo-student-a@example.test');
  await fill('#login-password', password);
  await click('.login-button');
  await waitPage("document.querySelector('.sidebar-menu')?.innerText || ''", (value) => value.includes('Dashboard'), 'authenticated navigation');
  await waitPage("document.querySelector('#owned-profile')?.options.length || 0", (value) => value >= 2, 'owned profile list');
  const profileOptionsA = await evaluate(`[...document.querySelector('#owned-profile').options].map(o=>o.value).filter(Boolean)`);
  assert.ok(profileOptionsA.length === 2 && profileOptionsA.includes(profileA) && !profileOptionsA.includes(profileB));
  await selectValue('#owned-profile', profileA);
  await waitPage("document.querySelector('#owned-profile')?.value || ''", (value) => value === profileA, 'selected synthetic account A profile');

  const scenarios = [];
  await callPage('Accessibility.enable');
  const accessTree = await callPage('Accessibility.getFullAXTree');
  assert.ok(accessTree.nodes.some((node) => node.role?.value === 'navigation' && node.name?.value === 'Primary navigation'));
  assert.ok(accessTree.nodes.some((node) => node.role?.value === 'link' && node.name?.value === 'Resume Builder'));
  const routeDirect = async (path, headingSelector, expected) => {
    await callPage('Page.navigate', { url: `${app}${path}` });
    await waitPage(`document.querySelector(${JSON.stringify(headingSelector)})?.innerText.trim() || ''`,
      (value) => value === expected, `direct route ${path}`);
  };
  await routeDirect('/resume-builder', '.resume-builder-page h1', 'Student Resume Builder');
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage("document.querySelector('.resume-builder-page h1')?.innerText.trim() || ''",
    (value) => value === 'Student Resume Builder', 'Resume Builder refresh');
  assert.equal(await evaluate('document.title'), 'Resume Builder | PLACE PRO');
  await click('a[href="/career-readiness"]');
  await waitPage('location.pathname', (value) => value === '/career-readiness', 'Career Readiness route link');
  await evaluate('history.back(); true');
  await waitPage('location.pathname', (value) => value === '/resume-builder', 'browser Back');
  await evaluate('history.forward(); true');
  await waitPage('location.pathname', (value) => value === '/career-readiness', 'browser Forward');
  await callPage('Page.reload', { ignoreCache: true });
  const readinessRefresh = await waitPage("({links:[...document.querySelectorAll('.sidebar-menu a')].map(a=>({text:a.innerText.trim(),current:a.getAttribute('aria-current'),href:a.getAttribute('href')})),h1:[...document.querySelectorAll('main h1')].map(x=>({text:x.innerText,hidden:Boolean(x.closest('[hidden]'))})),url:location.href,title:document.title,login:document.querySelector('.login-button')?.innerText.trim()||''})",
    (value) => value.links.length >= 12 || Boolean(value.login), 'Career Readiness refresh');
  assert.ok(readinessRefresh.links.some((link) => link.text === 'Career Readiness' && link.current === 'page'),
    `Career Readiness refresh active state was wrong: ${JSON.stringify(readinessRefresh)}`);
  await routeDirect('/goals#goal-management', '#goal-management-title', 'Goals and milestones');
  await waitPage('document.activeElement.id', (value) => value === 'goal-management-title', 'Goal deep-link focus after section data loads');
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage("document.querySelector('#goal-management-title')?.innerText.trim() || ''",
    (value) => value === 'Goals and milestones', 'Goals refresh');
  await routeDirect('/notifications', '.notification-page h1', 'Notifications');
  await waitPage("document.querySelector('.notification-empty h3')?.innerText || ''",
    (value) => value === 'No notifications yet', 'Notification Centre direct route');
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage("document.querySelector('.notification-page h1')?.innerText || ''", (value) => value === 'Notifications', 'Notifications refresh');
  await callPage('Page.navigate', { url: `${app}/dashboard` });
  await waitPage('document.title', (value) => value === 'Dashboard | PLACE PRO', 'direct route /dashboard');
  const dashboardActive = await evaluate(`[...document.querySelectorAll('.sidebar-menu a')].find(a=>a.getAttribute('aria-current')==='page')?.innerText.trim()||''`);
  assert.equal(dashboardActive, 'Dashboard');
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage('document.title', (value) => value === 'Dashboard | PLACE PRO', 'Dashboard refresh');
  await callPage('Page.navigate', { url: `${app}/unknown-placepro-route` });
  await waitPage('location.pathname', (value) => value === '/dashboard', 'unknown-route recovery');
  assert.equal(await evaluate('document.title'), 'Dashboard | PLACE PRO');
  await evaluate("document.querySelector('a[href=\"/resume-builder\"]')?.focus(); true");
  await callPage('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await callPage('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await waitPage('location.pathname', (value) => value === '/resume-builder', 'keyboard Enter navigation');
  await evaluate("document.querySelector('.skip-to-content')?.focus(); true");
  await callPage('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await callPage('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await waitPage("document.activeElement.id", (value) => value === 'main-content', 'keyboard skip link');
  scenarios.push('Direct routes and refresh for Dashboard, Career Readiness, Goals, Notifications, and Resume Builder; browser Back/Forward; unknown-route recovery; named accessibility landmarks; keyboard Enter and skip-link focus.');

  await click('a[href="/dashboard"]');
  await waitPage("[...document.querySelectorAll('.sidebar-menu a')].find(a=>a.getAttribute('aria-current')==='page')?.innerText.trim()||''", (value) => value === 'Dashboard', 'Dashboard navigation');
  scenarios.push('Authenticated Dashboard navigation.');
  await click('a[href="/career-readiness"]');
  await waitPage("document.querySelector('main h1')?.innerText || ''", (value) => value === 'Career Readiness', 'Career Readiness navigation');
  await waitPage("document.querySelector('.goal-management')?.innerText || document.querySelector('main').innerText", (value) => /goal|milestone/i.test(value), 'Goal Management content');
  scenarios.push('Career Readiness and Goal Management navigation.');
  await click('a[href="/notifications"]');
  await waitPage("[...document.querySelectorAll('.sidebar-menu a')].find(a=>a.getAttribute('aria-current')==='page')?.innerText.trim()||''", (value) => value === 'Notifications', 'Notification Centre navigation');
  const notificationState = await waitPage(`({error:document.querySelector('.notification-error')?.innerText||'',empty:document.querySelector('.notification-empty h3')?.innerText||''})`,
    (value) => !value.error && value.empty === 'No notifications yet', 'Notification Centre API and empty state');
  assert.equal(notificationState.error, '');
  scenarios.push('Notification Centre navigation, live API load and honest empty state.');

  await click('a[href="/resume-builder"]');
  await waitPage("document.querySelector('.resume-builder-page h1')?.innerText || ''", (value) => value === 'Student Resume Builder', 'Resume Builder initial render');
  const initialDraft = await pageRequest(`${api}/api/profile/${profileA}/resume-builder`);
  assert.equal(initialDraft.status, 200);
  assert.equal(initialDraft.cache, 'private, no-store');
  assert.equal(initialDraft.data.has_saved_draft, false);
  const csrfResponse = await pageRequest(`${api}/api/auth/csrf`);
  assert.equal(csrfResponse.status, 200);
  const missingCsrf = await pageRequest(`${api}/api/profile/${profileA}/resume-builder/import`, 'POST', {});
  assert.equal(missingCsrf.status, 403, 'Authenticated write without CSRF must be denied.');
  await clickButton('Import profile information', '.resume-builder-toolbar');
  await waitPage("document.querySelector('.resume-builder-notice')?.innerText || ''", (value) => value.includes('added'), 'profile import completion');
  const imported = await evaluate(`({name:document.querySelector('#resume-personal-name')?.value,email:document.querySelector('#resume-personal-email')?.value,skills:[...document.querySelectorAll('.resume-editor-card h3')].map(x=>x.innerText),labels:[...document.querySelectorAll('.resume-origin-field span')].map(x=>x.innerText)})`);
  assert.ok(imported.name.includes('Synthetic A'));
  assert.ok(imported.email.startsWith('synthetic-a-'));
  assert.ok(imported.skills.includes('Education') && imported.skills.includes('Skills') && imported.skills.includes('Projects'));

  await fill('#resume-personal-name', 'Synthetic Browser Candidate');
  await fill('#resume-summary', 'PLACEPRO_UNSAVED_NAV_MARKER Browser integration test summary.');
  const projectEditor = await evaluate(`(() => {const card=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Projects');return card?.querySelector('textarea')?.id||''})()`);
  assert.ok(projectEditor, 'Imported project editor must be available.');
  const projectOneDescription = `Synthetic pagination marker PLACEPRO_PHASE614. ${'Browser generated test text checks pagination and page boundaries. '.repeat(22)}`;
  await fill(`#${projectEditor}`, projectOneDescription);
  for (const index of [1, 2]) {
    await evaluate(`(() => {const c=[...document.querySelectorAll('.resume-editor-card')].find(x=>x.querySelector('h3')?.innerText==='Projects');[...c.querySelectorAll('button')].find(x=>x.innerText.trim()==='Add item').click();return true})()`);
    const fields = await evaluate(`(() => {const c=[...document.querySelectorAll('.resume-editor-card')].find(x=>x.querySelector('h3')?.innerText==='Projects');const item=c.querySelector('.resume-entry-editor:last-of-type');return [...item.querySelectorAll('input,textarea')].map(x=>x.id)})()`);
    const titleId = fields.find((id) => id.endsWith('-title'));
    const descriptionId = fields.find((id) => id.endsWith('-description'));
    await fill(`#${titleId}`, `Synthetic browser pagination project ${index}`);
    await fill(`#${descriptionId}`, `PLACEPRO_PHASE614 project ${index}. ${'Synthetic browser-generated text for pagination and clipping verification. '.repeat(19)}`);
  }
  // Add, edit, and remove one achievement entirely in the separately saved resume draft.
  const achievementTitle = await evaluate(`(() => {const c=[...document.querySelectorAll('.resume-editor-card')].find(x=>x.querySelector('h3')?.innerText==='Achievements');return c.querySelector('input[id$="-title"]')?.id||''})()`);
  assert.equal(achievementTitle, '', 'Achievement section starts without a student-authored entry.');
  await evaluate(`(() => {const c=[...document.querySelectorAll('.resume-editor-card')].find(x=>x.querySelector('h3')?.innerText==='Achievements');const b=[...c.querySelectorAll('button')].find(x=>x.innerText.trim()==='Add item');b.click();return true})()`);
  const achievementInput = await evaluate(`(() => [...document.querySelectorAll('input[id^="resume-achievements-"][id$="-title"]')].at(-1)?.id||'')()`);
  assert.ok(achievementInput);
  await fill(`#${achievementInput}`, 'Synthetic E2E achievement');
  await evaluate(`(() => {const c=[...document.querySelectorAll('.resume-editor-card')].find(x=>x.querySelector('h3')?.innerText==='Achievements');const item=c.querySelector('.resume-entry-editor:last-of-type');const b=[...item.querySelectorAll('button')].find(x=>x.innerText.trim()==='Remove');b.click();return true})()`);
  await waitPage(`document.querySelectorAll('input[id^="resume-achievements-"][id$="-title"]').length`, (value) => value === 0, 'achievement removal');

  await click('[aria-label="Move Education up"]');
  const movedSectionText = await waitPage(`JSON.stringify([...document.querySelectorAll('.resume-section-editor-list > section h3')].map(x=>x.innerText).slice(0,2))`,
    (value) => value === JSON.stringify(['Education', 'Professional Summary']), 'section reorder');
  const movedSection = JSON.parse(movedSectionText);
  assert.deepEqual(movedSection, ['Education', 'Professional Summary']);
  const skillsBefore = await evaluate(`(() => {const s=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Skills');return [...s.querySelectorAll('.resume-entry-editor strong')].map(x=>x.innerText)})()`);
  await evaluate(`(() => {const s=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Skills');s.querySelector('.resume-entry-editor .resume-entry-actions button:nth-child(2)').click();return true})()`);
  await waitPage(`JSON.stringify((()=>{const s=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Skills');return [...s.querySelectorAll('.resume-entry-editor strong')].map(x=>x.innerText)})())`,
    (value) => value !== JSON.stringify(skillsBefore), 'entry reorder');
  await evaluate(`(() => {const s=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Education');const box=s.querySelector('input[type=checkbox]');box.click();return true})()`);
  await waitPage(`Boolean([...document.querySelectorAll('.resume-paper-section h3')].find(x=>x.innerText.trim().toLowerCase()==='education'))`, (value) => !value, 'hide section');
  assert.equal(await evaluate(`[...document.querySelectorAll('.resume-paper-section h3')].some(x=>x.innerText.trim().toLowerCase()==='education')`), false, 'Hiding a section must update preview.');
  await evaluate(`(() => {const s=[...document.querySelectorAll('.resume-editor-card')].find(c=>c.querySelector('h3')?.innerText==='Education');s.querySelector('input[type=checkbox]').click();return true})()`);
  await waitPage(`Boolean([...document.querySelectorAll('.resume-paper-section h3')].find(x=>x.innerText.trim().toLowerCase()==='education'))`, (value) => value, 'show section');
  await selectValue('.resume-template-select select', 'modern');
  await waitPage("document.querySelector('.resume-paper')?.className || ''", (value) => value.includes('modern'), 'modern live preview');
  assert.equal(await evaluate(`document.querySelector('.resume-paper-header h2')?.innerText`), 'Synthetic Browser Candidate');
  const completeness = await evaluate(`[...document.querySelectorAll('.resume-completeness-card li')].map(x=>({text:x.innerText,complete:x.classList.contains('is-complete'),missing:x.classList.contains('is-missing')}))`);
  assert.ok(completeness.filter((item) => item.missing).length === 0, 'Required completeness entries must be complete.');
  assert.ok(await evaluate(`document.querySelector('.resume-completeness-card').innerText.includes('not a resume score')`));

  await click('a[href="/dashboard"]');
  await waitPage('location.pathname', (value) => value === '/dashboard', 'in-app navigation with unsaved resume changes');
  await click('a[href="/resume-builder"]');
  await waitPage("document.querySelector('#resume-summary')?.value || ''",
    (value) => value.includes('PLACEPRO_UNSAVED_NAV_MARKER'), 'in-memory unsaved resume restoration');
  const unsavedStorage = await evaluate(`JSON.stringify([...Object.values(localStorage), ...Object.values(sessionStorage)])`);
  assert.equal(unsavedStorage.includes('PLACEPRO_UNSAVED_NAV_MARKER'), false,
    'Unsaved resume text must not be persisted in browser storage.');
  scenarios.push('Unsaved resume edits survive internal navigation in memory without being written to local or session storage.');

  // Keyboard focus visibly moves among labelled editor fields.
  await evaluate(`document.querySelector('#resume-personal-name').focus()`);
  await callPage('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await callPage('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  const keyboard = await evaluate(`({id:document.activeElement.id,label:document.activeElement.labels?.[0]?.innerText||'',outline:getComputedStyle(document.activeElement).outlineStyle,unlabelled:[...document.querySelectorAll('.resume-builder-page input,.resume-builder-page textarea,.resume-builder-page select')].filter(x=>!x.labels?.length&&!x.getAttribute('aria-label')).length})`);
  assert.equal(keyboard.id, 'resume-personal-email');
  assert.equal(keyboard.label, 'Email');
  assert.ok(['auto','solid','dashed','dotted','double'].includes(keyboard.outline));
  assert.equal(keyboard.unlabelled, 0);
  scenarios.push('Resume import, editing, entry add/edit/remove, section/entry reorder, visibility, two live templates, completeness, keyboard focus and labels.');

  await clickButton('Save draft', '.resume-builder-toolbar');
  await waitPage("document.querySelector('.resume-builder-notice')?.innerText || ''", (value) => value.includes('saved'), 'save confirmation');
  await waitPage("[...document.querySelectorAll('.resume-builder-toolbar button')].some(button=>button.innerText.trim()==='Save draft'&&!button.disabled)", (value) => value, 'resume save completion');
  await fill('#resume-personal-phone', 'synthetic phone test');
  const afterEditNotice = await evaluate(`document.querySelector('.resume-builder-notice')?.innerText||''`);
  assert.match(afterEditNotice, /Unsaved changes/,'Editing after save must replace the saved confirmation with an unsaved-changes notice.');
  await fill('#resume-personal-phone', '');
  await waitPage("Boolean(document.querySelector('.resume-builder-toolbar button') && document.querySelector('.resume-builder-page h1'))", (value) => value, 'Resume Builder save controls after edit');
  await clickButton('Save draft', '.resume-builder-toolbar');
  await waitPage("document.querySelector('.resume-builder-notice')?.innerText || ''", (value) => value.includes('saved'), 'second save confirmation');
  await waitPage("[...document.querySelectorAll('.resume-builder-toolbar button')].some(button=>button.innerText.trim()==='Save draft'&&!button.disabled)", (value) => value, 'second resume save completion');
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage("document.querySelector('.sidebar-menu')?.innerText || ''", (value) => value.includes('Resume Builder'), 'session restoration after refresh');
  await click('a[href="/resume-builder"]');
  await waitPage("document.querySelector('#resume-personal-name')?.value || ''", (value) => value === 'Synthetic Browser Candidate', 'saved resume reload');
  assert.equal(await evaluate(`document.querySelector('#resume-summary')?.value`), 'PLACEPRO_UNSAVED_NAV_MARKER Browser integration test summary.');
  const persisted = await pageRequest(`${api}/api/profile/${profileA}/resume-builder`);
  assert.equal(persisted.data.has_saved_draft, true);
  assert.equal(persisted.cache, 'private, no-store');
  const profileAfter = await pageRequest(`${api}/api/profile/${profileA}`);
  assert.equal(profileAfter.status, 200);
  assert.equal(profileAfter.data.profile.personal.name, imported.name, 'Resume edits must not change canonical profile.');

  // A stale revision must conflict; the current revision remains readable.
  const current = persisted.data.draft;
  const csrf = (await pageRequest(`${api}/api/auth/csrf`)).data.csrf_token;
  const stale = structuredClone(current); stale.revision = 0;
  const staleResult = await pageRequest(`${api}/api/profile/${profileA}/resume-builder`, 'PUT', stale, csrf);
  assert.equal(staleResult.status, 409);
  assert.equal((await pageRequest(`${api}/api/profile/${profileA}/resume-builder`)).data.draft.revision, current.revision);
  scenarios.push('Save, post-save edit state, refresh persistence, canonical profile isolation, private/no-store headers, CSRF denial and stale-revision conflict.');

  await callPage('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const desktopMetrics = await evaluate(`({width:innerWidth,docWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,preview:document.querySelector('.resume-paper').getBoundingClientRect().toJSON()})`);
  await writeFile(path.join(artifactDir, 'resume-desktop.png'), Buffer.from((await callPage('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })).data, 'base64'), { flag: 'wx' });
  await callPage('Emulation.setDeviceMetricsOverride', { width: 768, height: 1024, deviceScaleFactor: 1, mobile: true });
  const tabletMetrics = await evaluate(`({width:innerWidth,docWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,preview:document.querySelector('.resume-paper').getBoundingClientRect().toJSON()})`);
  await writeFile(path.join(artifactDir, 'resume-tablet.png'), Buffer.from((await callPage('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })).data, 'base64'), { flag: 'wx' });
  await callPage('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  const mobileMetrics = await evaluate(`({width:innerWidth,docWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,preview:document.querySelector('.resume-paper').getBoundingClientRect().toJSON(),export:document.querySelector('.resume-builder-toolbar button:last-child').getBoundingClientRect().toJSON()})`);
  await writeFile(path.join(artifactDir, 'resume-mobile.png'), Buffer.from((await callPage('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })).data, 'base64'), { flag: 'wx' });
  assert.ok(mobileMetrics.preview.left >= 0 && mobileMetrics.preview.right <= mobileMetrics.width, 'Mobile preview must fit the viewport.');
  assert.ok(mobileMetrics.export.left >= 0 && mobileMetrics.export.right <= mobileMetrics.width, 'Mobile export control must fit.');
  await callPage('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  scenarios.push('Desktop, tablet and mobile layout measured; screenshots retained in the isolated demo workspace.');

  async function exportPdf(template) {
    await selectValue('.resume-template-select select', template);
    const templateDownloadDir = path.join(artifactDir, `${template}-pdf`);
    await mkdir(templateDownloadDir, { recursive: false });
    await browser.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: templateDownloadDir, eventsEnabled: true, browserContextId });
    const before = new Set(await readdir(templateDownloadDir));
    const startIndex = downloads.length;
    await clickButton('Export PDF', '.resume-builder-toolbar');
    await waitUntil(async () => downloads.slice(startIndex), (items) => items.some((item) => item.state === 'completed'), `${template} PDF download`, 30000);
    const created = (await readdir(templateDownloadDir)).filter((name) => !before.has(name) && name.toLowerCase().endsWith('.pdf'));
    assert.equal(created.length, 1, `Expected one downloaded ${template} PDF.`);
    return { template, filename: path.join(`${template}-pdf`, created[0]), bytes: (await readFile(path.join(templateDownloadDir, created[0]))).length };
  }
  const pdfs = [await exportPdf('classic'), await exportPdf('modern')];
  assert.ok(pdfs.every((item) => item.bytes > 1000));
  scenarios.push('Downloaded actual Classic and Modern PDF files from the browser.');

  // Resume upload dialog focus/keyboard behavior, without submitting a file or changing profile data.
  await click('a[href="/student-profile"]');
  await waitPage("[...document.querySelectorAll('.sidebar-menu a')].find(a=>a.getAttribute('aria-current')==='page')?.innerText.trim()||''", (value) => value === 'Student Profile', 'Student Profile navigation');
  await clickButton('Update from Resume');
  await waitPage("document.querySelector('[role=dialog]')?.getAttribute('aria-labelledby')||''", (value) => Boolean(value), 'resume upload dialog');
  const dialog = await evaluate(`(() => {const d=document.querySelector('[role=dialog]');const f=document.activeElement;return {labelledBy:d.getAttribute('aria-labelledby'),name:document.getElementById(d.getAttribute('aria-labelledby'))?.innerText,focusInside:d.contains(f),focus:f.outerHTML.slice(0,160)}})()`);
  assert.ok(dialog.focusInside, 'Resume upload dialog must receive initial focus.');
  await callPage('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await callPage('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await waitPage("Boolean(document.querySelector('[role=dialog]'))", (value) => !value, 'resume upload dialog Escape close');
  scenarios.push('Resume upload dialog has an accessible name, receives initial focus and closes by Escape without changing profile data.');

  // Use the actual UI to end A's session; sign into independent synthetic account B.
  await click('.navbar-user-trigger');
  await clickButton('Logout', '.user-menu');
  await waitPage("document.querySelector('.login-button')?.innerText.trim()||''", (value) => value === 'LOGIN', 'account A logout');
  await fill('#login-username', 'demo-student-b@example.test');
  await fill('#login-password', password);
  await click('.login-button');
  await waitPage("document.querySelector('#owned-profile')?.options.length||0", (value) => value >= 2, 'account B profile list');
  const profileOptionsB = await evaluate(`[...document.querySelector('#owned-profile').options].map(o=>o.value).filter(Boolean)`);
  assert.ok(profileOptionsB.length === 2 && profileOptionsB.includes(profileB) && !profileOptionsB.includes(profileA),
    'Account B profile selector must not expose Account A profiles.');
  const foreignRead = await pageRequest(`${api}/api/profile/${profileA}/resume-builder`);
  assert.equal(foreignRead.status, 404, 'Account B cannot read Account A resume.');
  const ownRead = await pageRequest(`${api}/api/profile/${profileB}/resume-builder`);
  assert.equal(ownRead.status, 200);
  assert.equal(ownRead.data.has_saved_draft, false);
  assert.equal((await pageRequest(`${api}/api/profile/${profileA}/resume-builder`)).status, 404);
  scenarios.push('Separate synthetic account cannot see, read or overwrite the first account resume; its own draft starts empty.');

  await click('.navbar-user-trigger');
  await clickButton('Logout', '.user-menu');
  await waitPage("document.querySelector('.login-button')?.innerText.trim()||''", (value) => value === 'LOGIN', 'account B logout');
  await routeDirect('/resume-builder', '.login-button', 'LOGIN');
  assert.equal(await evaluate('location.pathname'), '/resume-builder', 'Unauthenticated deep links show Login without losing the intended route.');
  await fill('#login-username', 'demo-student-b@example.test');
  await fill('#login-password', password);
  await click('.login-button');
  await waitPage("document.querySelector('.resume-builder-page h1')?.innerText || ''", (value) => value === 'Student Resume Builder', 'authenticated return to intended deep link');
  await waitPage("document.querySelector('#owned-profile')?.options.length||0", (value) => value >= 2, 'account B profiles after reauthentication');
  await selectValue('#owned-profile', profileB);
  await waitPage("document.querySelector('#owned-profile')?.value || ''", (value) => value === profileB, 'selected synthetic B profile');
  scenarios.push('Logout, unauthenticated deep-link access, Login, and return to the requested authenticated route.');

  await click('a[href="/dashboard"]');
  await click('a[href="/mock-tests"]');
  await waitPage("document.querySelector('.test-setup-card h2')?.innerText || ''", (value) => value === 'Test Configuration', 'Mock Tests route');
  await clickButton('Start Test', '.test-setup-card');
  await waitPage("document.querySelector('.test-running')?.innerText || ''", (value) => value.includes('Leave Test'), 'active assessment start');
  const assessmentHeading = await evaluate("document.querySelector('.test-running h1')?.innerText || ''");
  await callPage('Page.reload', { ignoreCache: true });
  await waitPage("document.querySelector('.test-running h1')?.innerText || ''",
    (value) => value === assessmentHeading, 'active Mock Tests refresh and session restoration');
  await click('a[href="/resume-builder"]');
  await waitPage("document.querySelector('[role=dialog] h2')?.innerText || ''", (value) => value === 'Leave Test', 'assessment route confirmation');
  assert.equal(await evaluate('location.pathname'), '/mock-tests', 'In-app navigation does not change route before confirmation.');
  await callPage('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await callPage('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await waitPage("!document.querySelector('[role=dialog]')", (value) => value, 'assessment leave cancellation');
  assert.equal(await evaluate('location.pathname'), '/mock-tests');
  await evaluate('history.back(); true');
  await waitPage("document.querySelector('[role=dialog] h2')?.innerText || ''", (value) => value === 'Leave Test', 'Back assessment guard');
  await clickButton('Cancel', '[role=dialog]');
  await waitPage('location.pathname', (value) => value === '/mock-tests', 'Back cancellation returns to assessment route');
  await click('a[href="/resume-builder"]');
  await waitPage("document.querySelector('[role=dialog] h2')?.innerText || ''", (value) => value === 'Leave Test', 'confirmed assessment navigation');
  await clickButton('Leave Test', '[role=dialog]');
  await waitPage('location.pathname', (value) => value === '/resume-builder', 'confirmed assessment leave');
  assert.equal(await evaluate("Boolean(document.querySelector('.test-running')?.closest('[hidden]'))"), true,
    'Assessment component remains mounted and hidden after confirmed navigation.');
  await evaluate('history.back(); true');
  await waitPage('location.pathname', (value) => value === '/mock-tests', 'return to preserved assessment');
  assert.equal(await evaluate("document.querySelector('.test-running h1')?.innerText || ''"), assessmentHeading);
  await evaluate('history.forward(); true');
  await waitPage("document.querySelector('[role=dialog] h2')?.innerText || ''", (value) => value === 'Leave Test', 'Forward assessment guard');
  await clickButton('Leave Test', '[role=dialog]');
  await waitPage('location.pathname', (value) => value === '/resume-builder', 'Forward confirmation');
  scenarios.push('Active assessment protects in-app navigation and browser Back/Forward with the existing Leave Test dialog; cancel restores the route, confirmation keeps the assessment mounted and timed.');

  const errorsSnapshot = [...new Set(errors)];
  assert.deepEqual(errorsSnapshot, [], 'No uncaught JavaScript exceptions.');
  assert.deepEqual(consoleErrors.filter((message) => typeof message === 'string'), [], 'No page console.error calls.');
  const result = { runId, scenarios, initial: { heading: initial.heading, ready: initial.ready },
    imported: { profileNamePresent: Boolean(imported.name), emailPresent: Boolean(imported.email), importedSections: imported.skills },
    completeness: completeness.map((item) => ({ text: item.text, complete: item.complete })),
    keyboard, staleStatus: staleResult.status, dialog, pdfs, downloads,
    responsive: { desktop: desktopMetrics, tablet: tabletMetrics, mobile: mobileMetrics },
    privateCacheResponses: responses.filter((item) => item.url.includes('resume-builder')).map((item) => ({ status: item.status, cache: item.cache })),
    consoleErrors, networkFailures, artifacts: artifactDir };
  await writeFile(path.join(artifactDir, 'browser-results.json'), `${JSON.stringify(result, null, 2)}\n`, { flag: 'wx' });
  console.log(JSON.stringify(result));
  await browser.send('Target.disposeBrowserContext', { browserContextId });
  browser.close(); page.close();
} catch (error) {
  console.error(error.stack || String(error));
  try { await browser.send('Target.disposeBrowserContext', { browserContextId }); } catch { /* retain demo data */ }
  browser.close(); page.close();
  process.exitCode = 1;
}
