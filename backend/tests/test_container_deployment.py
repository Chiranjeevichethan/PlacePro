"""Production launch policy without starting a server or touching databases."""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend import container_start
from backend.app.main import create_app
from backend.app.services.security_config import SecurityConfig


@pytest.fixture
def production_environment(monkeypatch):
    monkeypatch.setenv('PLACEPRO_SECURITY_MODE', 'production')
    monkeypatch.setenv('PLACEPRO_ALLOWED_ORIGINS', 'https://app.example.test')
    monkeypatch.setenv('FORWARDED_ALLOW_IPS', '10.42.0.7,10.43.0.0/24,::1')
    for name in ('PORT', 'PLACEPRO_DEV_STUDENT_EMAIL', 'PLACEPRO_DEV_STUDENT_PASSWORD',
                 'PLACEPRO_SESSION_IDLE_SECONDS', 'PLACEPRO_SESSION_ABSOLUTE_SECONDS'):
        monkeypatch.delenv(name, raising=False)


def test_host_port_single_worker_and_private_logging(production_environment, monkeypatch):
    monkeypatch.setenv('PORT', '9123')
    monkeypatch.setenv('WEB_CONCURRENCY', '8')
    command = container_start.production_command()
    assert command[:5] == [sys.executable, '-B', '-m', 'uvicorn', 'backend.app.main:app']
    assert command[command.index('--port') + 1] == '9123'
    assert command[command.index('--workers') + 1] == '1'
    assert command[command.index('--forwarded-allow-ips') + 1] == '10.42.0.7,10.43.0.0/24,::1'
    assert '--proxy-headers' in command and '--no-access-log' in command
    assert '--reload' not in command and '--env-file' not in command


def test_default_port_and_default_production_mode(production_environment, monkeypatch):
    monkeypatch.delenv('PLACEPRO_SECURITY_MODE')
    command = container_start.production_command()
    assert command[command.index('--port') + 1] == '8000'


@pytest.mark.parametrize('port', ['', '0', '65536', '-1', '+8000', '8000.0', 'abc', '８０００'])
def test_invalid_host_ports_fail_before_server_start(production_environment, monkeypatch, port):
    monkeypatch.setenv('PORT', port)
    with pytest.raises(ValueError, match='PORT'):
        container_start.production_command()


@pytest.mark.parametrize('proxies', ['', '*', '0.0.0.0/0', '::/0', 'proxy.example.test',
                                    '10.0.0.1,', '10.0.0.1/99'])
def test_missing_or_unbounded_proxy_trust_is_rejected(production_environment, monkeypatch, proxies):
    monkeypatch.setenv('FORWARDED_ALLOW_IPS', proxies)
    with pytest.raises(ValueError, match='FORWARDED_ALLOW_IPS'):
        container_start.production_command()


@pytest.mark.parametrize('origins', ['', '*', 'http://app.example.test', 'https://app.example.test/'])
def test_production_requires_explicit_https_origins(production_environment, monkeypatch, origins):
    monkeypatch.setenv('PLACEPRO_ALLOWED_ORIGINS', origins)
    with pytest.raises(ValueError):
        container_start.production_command()


def test_development_mode_cannot_be_launched_publicly(production_environment, monkeypatch):
    monkeypatch.setenv('PLACEPRO_SECURITY_MODE', 'development')
    monkeypatch.setenv('PLACEPRO_ALLOWED_ORIGINS', 'http://127.0.0.1:5173')
    with pytest.raises(ValueError, match='production security mode'):
        container_start.production_command()


@pytest.mark.parametrize('name', ['PLACEPRO_DEV_STUDENT_EMAIL', 'PLACEPRO_DEV_STUDENT_PASSWORD'])
def test_development_credentials_refuse_start_without_logging_values(production_environment, monkeypatch, capsys, name):
    synthetic_value = 'synthetic-value-never-print'
    monkeypatch.setenv(name, synthetic_value)
    monkeypatch.setattr(os, 'execv', lambda *_: pytest.fail('Server must not start'))
    assert container_start.main() == 1
    error = capsys.readouterr().err
    assert 'Development account environment variables' in error
    assert synthetic_value not in error


def test_launcher_replaces_itself_and_sets_private_file_creation_mode(production_environment, monkeypatch):
    calls = []
    monkeypatch.setattr(os, 'umask', lambda mode: calls.append(('umask', mode)))
    monkeypatch.setattr(os, 'execv', lambda executable, command: calls.append(('exec', executable, command)))
    container_start.main()
    assert calls[0] == ('umask', 0o077)
    assert calls[1][0:2] == ('exec', sys.executable)
    assert calls[1][2] == container_start.production_command()


@pytest.mark.parametrize('client_ip,forwarded_scheme,status', [
    ('10.42.0.7', 'https', 200),
    ('198.51.100.7', 'https', 403),
    ('10.42.0.7', 'http', 403),
])
def test_https_requires_a_trusted_proxy_without_bypassing_security(
    isolated_storage, client_ip, forwarded_scheme, status,
):
    origin = 'https://app.example.test'
    application = create_app(SecurityConfig(origins=(origin,)))
    proxied = ProxyHeadersMiddleware(application, trusted_hosts='10.42.0.7')
    with TestClient(proxied, base_url='http://api.example.test', client=(client_ip, 9123)) as client:
        response = client.get('/api/auth/login-challenge', headers={
            'Origin': origin, 'X-Forwarded-Proto': forwarded_scheme,
        })
    assert response.status_code == status
