"""Provision the documented local development student account.

Run from the project root after installing the pinned backend dependencies:

    PLACEPRO_SECURITY_MODE=development \
    PLACEPRO_DEV_STUDENT_EMAIL=student@placepro.com \
    python scripts/seed_dev_student.py --password

Enter and confirm your chosen password at the hidden prompts. Alternatively,
provide PLACEPRO_DEV_STUDENT_PASSWORD privately in the environment.
Production mode is refused, duplicates are prevented and an existing account's
password is never silently replaced. The password is never printed, logged or
returned.
"""
import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.account_service import AccountService  # noqa: E402
from backend.app.services.account_store import AccountStore  # noqa: E402
from backend.app.services.dev_account import (  # noqa: E402
    DEFAULT_DEVELOPMENT_EMAIL,
    DevelopmentAccountError,
    provision_development_student,
)
from backend.app.services.security_config import SecurityConfig  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', default=DEFAULT_DEVELOPMENT_EMAIL,
                        help='Local development student email (not a secret).')
    parser.add_argument('--password', action='store_true',
                        help='Prompt for the password with hidden input.')
    args = parser.parse_args(argv)
    config = SecurityConfig.from_environment()
    if config.mode != 'development':
        print('Refused: set PLACEPRO_SECURITY_MODE=development before provisioning.', file=sys.stderr)
        return 1
    import os
    os.environ.setdefault('PLACEPRO_DEV_STUDENT_EMAIL', args.email)
    if args.password or not os.environ.get('PLACEPRO_DEV_STUDENT_PASSWORD'):
        if not sys.stdin.isatty():
            print('Refused: set PLACEPRO_DEV_STUDENT_PASSWORD or run interactively.', file=sys.stderr)
            return 1
        entered = getpass.getpass('Local development password (15-128 characters, hidden): ')
        if entered != getpass.getpass('Confirm password: '):
            print('Refused: passwords do not match.', file=sys.stderr)
            return 1
        os.environ['PLACEPRO_DEV_STUDENT_PASSWORD'] = entered
    try:
        result = provision_development_student(AccountService(AccountStore()), config)
    except DevelopmentAccountError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 1
    if result is None:
        print('Nothing to provision: PLACEPRO_DEV_STUDENT_PASSWORD was not provided.', file=sys.stderr)
        return 1
    state = 'created' if result['created'] else 'already exists'
    print(f"Local development student account {result['email']} is ACTIVE ({state}; "
          f"origin {result['origin']}). The password was not displayed or stored in plaintext.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
