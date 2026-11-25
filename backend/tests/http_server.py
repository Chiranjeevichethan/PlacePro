"""Test-only ASGI wrapper identifying the process owned by the pytest fixture."""

import os
from pathlib import Path

from backend.tests.domain_app import app as application
from backend.app.services import assessment_service, company_store, profile_service
from backend.tests.support import PROJECT_ROOT


_storage_root = Path(os.environ["PLACEPRO_TEST_STORAGE_ROOT"]).resolve()
_run_id = os.environ["PLACEPRO_TEST_RUN_ID"].encode("ascii")
for _path in (
    profile_service.PROFILES_DIR,
    assessment_service.ASSESSMENTS_DIR,
    company_store.DB_PATH,
    os.environ["PLACEPRO_AUTH_DB"],
    os.environ["PLACEPRO_GOALS_DB"],
    os.environ["PLACEPRO_RESUME_BUILDER_DB"],
):
    _resolved = Path(_path).resolve()
    if (
        not _resolved.is_relative_to(_storage_root)
        or _resolved.is_relative_to(PROJECT_ROOT / "data")
    ):
        raise RuntimeError(f"Refusing non-isolated test-server storage: {_resolved}")


async def app(scope, receive, send):
    async def send_with_identity(message):
        if message["type"] == "http.response.start":
            message = dict(message)
            message["headers"] = list(message.get("headers", [])) + [
                (b"x-placepro-test-run-id", _run_id),
                (b"x-placepro-test-process-id", str(os.getpid()).encode("ascii")),
            ]
        await send(message)

    await application(scope, receive, send_with_identity)
