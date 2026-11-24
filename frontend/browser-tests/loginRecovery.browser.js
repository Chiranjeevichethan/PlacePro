// Execute with an installed Playwright page function against disposable secured test storage.
// Set page.__placeproLogin to { url, api, expectedApi, runId, email, password } in memory.
async (page) => {
  const config = page.__placeproLogin;
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  check(config?.url && config.api && config.expectedApi && config.email && config.password
    && /^[a-f0-9]{32}$/.test(config.runId || ''), 'Missing disposable login-test configuration.');
  for (const value of [config.url, config.api, config.expectedApi]) {
    const url = new URL(value);
    check(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname), 'Require loopback HTTP test origins.');
  }
  const health = await page.request.get(config.api + '/health');
  check(health.headers()['x-placepro-test-run-id'] === config.runId, 'Refuse a backend outside this owned test run.');
  check((await page.context().cookies()).length === 0, 'Require a fresh, isolated browser context.');
  const scenarios = [];
  config.scenarios = scenarios;
  const emailKey = 'placepro_login_email:v1';
  const sessionPath = /\/api\/auth\/session$/;
  const waitForLogin = async () => {
    await page.locator('#login-username').waitFor();
  };
  const request = async (url, method = 'GET', body, token) => page.evaluate(async (input) => {
    const options = { method: input.method, credentials: 'include', cache: 'no-store' };
    if (input.body !== undefined) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(input.body);
    }
    if (input.token) options.headers = { ...options.headers, 'X-CSRF-Token': input.token };
    const response = await fetch(input.url, options);
    return { status: response.status, data: response.status === 204 ? null : await response.json() };
  }, { url, method, body, token });
  const passwordIsAbsent = async () => page.evaluate((passwords) =>
    [sessionStorage, localStorage].every((storage) => Object.keys(storage)
      .every((key) => passwords.every((password) => !storage.getItem(key)?.includes(password)))),
  [config.password, 'Incorrect browser fixture password']);
  let other;
  let retainedContext;
  let release;
  let handler;

  try {
    await page.goto(config.url);
    await waitForLogin();
    const actualApi = await page.evaluate(async () => (await import('/src/services/apiTransport.js')).API_BASE_URL);
    check(actualApi === config.expectedApi, 'The browser API origin must use the page hostname in HTTP loopback development.');
    await page.locator('#login-username').fill(config.email);
    await page.locator('#login-password').fill('Incorrect browser fixture password');
    check(await page.evaluate((key) => sessionStorage.getItem(key), emailKey) === config.email, 'Persist the email immediately on input.');
    check(await passwordIsAbsent(), 'Typing must not persist a password.');
    await page.evaluate(() => {
      window.__loginRecovery = { email: document.querySelector('#login-username'),
        password: document.querySelector('#login-password'), timeOrigin: performance.timeOrigin };
    });
    other = await page.context().newPage();
    await other.goto('about:blank');
    await other.bringToFront();
    await page.bringToFront();
    check(await page.locator('#login-username').inputValue() === config.email, 'Tab activation must retain the email.');
    scenarios.push('Browser tab activation retains the email.');

    // Deliberately deliver focus because browser automation can suppress native window focus.
    // Hold the real request before forwarding it; no response or security proof is substituted.
    let received;
    const observedRequest = new Promise((resolve) => { received = resolve; });
    const gate = new Promise((resolve) => { release = resolve; });
    handler = async (route) => { received(); await gate; await route.continue(); };
    await page.route(sessionPath, handler);
    const anonymousResponse = page.waitForResponse((response) => sessionPath.test(response.url()));
    await page.evaluate(() => {
      document.dispatchEvent(new Event('visibilitychange'));
      window.dispatchEvent(new Event('blur'));
      window.dispatchEvent(new Event('focus'));
    });
    await Promise.race([observedRequest, anonymousResponse]);
    check(await page.evaluate(() => document.querySelector('#login-username') === window.__loginRecovery.email
      && document.querySelector('#login-password') === window.__loginRecovery.password
      && performance.timeOrigin === window.__loginRecovery.timeOrigin), 'Background validation must preserve the document and input nodes.');
    release();
    check((await anonymousResponse).status() === 401, 'Anonymous focus checks must still be rejected by the real API.');
    await page.unroute(sessionPath, handler);
    handler = null;
    check(await page.locator('#login-username').inputValue() === config.email, 'Focus restoration retains the email.');
    check(await page.locator('#login-password').inputValue() === 'Incorrect browser fixture password', 'The mounted form keeps only its in-memory password.');
    scenarios.push('Controlled focus/blur/visibility events preserve Login during and after a real anonymous 401.');

    const beforeReload = await page.evaluate(() => performance.timeOrigin);
    await page.reload();
    await waitForLogin();
    check(await page.evaluate(() => performance.timeOrigin) !== beforeReload, 'The reload test must replace the document.');
    check(await page.locator('#login-username').inputValue() === config.email, 'A document reload restores the email draft.');
    check(await page.locator('#login-password').inputValue() === '', 'A document reload must restore no password.');
    check(await passwordIsAbsent(), 'No password belongs in browser storage after reload.');
    scenarios.push('A full document reload restores email and clears the password.');

    await page.locator('#login-password').fill('Incorrect browser fixture password');
    let remountRequest;
    const observedRemount = new Promise((resolve) => { remountRequest = resolve; });
    const remountGate = new Promise((resolve) => { release = resolve; });
    handler = async (route) => { remountRequest(); await remountGate; await route.continue(); };
    await page.route(sessionPath, handler);
    const remountResponse = page.waitForResponse((response) => sessionPath.test(response.url()));
    await page.evaluate(async () => {
      window.__loginRecovery = { email: document.querySelector('#login-username'), timeOrigin: performance.timeOrigin };
      // Use the exact module URL loaded by App, including Vite's HMR timestamp.
      const loaded = performance.getEntriesByType('resource')
        .find((entry) => new URL(entry.name).pathname === '/src/services/auth.js');
      if (!loaded) throw new Error('The actual App authentication module was not observed.');
      const { authSession } = await import(loaded.name);
      authSession.restore();
    });
    await Promise.race([observedRemount, remountResponse]);
    await page.locator('#login-username').waitFor({ state: 'detached' });
    release();
    check((await remountResponse).status() === 401, 'The foreground restore still receives a real anonymous denial.');
    await page.unroute(sessionPath, handler);
    handler = null;
    await waitForLogin();
    check(await page.evaluate(() => document.querySelector('#login-username') !== window.__loginRecovery.email
      && !window.__loginRecovery.email.isConnected && performance.timeOrigin === window.__loginRecovery.timeOrigin),
    'The foreground-restoration test must cause a real component remount within the same document.');
    check(await page.locator('#login-username').inputValue() === config.email, 'A component remount restores the email.');
    check(await page.locator('#login-password').inputValue() === '', 'A component remount must restore no password.');
    scenarios.push('A forced real Login remount restores email and clears the password.');

    await page.locator('#login-password').fill('Incorrect browser fixture password');
    const [invalidResponse] = await Promise.all([
      page.waitForResponse((response) => response.url().endsWith('/api/auth/login') && response.request().method() === 'POST'),
      page.locator('.login-button').click(),
    ]);
    check(invalidResponse.status() === 401, 'Invalid credentials must receive a real 401.');
    await page.locator('.login-error').waitFor();
    check(await page.locator('#login-username').inputValue() === config.email, 'Invalid credentials preserve email.');
    check(await passwordIsAbsent(), 'A rejected login must not persist a password.');
    scenarios.push('Invalid credentials are rejected and preserve the email draft.');

    const noToken = await request(actualApi + '/api/auth/login', 'POST', { email: config.email, password: 'Incorrect browser fixture password' });
    check(noToken.status === 403, 'A login cookie without a CSRF token must remain denied.');
    const crossApi = new URL(actualApi);
    crossApi.hostname = crossApi.hostname === 'localhost' ? '127.0.0.1' : 'localhost';
    const crossChallenge = await request(crossApi.origin + '/api/auth/login-challenge');
    check(crossChallenge.status === 200 && /^[a-f0-9]{64}$/.test(crossChallenge.data?.csrf_token), 'The cross-site challenge still returns its bootstrap token.');
    const crossLogin = await request(crossApi.origin + '/api/auth/login', 'POST',
      { email: config.email, password: 'Incorrect browser fixture password' }, crossChallenge.data.csrf_token);
    check(crossLogin.status === 403, 'The original cross-site cookie boundary must remain enforced.');
    scenarios.push('Missing CSRF and explicit cross-site challenge cookies remain denied.');

    await page.locator('#login-password').fill(config.password);
    const [successResponse] = await Promise.all([
      page.waitForResponse((response) => response.url().endsWith('/api/auth/login') && response.request().method() === 'POST'),
      page.locator('.login-button').click(),
    ]);
    check(successResponse.status() === 200, 'Valid credentials and challenge must establish a real session.');
    await page.locator('.navbar-user-trigger').waitFor();
    check(await page.evaluate((key) => sessionStorage.getItem(key), emailKey) === null, 'Successful login clears the email draft.');
    check(await passwordIsAbsent(), 'Successful login must not persist a password.');
    const cookies = await page.context().cookies();
    const retained = cookies.find((cookie) => cookie.name === 'placepro_dev_session');
    check(retained?.domain === new URL(actualApi).hostname && retained.path === '/'
      && retained.httpOnly && retained.sameSite === 'Lax' && !retained.secure, 'Retain the existing development cookie policy.');
    check(!cookies.some((cookie) => cookie.name === 'placepro_dev_login'), 'Successful login consumes and clears its challenge cookie.');
    scenarios.push('Valid login establishes the unchanged HttpOnly Lax session and clears the email draft.');

    await page.reload();
    await page.locator('.navbar-user-trigger').waitFor();
    const restored = await request(actualApi + '/api/auth/session');
    check(restored.status === 200 && restored.data.account.email === config.email, 'A refreshed authenticated document restores the real session.');
    const csrf = await request(actualApi + '/api/auth/csrf');
    check(csrf.status === 200 && /^[a-f0-9]{64}$/.test(csrf.data?.csrf_token), 'The authenticated CSRF endpoint must issue a session-bound token.');
    const afterRestore = await page.evaluate(() => performance.timeOrigin);
    const [backgroundResponse] = await Promise.all([
      page.waitForResponse((response) => sessionPath.test(response.url())),
      page.evaluate(() => window.dispatchEvent(new Event('focus'))),
    ]);
    check(backgroundResponse.status() === 200, 'Authenticated focus restoration must succeed.');
    check(await page.evaluate(() => performance.timeOrigin) === afterRestore, 'Authenticated focus must not reload the document.');
    scenarios.push('Session/CSRF acquisition and authenticated background restoration succeed after refresh.');

    await page.locator('.navbar-user-trigger').click();
    const [logoutResponse] = await Promise.all([
      page.waitForResponse((response) => response.url().endsWith('/api/auth/logout')),
      page.getByRole('button', { name: 'Logout', exact: true }).click(),
    ]);
    check(logoutResponse.status() === 204, 'Real UI logout must revoke the session with CSRF protection.');
    await waitForLogin();
    check(await page.locator('#login-username').inputValue() === '', 'Logout after successful login has no old email draft.');
    check(await page.locator('#login-password').inputValue() === '', 'Logout restores no password.');
    retainedContext = await page.context().browser().newContext();
    await retainedContext.addCookies([retained]);
    check((await retainedContext.request.get(actualApi + '/api/auth/session')).status() === 401, 'A retained revoked session cookie must be denied.');
    await retainedContext.close();
    retainedContext = null;
    scenarios.push('CSRF-protected UI logout clears the form and retained revoked cookies stay denied.');

    await page.locator('#login-username').fill('separate-tab@example.test');
    await other.goto(config.url);
    await other.locator('#login-username').waitFor();
    check(await other.locator('#login-username').inputValue() === '', 'Email drafts are isolated to the current tab.');
    check(await page.locator('#login-username').inputValue() === 'separate-tab@example.test', 'Opening another login tab preserves this tab email.');
    scenarios.push('Email drafts remain isolated between independent tabs.');
    return { origin: config.url, api: actualApi, scenarios, passwordPersisted: false,
      cookie: { name: retained.name, domain: retained.domain, path: retained.path,
        httpOnly: retained.httpOnly, sameSite: retained.sameSite, secure: retained.secure } };
  } finally {
    release?.();
    if (handler) await page.unroute(sessionPath, handler);
    if (retainedContext) await retainedContext.close();
    if (other) await other.close();
  }
};
