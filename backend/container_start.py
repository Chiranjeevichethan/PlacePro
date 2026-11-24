"""Production container launcher; application contracts/security stay unchanged."""
import ipaddress
import os
import sys

from backend.app.services.security_config import SecurityConfig


def production_command():
    config = SecurityConfig.from_environment()
    if config.mode != 'production' or not config.origins:
        raise ValueError('Set production security mode and explicit HTTPS PLACEPRO_ALLOWED_ORIGINS.')
    if any(os.environ.get(name) for name in (
        'PLACEPRO_DEV_STUDENT_EMAIL', 'PLACEPRO_DEV_STUDENT_PASSWORD',
    )):
        raise ValueError('Development account environment variables must be absent in production.')

    port = os.environ.get('PORT', '8000')
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError('PORT must be an integer between 1 and 65535.')

    proxies = os.environ.get('FORWARDED_ALLOW_IPS', '').strip()
    try:
        networks = [ipaddress.ip_network(value.strip(), strict=False) for value in proxies.split(',')]
    except ValueError:
        raise ValueError('Set FORWARDED_ALLOW_IPS to explicit trusted proxy IPs or CIDRs; wildcard trust is forbidden.') from None
    if any(network.prefixlen == 0 for network in networks):
        raise ValueError('FORWARDED_ALLOW_IPS must not trust the entire Internet.')

    return [sys.executable, '-B', '-m', 'uvicorn', 'backend.app.main:app',
            '--host', '0.0.0.0', '--port', port, '--workers', '1',
            '--loop', 'asyncio', '--http', 'h11', '--proxy-headers',
            '--forwarded-allow-ips', proxies, '--no-access-log', '--no-server-header']


def main():
    try:
        command = production_command()
    except ValueError as error:
        print(f'Production startup refused: {error}', file=sys.stderr)
        return 1
    # Private database, JSON and temporary records must not be world-readable.
    os.umask(0o077)
    # Replace the launcher so the container sends SIGTERM directly to Uvicorn.
    os.execv(sys.executable, command)


if __name__ == '__main__':
    raise SystemExit(main())
