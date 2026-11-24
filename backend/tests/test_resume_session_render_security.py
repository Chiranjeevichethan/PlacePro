"""Denied real sessions must never disclose extraction or access owned profiles."""
import pytest

from backend.tests.test_profile_ownership import pair, encoded_password, create, identity
from backend.tests.test_resume_profile_update import preview, snapshot
from backend.app.services import profile_service


@pytest.mark.parametrize('failure', ['idle_expired', 'absolute_expired', 'revoked'])
def test_resume_review_denied_session_is_rejected_before_parser_and_preserves_profiles(
    pair, isolated_storage, monkeypatch, failure,
):
    app, client, _, headers, _ = pair
    profile = create(client, headers)
    session = identity(app, client)
    if failure == 'revoked':
        app.state.sessions.revoke_account(session.account_id)
    else:
        boundary = session.idle_expires_at if failure == 'idle_expired' else session.absolute_expires_at
        monkeypatch.setattr(app.state.sessions, 'clock', lambda: boundary)
    before = snapshot(isolated_storage)
    monkeypatch.setattr(profile_service, 'prepare_draft_with_analysis',
                        lambda *args, **kwargs: pytest.fail('Denied session reached resume parsing'))
    response = preview(client, headers, profile)
    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication is required.'}
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get('/api/profile/' + profile['profile_id']).status_code == 401
    assert snapshot(isolated_storage) == before
