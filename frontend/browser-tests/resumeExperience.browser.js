// Real-browser regression, executed by Playwright's browser_run_code tool.
// Set page.__placeproDemo to { url, api, runId, resume, password } first.
// Use a NEW isolated context and only a fresh scripts/demo.py workspace.
// Credentials stay in memory; no HTTP responses or authentication are mocked.
async (page) => {
  const config = page.__placeproDemo;
  if (!config || !/^[a-f0-9]{32}$/.test(config.runId)) throw new Error('An owned synthetic demo is required.');
  for (const target of [config.url, config.api]) {
    const url = new URL(target);
    if (url.hostname !== '127.0.0.1' || url.protocol !== 'http:') throw new Error('Loopback demo required.');
  }
  const health = await page.request.get(config.api + '/health');
  if (health.headers()['x-placepro-demo-run'] !== config.runId) throw new Error('Demo identity mismatch.');
  if ((await page.context().cookies()).length) throw new Error('A fresh browser context is required.');
  const checks = [];
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  const expected = { role: 'Volunteer Developer', company: 'Synthetic Community Workshop',
    duration: 'Jan 2026 - Mar 2026', technologies: 'HTML, CSS' };
  const requests = [];
  const pending = [];
  let stage = 'initial session restoration';
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  const extra = new Map();
  const metadata = (event) => ({ cookiePresent: Boolean(event.headers.Cookie || event.headers.cookie),
    sessionCookiePresent: /placepro_dev_session=/.test(event.headers.Cookie || event.headers.cookie || ''),
    cookies: event.associatedCookies.map(({ cookie, blockedReasons }) => ({ name: cookie.name,
      domain: cookie.domain, path: cookie.path, httpOnly: cookie.httpOnly, sameSite: cookie.sameSite, blockedReasons })) });
  cdp.on('Network.requestWillBeSentExtraInfo', (event) => {
    const record = requests.find((r) => r.requestId === event.requestId);
    if (record) Object.assign(record, metadata(event));
    else extra.set(event.requestId, metadata(event));
  });
  cdp.on('Network.requestWillBeSent', (event) => {
    if (!event.request.url.endsWith('/api/auth/session')) return;
    requests.push({ requestId: event.requestId, stage, url: event.request.url,
      method: event.request.method, initiator: event.initiator, ...extra.get(event.requestId) });
    extra.delete(event.requestId);
  });
  page.on('response', (response) => {
    if (!response.url().endsWith('/api/auth/session')) return;
    const record = requests.findLast((r) => r.status === undefined);
    if (record) {
      record.status = response.status();
      pending.push(response.json().then((body) => { record.body = body; }));
    }
  });
  await page.addInitScript(() => {
    const names = new Map();
    let previous = [];
    window.__resumeLifecycle = { events: [], commits: [] };
    function kind(fiber) {
      const props = fiber.memoizedProps || {};
      if ('preservedProfile' in props && 'resumeDraft' in props) return 'ResumeUploadModal';
      if ('profile' in props && 'onChange' in props && 'disabled' in props) return 'ResumeEvidenceEditor';
      if ('resumeOpen' in props && 'onRequestResume' in props) return 'StudentProfile';
      if ('accountId' in props && 'children' in props) return 'StudentProfileProvider';
      return names.get(fiber.type);
    }
    // Diagnostic hook only. It observes committed fibers; it never changes props/state.
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {
      supportsFiber: true, inject: () => 1,
      onCommitFiberRoot(_id, root) {
        const current = [], state = {};
        function visit(fiber) {
          if (!fiber) return;
          if (typeof fiber.type === 'function') {
            const hooks = [];
            for (let hook = fiber.memoizedState; hook; hook = hook.next) hooks.push(hook.memoizedState);
            const session = hooks.find((value) => value && typeof value.status === 'string' && 'epoch' in value && 'account' in value);
            if (session && hooks[0] === session && hooks.length === 3 && Object.keys(fiber.memoizedProps || {}).length === 0) {
              names.set(fiber.type, 'SessionApp'); state.session = session;
            }
            const name = kind(fiber);
            if (name) {
              names.set(fiber.type, name); current.push({ name, fiber });
              if (name === 'ResumeUploadModal') {
                const modal = hooks.find((value) => value && typeof value.step === 'string');
                state.modal = { step: modal?.step, experience: modal?.draft?.experience,
                  selectedFields: hooks.find(Array.isArray), corrections: hooks[6],
                  mounted: hooks.find((value) => value?.current === true)?.current === true };
              }
              if (name === 'ResumeEvidenceEditor') state.editorExperience = fiber.memoizedProps.profile.experience;
            }
          }
          visit(fiber.child); visit(fiber.sibling);
        }
        visit(root.current);
        for (const item of current) if (!previous.some((old) => old.fiber === item.fiber || old.fiber === item.fiber.alternate)) {
          window.__resumeLifecycle.events.push({ event: 'mount', name: item.name });
        }
        for (const item of previous) if (!current.some((next) => next.fiber === item.fiber || next.fiber.alternate === item.fiber)) {
          window.__resumeLifecycle.events.push({ event: 'unmount', name: item.name });
        }
        previous = current;
        window.__resumeLifecycle.commits.push(state);
      },
      onCommitFiberUnmount() {},
    };
  });
  const sessionResponse = () => page.waitForResponse((r) => r.url().endsWith('/api/auth/session'));
  let response = sessionResponse();
  await page.goto(config.url);
  require((await response).status() === 401, 'Fresh anonymous restoration must be denied.');
  await page.getByRole('button', { name: 'LOGIN', exact: true }).waitFor();
  stage = 'anonymous focus handler: deliberately dispatched test event';
  response = sessionResponse();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  require((await response).status() === 401, 'Anonymous focus restoration must be denied.');
  require(await page.getByRole('dialog').count() === 0, 'An anonymous user must have no editor.');
  checks.push('Two independent anonymous restorations are denied without a misleading editor.');

  await page.getByRole('textbox', { name: 'Email', exact: true }).fill('demo-student-a@example.test');
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(config.password);
  await page.getByRole('button', { name: 'LOGIN', exact: true }).click();
  await page.getByRole('link', { name: 'Student Profile', exact: true }).click();
  await page.getByRole('button', { name: 'Update from Resume', exact: true }).click();
  await page.locator('input[type=file]').setInputFiles(config.resume);
  const previewResponse = page.waitForResponse((r) => r.url().includes('/resume-preview') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Upload & Extract', exact: true }).click();
  const preview = await previewResponse;
  require(preview.status() === 200, 'Owned authenticated extraction must succeed.');
  const extracted = (await preview.json()).profile;
  const path = '/api/profile/' + extracted.profile_id;
  const original = (await (await page.request.get(config.api + path)).json()).profile;
  require(extracted.experience[0].role === expected.role && extracted.experience[0].company === expected.company,
    'The parser must return the synthetic experience.');
  const checkbox = page.getByRole('checkbox', { name: 'Use resume: experience', exact: true });
  await checkbox.check();
  async function values(expectedValues) {
    return page.evaluate((expectedValues) => Object.entries(expectedValues).map(([key, expected]) => {
      const node = document.getElementById('evidence-experience.0.' + key);
      if (!node || node.value !== expected || node.disabled || !node.getClientRects().length) {
        throw new Error('Missing, hidden, disabled or wrong editable value: ' + key);
      }
      return { id: node.id, name: node.name, label: node.labels[0]?.textContent, value: node.value,
        reactValue: node[Object.keys(node).find((key) => key.startsWith('__reactProps'))]?.value };
    }), expectedValues);
  }
  const controls = await values(expected);
  const selection = await page.getByRole('dialog').locator('.resume-import-option input:checked').count();
  require(selection === 1, 'Only Experience must be selected.');
  const selectedState = await page.evaluate(() => window.__resumeLifecycle.commits.at(-1));
  require(selectedState.session.status === 'authenticated' && selectedState.modal.selectedFields.join() === 'experience',
    'The mounted review must receive the selected experience.');
  require(selectedState.editorExperience[0].role === expected.role, 'Extracted experience must reach editor props.');
  await page.screenshot({ path: config.screenshot, fullPage: true });
  checks.push('Real parser -> preview -> Experience-only selection -> four visible controlled inputs.');

  const corrected = Object.fromEntries(Object.entries(expected).map(([key, value]) => [key, value + ' reviewed']));
  for (const [key, value] of Object.entries(corrected)) {
    await page.locator('[id="evidence-experience.0.' + key + '"]').fill(value);
  }
  await values(corrected);
  require(await page.getByRole('button', { name: 'Confirm & Update My Profile', exact: true }).isDisabled(),
    'Corrections must require explicit acknowledgement.');
  checks.push('Every field is editable, corrections survive rerenders, and confirmation remains required.');
  await checkbox.uncheck();
  // Earlier confirmation scenarios can leave legitimate stored experience.
  // Deselection restores that captured profile, which need not be empty.
  await page.waitForFunction((experience) => {
    if (JSON.stringify(window.__resumeLifecycle.commits.at(-1)?.editorExperience) !== JSON.stringify(experience)) return false;
    if (document.querySelectorAll('[id^="evidence-experience."][id$=".role"]').length !== experience.length) return false;
    return experience.every((record, index) => ['role', 'company', 'duration', 'technologies'].every((field) => {
      const control = document.getElementById('evidence-experience.' + index + '.' + field);
      const stored = record[field];
      const expected = Array.isArray(stored) ? stored.join(', ') : stored ?? '';
      return control?.value === expected;
    }));
  }, original.experience || []);
  await checkbox.check();
  await values(expected);
  const unchanged = (await (await page.request.get(config.api + path)).json()).profile;
  require(JSON.stringify(unchanged) === JSON.stringify(original), 'Unconfirmed review must not alter the profile.');
  checks.push('Deselect/reselect restores extraction; unrelated stored fields and revision remain unchanged.');

  await page.evaluate(() => {
    window.__dialogBeforeRestore = document.querySelector('[role=dialog]');
    window.__roleBeforeRestore = document.getElementById('evidence-experience.0.role');
  });
  stage = 'authenticated focus handler: deliberately dispatched test event';
  response = sessionResponse();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  require((await response).status() === 200, 'Normal authenticated restoration must succeed.');
  await values(expected);
  require(await page.evaluate(() => window.__dialogBeforeRestore === document.querySelector('[role=dialog]') &&
    window.__roleBeforeRestore === document.getElementById('evidence-experience.0.role')), 'Restoration must preserve the mounted editor.');
  checks.push('Valid background restoration preserves the modal, input nodes and selected data.');
  const beforeDenial = await page.evaluate(() => window.__resumeLifecycle.events);
  require(!beforeDenial.some((event) => event.event === 'unmount' &&
    ['ResumeUploadModal', 'ResumeEvidenceEditor', 'StudentProfile', 'StudentProfileProvider'].includes(event.name)),
  'Normal authenticated review must not unmount private components.');

  // A second isolated consumer logs out the real session. The first browser
  // retains its cookie, exercising server revocation rather than deleting it.
  const other = await page.context().browser().newContext();
  try {
    await other.addCookies(await page.context().cookies());
    const csrfResponse = await other.request.get(config.api + '/api/auth/csrf', { headers: { Origin: config.url } });
    const token = (await csrfResponse.json()).csrf_token;
    const logout = await other.request.post(config.api + '/api/auth/logout',
      { headers: { Origin: config.url, 'X-CSRF-Token': token } });
    require(logout.status() === 204, 'Real CSRF-protected logout must succeed.');
    stage = 'focus restoration with retained, server-revoked session cookie';
    response = sessionResponse();
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    require((await response).status() === 401, 'A revoked cookie must be rejected.');
    await page.getByText('Your session has expired. Sign in again.', { exact: true }).waitFor();
    require(await page.getByRole('dialog').count() === 0, 'Authentication failure must unmount the review.');
    require(await page.locator('[id="evidence-experience.0.role"]').count() === 0, 'A stale blank editor must not remain.');
    const denied = await page.request.get(config.api + path);
    require(denied.status() === 401, 'Revoked sessions must not access owned profiles.');
    checks.push('Real session revocation shows sign-in notice, clears authentication and unmounts private components.');
  } finally { await other.close(); }
  await Promise.all(pending);
  const lifecycle = await page.evaluate(() => window.__resumeLifecycle);
  for (const name of ['ResumeUploadModal', 'ResumeEvidenceEditor', 'StudentProfile', 'StudentProfileProvider']) {
    require(lifecycle.events.some((event) => event.name === name && event.event === 'mount'), name + ' mount missing.');
    require(lifecycle.events.some((event) => event.name === name && event.event === 'unmount'), name + ' unmount missing.');
  }
  require(requests.at(-1).sessionCookiePresent, 'Revoked-session request must carry the retained cookie.');
  require(requests.slice(0, 2).every((r) => !r.cookiePresent), 'Anonymous denials must have no cookie.');
  page.__placeproResult = { checks, controls, selectedState, requests, lifecycle,
    note: 'Focus events were deliberately dispatched by this regression. They are not evidence about the operator\'s original two 401s.' };
  return page.__placeproResult;
}
