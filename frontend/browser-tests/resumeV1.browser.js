async (page) => {
  // Run only with a fresh isolated fixture. No credentials belong in this config.
  const config = page.__resumeV1Config;
  if (!config?.frontend || !config.api || !config.appApi || !config.resume) throw new Error('Missing isolated resume/V1 fixture config.');
  const context = await page.context().browser().newContext();
  const check = await context.newPage();
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const paths = [], errors = [];
  check.on('pageerror', error => errors.push(error.message));
  await context.route('**/api/**', async route => {
    const target = new URL(route.request().url());
    assert(target.origin === config.appApi, 'Unexpected frontend API destination.');
    target.host = new URL(config.api).host;
    await route.continue({ url: target.href });
  });
  check.on('response', response => {
    if (new URL(response.url()).pathname.startsWith('/api/')) {
      assert(response.headers()['x-placepro-isolated-check'] === 'placepro-isolated-security-check', 'Unisolated API response.');
      paths.push({ path: new URL(response.url()).pathname, status: response.status() });
    }
  });
  const generated = await check.evaluate(() => {
    const random = () => Array.from(crypto.getRandomValues(new Uint8Array(24)), value => value.toString(16).padStart(2, '0')).join('');
    return { email: 'resume-v1-' + random().slice(0, 20) + '@example.test', password: random() };
  });
  const secured = async () => {
    const response = await context.request.get(config.api + '/api/auth/csrf', { headers: { Origin: config.frontend } });
    assert(response.status() === 200, 'Real CSRF acquisition failed.');
    return { Origin: config.frontend, 'X-CSRF-Token': (await response.json()).csrf_token };
  };
  const body = profile => Object.fromEntries(['profile_id', 'revision', 'personal', 'education', 'skills',
    'projects', 'internships', 'experience', 'certifications', 'achievements', 'ml_inputs', 'additional_info']
    .filter(key => profile[key] !== undefined).map(key => [key, profile[key]]));
  const getProfile = async id => {
    const response = await context.request.get(config.api + '/api/profile/' + id, { headers: { Origin: config.frontend } });
    assert(response.status() === 200, 'Saved profile load failed.');
    return (await response.json()).profile;
  };
  const describeForm = () => check.locator('.student-form').evaluate(form => ({
    sections: [...form.querySelectorAll('.form-section-card')].map(section => ({
      heading: section.querySelector('h3').textContent,
      kicker: section.querySelector('.form-section-header p').textContent,
      columns: getComputedStyle(section.querySelector('.form-grid')).gridTemplateColumns,
      gap: getComputedStyle(section.querySelector('.form-grid')).gap,
    })),
    controls: [...form.querySelectorAll('[name]')].map(control => ({
      name: control.name, label: form.querySelector('label[for="' + control.id + '"]').textContent,
      type: control.type, min: control.getAttribute('min'), max: control.getAttribute('max'),
      step: control.getAttribute('step'), placeholder: control.getAttribute('placeholder'),
      options: control.options ? [...control.options].map(option => ({ value: option.value, label: option.textContent })) : null,
      width: getComputedStyle(control).width, height: getComputedStyle(control).height,
      padding: getComputedStyle(control).padding, border: getComputedStyle(control).border,
      radius: getComputedStyle(control).borderRadius,
    })),
  }));
  const validationCases = [
    ['cgpa', '3.9', 'CGPA must be between 4 and 10.'],
    ['codingSkill', '0', 'Coding Skill must be between 1 and 10.'],
    ['dsaScore', '11', 'DSA Score must be between 1 and 10.'],
    ['mlKnowledge', '-1', 'ML Knowledge must be between 0 and 10.'],
    ['systemDesign', '11', 'System Design must be between 0 and 10.'],
    ['aptitudeScore', '19', 'Aptitude Score must be between 20 and 100.'],
    ['communicationSkill', '0', 'Communication Skill must be between 1 and 10.'],
    ['projects', '1.5', 'Projects must be a whole number.'],
    ['openSourceContributions', '-1', 'Open Source Contributions must be at least 0.'],
    ['extracurricular', '', 'Extracurricular Activities is required.'],
  ];
  const checkValidation = async () => {
    for (const [field, invalid, message] of validationCases) {
      const input = check.locator('.student-form [name="' + field + '"]');
      const original = await input.inputValue();
      const callsBefore = paths.filter(item => ['/api/predict', '/api/experimental/v1/predict'].includes(item.path)).length;
      await input.fill(invalid);
      await check.getByRole('button', { name: 'PREDICT PLACEMENT', exact: true }).click();
      assert(await check.getByText(message, { exact: true }).isVisible(), 'Reference validation mismatch for ' + field);
      assert(paths.filter(item => ['/api/predict', '/api/experimental/v1/predict'].includes(item.path)).length === callsBefore, 'Invalid form requested inference.');
      await input.fill(original);
    }
  };
  try {
    const health = await context.request.get(config.api + '/health');
    assert(health.headers()['x-placepro-isolated-check'] === 'placepro-isolated-security-check', 'Refusing non-fixture backend.');
    const setup = await context.request.post(config.api + '/__test/bootstrap', { headers: { Origin: config.frontend }, data: generated });
    assert(setup.status() === 200, 'Isolated account creation failed.');
    await check.goto(config.frontend);
    await check.locator('#login-username').fill(generated.email);
    await check.locator('#login-password').fill(generated.password);
    await check.getByRole('button', { name: 'LOGIN', exact: true }).click();
    await check.locator('.sidebar-menu').waitFor();
    const initial = { personal: { name: 'Previous Student', email: generated.email },
      education: { branch: 'CSE', cgpa: 7.4 }, skills: { programming_languages: ['Java'] },
      projects: [{ project_name: 'Previous project', technologies: ['Java'] }], internships: [], experience: [],
      certifications: [], achievements: { hackathons: ['Previous event'] },
      ml_inputs: { college_tier: 'Tier-2', backlogs: 0, coding_skills: 8, dsa_score: 7, aptitude_score: 81,
        communication_skills: 7, ml_knowledge: 6, system_design: 5, open_source_contributions: 0, extracurriculars: 2 },
      additional_info: { age: 24, gender: 'Female', attendance: 90, github_repositories: 6, linkedin_connections: 100,
        logical_reasoning: 70, mock_interview: 65, leadership: 55, volunteer_experience: 'Yes', sleep_hours: 7.5, study_hours: 4 } };
    const created = await context.request.post(config.api + '/api/profile/verify', { headers: await secured(), data: initial });
    assert(created.status() === 200, 'Owned fixture profile creation failed.');
    const savedId = (await created.json()).profile.profile_id;
    await check.reload();
    await check.getByRole('link', { name: 'Student Profile', exact: true }).click();
    await check.getByRole('button', { name: 'Update from Resume', exact: true }).click();
    const dialog = check.getByRole('dialog');
    await dialog.locator('input[type=file]').setInputFiles(config.resume);
    const extraction = check.waitForResponse(response => response.url().includes('/resume-preview') && response.status() === 200);
    await dialog.getByRole('button', { name: 'Upload & Extract', exact: true }).click();
    const extracted = (await extraction).json();
    const all = dialog.getByRole('checkbox', { name: 'Select all', exact: true });
    const confirmed = dialog.getByRole('checkbox', { name: /I reviewed the selected values/ });
    const submit = dialog.getByRole('button', { name: 'Confirm & Update My Profile', exact: true });
    await all.waitFor();
    assert(!await all.isChecked() && !await confirmed.isChecked(), 'Review controls were automatically checked.');
    assert(await submit.isDisabled(), 'Confirmation button initially enabled.');
    assert((await dialog.locator('summary').textContent()).includes('(0 selected)'), 'Initial count incorrect.');
    await all.check();
    const count = await dialog.locator('.resume-import-option input:checked').count();
    assert(count > 0 && (await dialog.locator('summary').textContent()).includes('(' + count + ' selected)'), 'Select All count incorrect.');
    assert(await all.evaluate(element => !element.indeterminate), 'All selection remained indeterminate.');
    const name = dialog.getByRole('checkbox', { name: 'Use resume: personal name', exact: true });
    await name.uncheck();
    assert(await all.evaluate(element => element.indeterminate) && await all.getAttribute('aria-checked') === 'mixed', 'Partial selection missing mixed state.');
    assert((await dialog.locator('summary').textContent()).includes('(' + (count - 1) + ' selected)'), 'Partial count incorrect.');
    await all.check();
    await all.uncheck();
    assert(await dialog.locator('.resume-import-option input:checked').count() === 0, 'Deselect All retained fields.');
    assert(await dialog.locator('#review-cgpa').inputValue() === '7.4', 'Unchecked value did not retain current profile.');
    await all.check();
    await name.uncheck();
    await dialog.locator('#review-cgpa').fill('9.2');
    assert(await submit.isDisabled(), 'Correction bypassed final confirmation.');
    const geometry = await confirmed.evaluate(element => ({ width: element.getBoundingClientRect().width,
      color: getComputedStyle(element.parentElement).color, weight: getComputedStyle(element.parentElement).fontWeight }));
    assert(geometry.width >= 24 && Number(geometry.weight) >= 600, 'Confirmation lacks visual emphasis.');
    await confirmed.focus(); await confirmed.press('Space');
    assert(await confirmed.isChecked() && await submit.isEnabled(), 'Keyboard acknowledgement did not enable confirmation.');
    assert(await confirmed.evaluate(element => element.matches(':focus-visible')), 'Confirmation lacks keyboard focus state.');
    await dialog.locator('#review-cgpa').fill('9.3');
    assert(!await confirmed.isChecked() && await submit.isDisabled(), 'Changing correction did not reset acknowledgement.');
    await confirmed.check();
    const updated = check.waitForResponse(response => new URL(response.url()).pathname === '/api/profile/verify' && response.status() === 200);
    await submit.click(); await updated; await dialog.waitFor({ state: 'hidden' });
    const saved = await getProfile(savedId);
    assert(saved.personal.name === 'Previous Student' && saved.education.cgpa === 9.3, 'Unchecked identity/corrected CGPA were not preserved.');
    const parsed = (await extracted).profile;
    assert(saved.projects.length === parsed.projects.length && saved.projects.length > 0, 'Selected projects were not persisted.');
    await check.getByRole('link', { name: 'Experimental V1 Model', exact: true }).click();
    const v1 = field => check.locator('.experimental-v1-form [name="' + field + '"]');
    await check.waitForFunction(() => document.querySelector('[name=cgpa]')?.value === '9.3');
    assert(await v1('projects').inputValue() === String(saved.projects.length), 'V1 omitted saved project count.');
    assert(await v1('branch').inputValue() === 'CE', 'V1 branch normalization failed.');
    assert(await v1('codingSkill').inputValue() === '8' && await v1('aptitudeScore').inputValue() === '81', 'Saved production-scale scores not prefilled.');
    assert(await v1('communicationSkill').inputValue() === '7' && await v1('extracurricular').inputValue() === '2', 'Saved production-scale values changed.');
    await v1('cgpa').fill('9.5'); await v1('projects').fill('99'); await v1('aptitudeScore').fill('');
    const newer = body(saved);
    newer.education = { ...newer.education, cgpa: 7.9 };
    newer.projects = [1, 2, 3].map(number => ({ project_name: 'Latest project ' + number }));
    newer.ml_inputs = { ...newer.ml_inputs, coding_skills: 9, aptitude_score: 72 };
    const newerResponse = await context.request.post(config.api + '/api/profile/verify', { headers: await secured(), data: newer });
    assert(newerResponse.status() === 200, 'Latest saved revision failed.');
    await check.evaluate(() => window.dispatchEvent(new Event('focus')));
    await check.waitForFunction(() => document.querySelector('[name=codingSkill]')?.value === '9');
    assert(await v1('cgpa').inputValue() === '9.5' && await v1('projects').inputValue() === '99', 'Profile refresh overwrote manual edits.');
    assert(await v1('aptitudeScore').inputValue() === '', 'Profile refresh overwrote a deliberate blank.');
    await check.getByRole('link', { name: 'Student Profile', exact: true }).click();
    await check.getByRole('link', { name: 'Experimental V1 Model', exact: true }).click();
    await check.waitForFunction(() => document.querySelector('[name=cgpa]')?.value === '7.9');
    assert(await v1('projects').inputValue() === '3', 'Navigation reused stale saved profile.');
    await check.reload();
    await check.waitForFunction(() => document.querySelector('[name=cgpa]')?.value === '7.9');
    assert(await v1('codingSkill').inputValue() === '9', 'Reload did not use latest persisted profile.');
    await check.getByRole('link', { name: 'Placement Prediction', exact: true }).click();
    await check.locator('.student-form').waitFor();
    assert(await check.locator('.student-form [name]').count() === 16, 'Production form contract changed.');
    await checkValidation();
    const productionResponse = check.waitForResponse(response => new URL(response.url()).pathname === '/api/predict' && response.status() === 200);
    await check.getByRole('button', { name: 'PREDICT PLACEMENT', exact: true }).click();
    const production = await productionResponse;
    assert(Object.keys(production.request().postDataJSON()).length === 16, 'Production payload changed.');
    await check.getByText('placepro-final-v1', { exact: true }).waitFor();
    await check.getByRole('link', { name: 'Experimental V1 Model', exact: true }).click();
    assert(await check.locator('.experimental-v1-form [name]').count() === 16, 'V1 form did not retain exactly 16 controls.');
    await checkValidation();
    for (const width of [1280, 900, 390]) {
      await check.setViewportSize({ width, height: 900 });
      await check.getByRole('link', { name: 'Placement Prediction', exact: true }).click();
      const reference = await describeForm();
      await check.getByRole('link', { name: 'Experimental V1 Model', exact: true }).click();
      const experimental = await describeForm();
      const differences = [];
      for (const group of ['sections', 'controls']) reference[group].forEach((item, index) => {
        for (const key of Object.keys(item)) if (JSON.stringify(item[key]) !== JSON.stringify(experimental[group][index][key])) {
          differences.push({ group, index, key, reference: item[key], experimental: experimental[group][index][key] });
        }
      });
      assert(differences.length === 0, 'Form differences at width ' + width + ': ' + JSON.stringify(differences));
    }
    await check.setViewportSize({ width: 1280, height: 900 });
    const v1Response = check.waitForResponse(response => new URL(response.url()).pathname === '/api/experimental/v1/predict' && response.status() === 200);
    await check.getByRole('button', { name: 'PREDICT PLACEMENT', exact: true }).click();
    assert(Object.keys((await v1Response).request().postDataJSON()).length === 16, 'V1 payload contract changed.');
    await check.getByText('placepro-experimental-v1-16-inputs', { exact: true }).waitFor();
    await v1('codingSkill').fill('8.5');
    assert(await check.getByRole('heading', { name: 'Experimental V1 Result' }).count() === 0, 'Editing retained stale prediction.');
    assert(errors.length === 0, JSON.stringify(errors));
    return { passed: true, eligibleSelectedFields: count, finalProfileRevision: (await getProfile(savedId)).revision,
      selectedResumeSaved: true, confirmationKeyboardAndButton: true, v1LatestPrefill: true,
      manualEditsAndBlanksPreserved: true, navigationAndReload: true, productionAndV1Contracts: true,
      identicalFieldsOptionsAndGeometry: [1280, 900, 390], matchingValidationCases: validationCases.length,
      realSecuredAPI: true, isolatedStorage: true, pageErrors: errors.length, paths };
  } finally {
    generated.password = ''; generated.email = '';
    await context.close();
  }
}
