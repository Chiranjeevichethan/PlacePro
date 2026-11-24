"""Local synthetic demonstration. Never reuse storage or relax application security."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EMAILS = ('demo-student-a@example.test', 'demo-student-b@example.test', 'demo-empty@example.test')

# Self-contained fictional fixture: never load a student's resume or test fixture.
# No real phone number, social account, home address or contactable domain.
SYNTHETIC_RESUME_LINES = (
    'Synthetic Demo Learner',
    'synthetic-resume@example.test',
    'SYNTHETIC DEMONSTRATION DATA - every person and organisation is fictional',
    'EDUCATION',
    'B.Tech Computer Science and Engineering',
    'Synthetic Demonstration College | Graduation: 2027 | CGPA: 8.2',
    'SKILLS',
    'Python, JavaScript, SQL',
    'React.js, NodeJS, Spring Boot',
    'PostgreSQL, SQLite',
    'Docker, AWS',
    'Machine Learning, pandas, NumPy',
    'HTML, CSS, REST API',
    'Git, VS Code',
    'Teamwork, Problem Solving',
    'PROJECTS',
    'Synthetic Library Planner - Fictional book-loan tracking practice application',
    'Technologies: Python, FastAPI, SQLite',
    '- Built a loan tracker using entirely fictional library records.',
    '- Added input validation and search.',
    'Synthetic Study Board',
    '- Built a fictional study planner for practice.',
    'Technologies: React.js, NodeJS, PostgreSQL',
    'INTERNSHIPS',
    'Software Intern at Synthetic Practice Lab | Jun 2025 - Aug 2025',
    '- Built practice endpoints using Python and FastAPI.',
    'EXPERIENCE',
    'Volunteer Developer at Synthetic Community Workshop | Jan 2026 - Mar 2026',
    '- Maintained a fictional website using HTML and CSS.',
    'CERTIFICATIONS',
    'Synthetic Python Practice Certificate | Synthetic Learning Academy | 2025',
    'REFERENCES',
    'No real student information is included.',
)


def new_workspace(parent=None):
    parent = Path(parent or tempfile.gettempdir()).resolve()
    if parent.is_relative_to(ROOT):
        raise ValueError('Demo storage must be outside historical student storage.')
    root = Path(tempfile.mkdtemp(prefix='placepro_demo_', dir=parent)).resolve()
    (root / 'profiles').mkdir()
    (root / 'assessments').mkdir()
    marker = {'kind': 'placepro-isolated-synthetic-demo', 'run_id': uuid.uuid4().hex,
              'created_at': datetime.now(timezone.utc).isoformat()}
    with (root / 'demo-workspace.json').open('x', encoding='utf-8') as output:
        json.dump(marker, output)
    return root


def checked_workspace(root):
    raw = Path(root)
    root = raw.resolve()
    if raw.is_symlink() or raw.is_junction() or not root.name.startswith('placepro_demo_') or root.is_relative_to(ROOT):
        raise ValueError('Refusing non-demo storage.')
    marker_path = root / 'demo-workspace.json'
    if marker_path.is_symlink():
        raise ValueError('Refusing linked demo storage.')
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if (not isinstance(marker, dict) or marker.get('kind') != 'placepro-isolated-synthetic-demo'
            or not isinstance(marker.get('run_id'), str) or not re.fullmatch('[a-f0-9]{32}', marker['run_id'])):
        raise ValueError('Invalid demo workspace marker.')
    for name in ('profiles', 'assessments', 'accounts.sqlite3', 'companies.db'):
        path = root / name
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root):
            raise ValueError('Refusing linked demo storage.')
    return root, marker


def seed_accounts(root, password):
    """Provision only newly created fixture accounts, never activate existing users."""
    root, _ = checked_workspace(root)
    path = root / 'accounts.sqlite3'
    if path.exists():
        raise ValueError('Demo provisioning requires a new authentication database.')
    from backend.app.services.account_service import AccountService
    from backend.app.services.account_store import AccountStore
    from backend.app.services.account_validation import validate_password
    validate_password(password)
    with path.open('xb'):
        pass  # Exclusively reserve this new database before SQLite initializes it.
    service = AccountService(AccountStore(path))
    for email in EMAILS:
        service.register(email, password)
    with sqlite3.connect(path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        rows = connection.execute('SELECT email_normalized,status FROM accounts').fetchall()
        if set(rows) != {(email, 'PENDING_EMAIL') for email in EMAILS}:
            raise ValueError('Unexpected synthetic account state; refusing activation.')
        now = datetime.now(timezone.utc).isoformat()
        connection.executemany("UPDATE accounts SET status='ACTIVE',email_verified_at=?,updated_at=? WHERE email_normalized=? AND status='PENDING_EMAIL'",
                               [(now, now, email) for email in EMAILS])
    # This fixture is not email verification. No web activation endpoint is added.


def synthetic_profile(account, number):
    return {
        'personal': {'name': f'Synthetic {account.upper()} — Profile {number}', 'email': f'synthetic-{account}-{number}@example.test'},
        'education': {'degree': 'B.Tech', 'college': 'Synthetic Demonstration College', 'branch': 'CSE', 'cgpa': 8.2 if number == 1 else 6.8, 'graduation_year': 2027},
        'skills': {'programming_languages': ['Python', 'Java'], 'databases': ['SQL'], 'web_technologies': ['HTML', 'CSS']},
        'projects': [{'project_name': 'Synthetic Campus Portal', 'technologies': ['Python', 'SQL']}],
        'internships': [{'company': 'Synthetic Engineering Lab', 'role': 'Practice developer'}],
        'certifications': [], 'achievements': {'hackathons': []},
        'ml_inputs': {'college_tier': 'Tier-3', 'backlogs': 0, 'coding_skills': 7 if number == 1 else 5,
                      'dsa_score': 7 if number == 1 else 4, 'aptitude_score': 75, 'communication_skills': 7,
                      'ml_knowledge': 5, 'system_design': 4, 'open_source_contributions': 0, 'extracurriculars': 1},
    }


def request(opener, base, path, method='GET', body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        response = opener.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        return response.status, json.loads(content) if content else None


def seed_profiles(base, origin, password):
    references = {}
    for label, email in zip(('a', 'b', 'empty'), EMAILS):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        headers = {'Origin': origin}
        code, challenge = request(opener, base, '/api/auth/login-challenge', headers=headers)
        if code != 200:
            raise RuntimeError('Demo login challenge failed.')
        code, _ = request(opener, base, '/api/auth/login', 'POST', {'email': email, 'password': password},
                          headers | {'X-CSRF-Token': challenge['csrf_token']})
        if code != 200:
            raise RuntimeError('Demo credential verification failed.')
        code, token = request(opener, base, '/api/auth/csrf', headers=headers)
        if code != 200:
            raise RuntimeError('Demo session security check failed.')
        secured = headers | {'X-CSRF-Token': token['csrf_token']}
        references[label] = []
        for number in range(1, 3) if label != 'empty' else ():
            code, result = request(opener, base, '/api/profile/verify', 'POST', synthetic_profile(label, number),
                                   secured | {'Idempotency-Key': f'demo-create-{number}'})
            if code != 200:
                raise RuntimeError('Owned synthetic profile creation failed.')
            profile_id = result['profile']['profile_id']
            references[label].append(profile_id)
            if number == 1:
                code, _ = request(opener, base, '/api/profile/' + profile_id + '/predict', 'POST',
                                  headers=secured | {'Idempotency-Key': 'demo-initial-prediction'})
                if code != 200:
                    raise RuntimeError('Synthetic model calculation failed.')
        code, _ = request(opener, base, '/api/auth/logout', 'POST', headers=secured)
        if code != 204:
            raise RuntimeError('Synthetic provisioning session logout failed.')
    return references


def create_resume(root):
    root, _ = checked_workspace(root)
    from docx import Document
    document = Document()
    document.core_properties.author = 'PlacePro Synthetic Demo'
    document.core_properties.last_modified_by = 'PlacePro Synthetic Demo'
    document.core_properties.title = 'PlacePro Fictional Resume'
    document.core_properties.subject = 'Entirely fictional demonstration data'
    for text in SYNTHETIC_RESUME_LINES:
        document.add_paragraph(text)
    path = root / 'Synthetic-Resume.docx'
    if path.exists():
        raise ValueError('Refusing to replace an existing resume.')
    with path.open('xb') as output:
        document.save(output)
    return path


def free_port(port):
    with socket.socket() as probe:
        if sys.platform == 'win32':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(('127.0.0.1', port))


@contextmanager
def launch_frontend(root, api_port, frontend_port):
    """Owned loopback development server; never produce a loopback production build."""
    root, marker = checked_workspace(root)
    free_port(frontend_port)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('VITE_', 'PLACEPRO_', 'GOOGLE_'))}
    env.update(NODE_ENV='development', VITE_API_BASE_URL=f'http://127.0.0.1:{api_port}',
               VITE_DEMO_MODE='synthetic')
    process = None
    with (root / 'frontend.log').open('x', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(['node', str(ROOT / 'scripts' / 'demo_frontend.mjs'),
                                        str(ROOT / 'frontend'), str(root / 'vite-cache'),
                                        str(frontend_port), marker['run_id']],
                                       cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                       text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            deadline = time.monotonic() + 30
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Demo frontend exited before startup; inspect its isolated log.')
                try:
                    with opener.open(f'http://127.0.0.1:{frontend_port}/', timeout=1) as response:
                        if response.headers.get('X-PlacePro-Demo-Run') != marker['run_id']:
                            raise RuntimeError('Frontend port belongs to another process; refusing to reuse it.')
                        break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Demo frontend startup timed out.')
            yield process
        finally:
            if process is not None:
                if process.poll() is None:
                    process.stdin.write('stop\n')
                    process.stdin.flush()
                process.wait(timeout=15)
                process.stdin.close()
                if process.returncode != 0:
                    raise RuntimeError('Demo frontend shutdown failed; inspect its isolated log.')


@contextmanager
def launch_api(root, port, frontend_port):
    root, marker = checked_workspace(root)
    free_port(port)
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    process = None
    with (root / 'server.log').open('x', encoding='utf-8') as log:
        try:
            process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--serve', str(root),
                                        '--api-port', str(port), '--frontend-port', str(frontend_port)],
                                       cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=log, stderr=log, text=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            deadline = time.monotonic() + 30
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Demo backend exited before startup; inspect the isolated server log.')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                        if response.headers.get('X-PlacePro-Demo-Run') != marker['run_id']:
                            raise RuntimeError('Port is served by another process; refusing to reuse it.')
                        break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Demo backend startup timed out.')
            yield process
        finally:
            if process is not None:
                if process.poll() is None:
                    process.stdin.write('stop\n')
                    process.stdin.flush()
                process.wait(timeout=15)  # Do not enumerate or terminate unrelated processes.
                process.stdin.close()
                if process.returncode != 0:
                    raise RuntimeError('Demo server shutdown failed; inspect its isolated log.')


def serve_api(root, port, frontend_port):
    root, marker = checked_workspace(root)
    os.environ.update(PLACEPRO_PROFILES_DIR=str(root / 'profiles'), PLACEPRO_ASSESSMENTS_DIR=str(root / 'assessments'),
                      PLACEPRO_AUTH_DB=str(root / 'accounts.sqlite3'), PLACEPRO_COMPANIES_DB=str(root / 'companies.db'),
                      PLACEPRO_SECURITY_MODE='development', PLACEPRO_ALLOWED_ORIGINS=f'http://127.0.0.1:{frontend_port}')
    from backend.app.main import app as secured_application
    import uvicorn
    async def app(scope, receive, send):
        async def identify(message):
            if message['type'] == 'http.response.start':
                message = dict(message)
                message['headers'] = list(message.get('headers', [])) + [(b'x-placepro-demo-run', marker['run_id'].encode())]
            await send(message)
        await secured_application(scope, receive, identify)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False, access_log=False))
    def stop():
        if sys.stdin.readline().strip() == 'stop':
            server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()


def main():
    parser = argparse.ArgumentParser(description='Loopback-only synthetic PlacePro demonstration; never uses historical storage.')
    parser.add_argument('--api-port', type=int, default=8765)
    parser.add_argument('--frontend-port', type=int, default=5173)
    parser.add_argument('--serve', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.api_port <= 65535 or not 1 <= args.frontend_port <= 65535 or args.api_port == args.frontend_port:
        parser.error('Choose two different valid loopback ports.')
    if args.serve:
        serve_api(args.serve, args.api_port, args.frontend_port)
        return
    free_port(args.api_port)
    free_port(args.frontend_port)
    if not sys.stdin.isatty():
        raise ValueError('Start the demo in an interactive terminal so password input stays hidden.')
    print('SYNTHETIC LOCAL DEMO. No real student data or production activation. Close with Ctrl+C.')
    password = getpass.getpass('Choose a demo password (15–128 characters; input hidden): ')
    if password != getpass.getpass('Confirm demo password: '):
        raise ValueError('Demo passwords do not match.')
    root = new_workspace()
    print('Isolated records/cache/logs retained at:', root)
    seed_accounts(root, password)
    create_resume(root)
    with launch_api(root, args.api_port, args.frontend_port):
        references = seed_profiles(f'http://127.0.0.1:{args.api_port}', f'http://127.0.0.1:{args.frontend_port}', password)
        password = None  # Never serialize or print the password.
        with (root / 'profile-references.json').open('x', encoding='utf-8') as output:
            json.dump(references, output)
        with launch_frontend(root, args.api_port, args.frontend_port):
            print('Open:', f'http://127.0.0.1:{args.frontend_port}')
            print('Synthetic student logins:', ', '.join(EMAILS), '(use your chosen password)')
            print('Resume onboarding file:', root / 'Synthetic-Resume.docx')
            print('Registration remains unavailable. Demo outcomes are model calculations on synthetic inputs.')
            try:
                while True:
                    time.sleep(.5)
            except KeyboardInterrupt:
                pass
    print('Owned demo servers stopped. Records retained; nothing deleted.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f'Demo stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
