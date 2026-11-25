// Execute with the installed Playwright browser_run_code filename tool.
// page.__resumeConfig contains only the fresh launcher's origins/run ID/file and
// an evidence path. No credentials or HTTP responses are mocked by this test.
async (page) => {
  const config = page.__resumeConfig;
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  require(config && new URL(config.api).hostname === '127.0.0.1', 'Owned loopback demo required.');
  const health = await page.request.get(config.api + '/health');
  require(health.headers()['x-placepro-demo-run'] === config.runId, 'Wrong demo process.');
  const operation = config.operation || 'repeat';
  async function holdRealResponse(pattern) {
    // Intercept the response after Chromium has sent the original request.
    // route.fetch cannot replay file uploads: CDP omits their binary bodies.
    const cdp = await page.context().newCDPSession(page);
    let heldId;
    let released = false;
    let received;
    const completed = new Promise((resolve) => { received = resolve; });
    cdp.on('Fetch.requestPaused', async (event) => {
      if (event.request.method !== 'POST' || heldId) {
        return cdp.send('Fetch.continueRequest', { requestId: event.requestId });
      }
      heldId = event.requestId;
      received({ status: event.responseStatusCode, method: event.request.method });
    });
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: pattern, requestStage: 'Response' }] });
    return { completed,
      async release() {
        if (released) return;
        released = true;
        if (heldId) await cdp.send('Fetch.continueRequest', { requestId: heldId });
        await cdp.send('Fetch.disable');
        await cdp.detach();
      },
    };
  }
  const read = () => page.evaluate(() => ({
    dialog: Boolean(document.querySelector('[role=dialog][aria-labelledby=resume-modal-title]')),
    controls: ['role', 'company', 'duration', 'technologies'].filter((field) =>
      document.getElementById('evidence-experience.0.' + field)).length,
    events: window.__placeproResumeDiagnostics || [],
  }));
  async function openReview() {
    await page.getByRole('button', { name: 'Update from Resume', exact: true }).click();
    await page.locator('input[type=file]').setInputFiles(config.resume);
    const response = page.waitForResponse((r) => r.url().includes('/resume-preview') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Upload & Extract', exact: true }).click();
    require((await response).status() === 200, 'Real owned extraction failed.');
    await page.getByRole('checkbox', { name: 'Use resume: experience', exact: true }).check();
    require((await read()).controls === 4, 'Experience selection must render all four fields.');
    require(await page.getByRole('dialog').locator('.resume-import-option input:checked').count() === 1,
      'Experience must be the only selected extraction field.');
    const expected = { role: 'Volunteer Developer', company: 'Synthetic Community Workshop',
      duration: 'Jan 2026 - Mar 2026', technologies: 'HTML, CSS' };
    for (const [field, value] of Object.entries(expected)) {
      const control = page.locator('[id="evidence-experience.0.' + field + '"]');
      require(await control.inputValue() === value && await control.isEditable() && await control.isVisible(),
        'Wrong or unavailable extracted editable value: ' + field);
    }
  }
  async function navigateAway() {
    // Exercise the real sidebar event while a modal is open. The overlay blocks
    // pointer access; the existing app permits keyboard sidebar navigation.
    await page.getByRole('link', { name: 'About', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('dialog').waitFor({ state: 'detached' });
  }
  await openReview();
  const start = await read();
  const baseline = start.events.findLast((event) => event.event === 'app.state');
  await page.evaluate(() => {
    window.__resumeOriginalDialog = document.querySelector('[role=dialog][aria-labelledby=resume-modal-title]');
    window.__resumeOriginalRole = document.getElementById('evidence-experience.0.role');
  });

  if (operation === 'pointer') {
    const button = page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true });
    await button.scrollIntoViewIfNeeded();
    const hit = await button.evaluate((node) => {
      const box = node.getBoundingClientRect();
      const top = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return { receivesPointer: node === top || node.contains(top), interceptor: top?.className || '' };
    });
    page.__resumePointerResult = { operation, hit, baseline };
    require(hit.receivesPointer, 'Navbar intercepts the visible resume close button.');
    await button.click();
    require(!(await read()).dialog, 'Pointer close must close the modal.');
    return page.__resumePointerResult;
  }

  if (operation === 'cancel') {
    await page.getByRole('button', { name: 'Upload a Different Resume', exact: true }).click();
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    require(!(await read()).dialog, 'Explicit upload cancellation must close the modal.');
    const close = (await read()).events.findLast((event) => event.event === 'close.request');
    require(close?.reason === 'cancel', 'Cancellation must identify the close callback.');
    return { operation, closed: true, close };
  }

  if (operation === 'confirm') {
    await page.getByRole('checkbox', { name: /I reviewed the selected values/ }).check();
    const response = page.waitForResponse((r) => r.url().endsWith('/api/profile/verify') &&
      r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Confirm & Update My Profile', exact: true }).click();
    require((await response).status() === 200, 'Explicit real confirmation must succeed.');
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    const after = await read();
    const callback = after.events.findLast((event) => event.event === 'confirmation.callback');
    const close = after.events.findLast((event) => event.event === 'close.callback');
    require(callback && close && callback.sequence < close.sequence &&
      close.authStatus === 'authenticated' && close.profileId === baseline.profileId,
    'Only the mounted successful confirmation should close its review.');
    return { operation, intentionallyClosed: true, callback, close };
  }

  if (operation === 'stale-extraction') {
    const held = await holdRealResponse('*/resume-preview');
    try {
    await page.getByRole('button', { name: 'Upload a Different Resume', exact: true }).click();
    await page.getByRole('button', { name: 'Upload & Extract', exact: true }).click();
    const delayed = await held.completed;
    require(delayed.status === 200 && delayed.method === 'POST', 'The delayed real extraction must succeed.');
    await navigateAway();
    await page.getByRole('link', { name: 'Student Profile', exact: true }).click();
    await openReview();
    await page.evaluate(() => { window.__resumeNewDialog = document.querySelector('[role=dialog]'); });
    await held.release();
    await page.waitForFunction((sequence) => window.__placeproResumeDiagnostics.some((event) =>
      event.event === 'extraction.ignored' && event.sequence > sequence), start.events.at(-1).sequence);
    const after = await read();
    require(after.controls === 4 && await page.evaluate(() => window.__resumeNewDialog === document.querySelector('[role=dialog]')),
      'A stale extraction response changed the newer modal.');
    const result = { operation, delayed, newerModalPreserved: true,
      ignored: after.events.findLast((event) => event.event === 'extraction.ignored') };
    page.__resumeAsyncResult = result;
    return result;
    } finally { await held.release(); }
  }

  if (operation === 'logout') {
    const response = page.waitForResponse((r) => r.url().endsWith('/api/auth/logout') && r.request().method() === 'POST');
    await page.locator('.navbar-user-trigger').focus();
    await page.keyboard.press('Enter');
    await page.getByRole('menuitem', { name: 'Logout', exact: true }).focus();
    await page.keyboard.press('Enter');
    require((await response).status() === 204, 'Real UI logout failed.');
    await page.getByRole('button', { name: 'LOGIN', exact: true }).waitFor();
    require(!(await read()).dialog, 'Real logout must remove the private modal.');
    return { operation, loggedOut: true, diagnostics: (await read()).events.slice(-8) };
  }

  if (operation === 'stale-confirmation') {
    const held = await holdRealResponse('*/api/profile/verify');
    try {
    await page.getByRole('checkbox', { name: /I reviewed the selected values/ }).check();
    await page.getByRole('button', { name: 'Confirm & Update My Profile', exact: true }).click();
    const delayed = await held.completed;
    require(delayed.status === 200 && delayed.method === 'POST', 'The delayed real confirmation must succeed.');
    await navigateAway();
    await page.getByRole('link', { name: 'Student Profile', exact: true }).click();
    await page.evaluate(async () => {
      const root = document.getElementById('root');
      const container = root[Object.keys(root).find((key) => key.startsWith('__reactContainer'))];
      let context;
      function visit(fiber) {
        if (!fiber || context) return;
        if (fiber.memoizedProps?.value?.rawProfile && fiber.memoizedProps.value.refetch) context = fiber.memoizedProps.value;
        visit(fiber.child); visit(fiber.sibling);
      }
      visit(container.stateNode.current);
      await context.refetch();
    });
    await openReview();
    await page.evaluate(() => { window.__resumeNewDialog = document.querySelector('[role=dialog]'); });
    await held.release();
    await page.waitForFunction((sequence) => window.__placeproResumeDiagnostics.some((event) =>
      event.event === 'confirmation.ignored' && event.sequence > sequence), start.events.at(-1).sequence);
    const after = await read();
    require(after.controls === 4 && await page.evaluate(() => window.__resumeNewDialog === document.querySelector('[role=dialog]')),
      'A stale confirmation callback closed the newer modal.');
    return { operation, delayed, newerModalPreserved: true,
      ignored: after.events.findLast((event) => event.event === 'confirmation.ignored') };
    } finally { await held.release(); }
  }

  if (operation === 'refresh') {
    const correction = 'Reviewed Synthetic Volunteer';
    await page.locator('[id="evidence-experience.0.role"]').fill(correction);
    // Hold a REAL list response to observe the transient listLoading state.
    // The response is forwarded unchanged. This uses the actual provider's
    // refetch callback, not a substituted controller or authentication context.
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    await page.route('**/api/account/profiles', async (route) => {
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response });
    });
    await page.evaluate(() => {
      const element = document.getElementById('root');
      const container = element[Object.keys(element).find((key) => key.startsWith('__reactContainer'))];
      let context;
      function visit(fiber) {
        if (!fiber || context) return;
        const value = fiber.memoizedProps?.value;
        if (value?.rawProfile && typeof value.refetch === 'function') context = value;
        visit(fiber.child); visit(fiber.sibling);
      }
      visit(container.stateNode.current);
      if (!context) throw new Error('Real profile context not found.');
      window.__resumeRefresh = context.refetch();
    });
    let during;
    try {
      await page.waitForFunction(() => document.getElementById('owned-profile')?.disabled);
      during = await read();
    } finally {
      release();
      await page.evaluate(() => window.__resumeRefresh);
      await page.unroute('**/api/account/profiles');
    }
    const after = await read();
    const sameNodes = await page.evaluate(() => window.__resumeOriginalDialog ===
      document.querySelector('[role=dialog][aria-labelledby=resume-modal-title]') &&
      window.__resumeOriginalRole === document.getElementById('evidence-experience.0.role'));
    const result = { operation, during, after, sameNodes, baseline };
    page.__resumeCaseResult = result;
    require(during.dialog && during.controls === 4 && after.controls === 4 && sameNodes,
      'Successful same-profile refresh removed or reset the active resume review.');
    require(await page.locator('[id="evidence-experience.0.role"]').inputValue() === correction,
      'Successful refresh erased the unsaved correction.');
    require(after.events.findLast((event) => event.event === 'app.state').authStatus === 'authenticated',
      'Same-profile refresh must preserve the valid authenticated workspace.');
    return result;
  }

  const iteration = (page.__resumeRepeats || []).length + 1;
  await page.waitForTimeout(config.idleMs || 15000);
  const idle = await read();
  require(idle.dialog && idle.controls === 4, 'Modal closed during the idle observation.');
  await page.locator('[id="evidence-experience.0.role"]').fill('Reviewed Synthetic Volunteer');
  const edited = await read();
  require(edited.dialog && edited.controls === 4, 'Editing closed the modal.');
  await page.locator('fieldset').filter({ has: page.locator('[id="evidence-experience.0.role"]') })
    .screenshot({ path: config.evidence + '/repetition-' + iteration + '.png' });
  const closeReason = iteration === 3 ? 'escape' : iteration === 4 ? 'backdrop' : 'close-button';
  if (closeReason === 'escape') await page.keyboard.press('Escape');
  else if (closeReason === 'backdrop') {
    const overlay = page.locator('.modal-overlay');
    const box = await overlay.boundingBox();
    await overlay.click({ position: { x: 2, y: box.height - 2 } });
  } else {
    await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).focus();
    await page.keyboard.press('Enter');
  }
  await page.getByRole('dialog').waitFor({ state: 'detached' });
  const closed = await read();
  const close = closed.events.findLast((event) => event.event === 'close.request');
  require(close?.reason === closeReason, 'Close function/event was not captured.');
  require(close.authStatus === 'authenticated' && close.profileId === baseline.profileId,
    'Explicit close should preserve authentication and profile identity.');
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await page.getByRole('link', { name: 'Student Profile', exact: true }).click();
  require(!(await read()).dialog, 'Returning to Profile must not reopen a cancelled review.');
  const session = await page.request.get(config.api + '/api/auth/session');
  require(session.status() === 200, 'Session must remain valid after explicit close/navigation.');
  const result = { iteration, idleMs: config.idleMs || 15000, idleRemainedOpen: true,
    editRemainedOpen: true, closeReason, profileUnchanged: true, sessionStatus: session.status(),
    diagnostics: closed.events.filter((event) => event.sequence > (start.events.at(-1)?.sequence || 0)),
    closeEvent: close };
  page.__resumeRepeats ||= [];
  page.__resumeRepeats.push(result);
  return result;
}
