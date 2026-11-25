"""Own first, then use existing domain locks, revision rules and protected fields."""
import hashlib
import json
import os
from pathlib import Path
import uuid
from pydantic import ValidationError

from ..schemas_profile import StudentProfile
from . import profile_service as profiles
from .ownership_store import OwnershipNotFound,OwnershipConflict
from .retry_integrity import fingerprint,request_identity,creation_id


class OwnedProfileService:
    def __init__(self,store):
        self.store=store

    def authorize(self,identity,profile_id):
        return self.store.authorize(identity,profile_id)

    def list_owned(self,identity):
        # Only references; never scan student JSON or expose foreign/unowned IDs.
        rows=self.store.list_owned(identity)
        return {'profiles':[{'profile_id':r['profile_id']} for r in rows
                            if Path(profiles._profile_path(r['profile_id'])).is_file()]}

    def _existing(self,profile_id):
        try:
            profile,completion=profiles.get_profile(profile_id)
            checked=StudentProfile.model_validate(profile)
            if checked.profile_id!=profile_id or checked.revision is None or checked.revision<1:
                raise OwnershipNotFound()
            return profile,completion
        except (profiles.ProfileNotFoundError,ValidationError,ValueError,TypeError,AttributeError,KeyError):
            raise OwnershipNotFound() from None

    def _require_file(self,profile_id):
        path=Path(profiles._profile_path(profile_id))
        if not path.is_file() or path.is_symlink():
            raise OwnershipNotFound()

    def get(self,identity,profile_id):
        self.authorize(identity,profile_id)  # No lock artifacts for denied targets.
        self._require_file(profile_id)
        with profiles.profile_transaction(profile_id):
            self.store.authorize(identity,profile_id,acceptance=True)
            self._require_file(profile_id)
            return self._existing(profile_id)

    def update(self,identity,profile_id,submitted, *, confirming=False,request_id=None):
        self.authorize(identity,profile_id)
        self._require_file(profile_id)
        if submitted.get('revision') is None:
            raise profiles.InvalidProfileError('A reviewed profile revision is required.')
        with profiles.profile_transaction(profile_id):
            self.store.authorize(identity,profile_id,acceptance=True)
            self._require_file(profile_id)
            existing,completion=self._existing(profile_id)  # Never fall back to creation.
            operation='confirm' if confirming else 'update'
            key=request_identity(identity,operation,profile_id,request_id) if request_id is not None else None
            digest=fingerprint(submitted) if key else None
            receipts=existing.get('_request_receipts',{})
            if not isinstance(receipts,dict):
                raise profiles.ProfilePersistenceError('Profile request integrity is unavailable.')
            if key in receipts:
                receipt=receipts[key]
                if (not isinstance(receipt,dict) or receipt.get('payload')!=digest
                        or receipt.get('account_id')!=identity.account_id
                        or receipt.get('revision')!=existing['revision']
                        or receipt.get('ownership_version')!=self.authorize(identity,profile_id)['association_version']):
                    raise profiles.ProfileConflictError('This request cannot be replayed. Reload and review the profile.')
                return existing,completion
            if confirming:
                result,completion=profiles.verify_profile({**submitted,'profile_id':profile_id})
            else:
                result,completion=profiles.update_profile(profile_id,submitted)
            if key:
                association=self.authorize(identity,profile_id)
                result['_request_receipts']={**receipts,key:{'payload':digest,'account_id':identity.account_id,
                    'revision':result['revision'],'ownership_version':association['association_version']}}
                profiles._save(result)  # Metadata does not advance the domain revision.
            return result,completion

    def _publish(self,identity,profile,completion):
        profile['revision']=1
        # Validate/serialize completely before reserving metadata or writing any JSON.
        StudentProfile.model_validate(profile)
        encoded=json.dumps(profile,indent=2,ensure_ascii=True,allow_nan=False).encode('utf-8')
        expected=hashlib.sha256(encoded).hexdigest()
        profile_id=profile['profile_id']
        if os.path.lexists(profiles._profile_path(profile_id)):
            raise OwnershipConflict()
        self.store.reserve(identity,profile_id,expected)
        with profiles.profile_transaction(profile_id):
            # Recheck session after reservation and before file creation.
            with self.store.transaction() as connection:
                self.store.sessions.validate_identity(connection,identity)
            profiles.persist_new_profile(profile,encoded)
            # Hold the cooperating profile lock through durable verification/activation.
            data=Path(profiles._profile_path(profile_id)).read_bytes()
            saved=StudentProfile.model_validate_json(data)
            if saved.profile_id!=profile_id or saved.revision!=1 or hashlib.sha256(data).hexdigest()!=expected:
                raise OwnershipConflict()
            self.store.activate(identity,profile_id,expected)
        return profile,completion

    def _create(self,identity,operation,payload,key,prepare):
        with self.store.sessions.store.transaction() as connection:
            self.store.sessions.validate_identity(connection,identity)
        if key is None:
            profile,completion,analysis=prepare(str(uuid.uuid4()))
            profile,completion=self._publish(identity,profile,completion)
            return profile,completion,analysis
        profile_id=creation_id(identity,operation,key)
        digest=fingerprint(payload)
        token=request_identity(identity,operation,None,key)
        with profiles.profile_transaction(profile_id):
            if os.path.lexists(profiles._profile_path(profile_id)):
                try:
                    association=self.authorize(identity,profile_id)
                    self._require_file(profile_id)
                    existing,completion=self._existing(profile_id)
                except OwnershipNotFound:
                    raise OwnershipConflict() from None
                receipt=existing.get('_creation_receipt')
                if (not isinstance(receipt,dict) or receipt.get('key')!=token or receipt.get('payload')!=digest
                        or receipt.get('account_id')!=identity.account_id or existing['revision']!=1
                        or receipt.get('ownership_version')!=association['association_version']):
                    raise OwnershipConflict()
                return existing,completion,receipt.get('analysis')
            with self.store.transaction() as connection:
                if connection is not None and connection.execute('SELECT 1 FROM profile_ownership WHERE profile_id=?',(profile_id,)).fetchone():
                    raise OwnershipConflict()  # Pending/failed reservations never re-extract or republish.
            profile,completion,analysis=prepare(profile_id)
            profile['_creation_receipt']={'key':token,'payload':digest,'account_id':identity.account_id,
                                         'ownership_version':2,'analysis':analysis}
            profile,completion=self._publish(identity,profile,completion)
            return profile,completion,analysis

    def create_confirmed(self,identity,submitted,request_id=None):
        if submitted.get('profile_id') is not None:
            raise OwnershipNotFound()
        def prepare(profile_id):
            profile,completion=profiles.prepare_confirmed_profile(submitted,profile_id)
            return profile,completion,None
        profile,completion,_=self._create(identity,'create-confirmed',submitted,request_id,prepare)
        return profile,completion

    def create_resume(self,identity,filename,content,content_type=None,request_id=None):
        payload=[filename,content_type,hashlib.sha256(content).hexdigest()]
        return self._create(identity,'create-resume',payload,request_id,
            lambda profile_id: profiles.prepare_draft_with_analysis(filename,content,content_type,profile_id=profile_id))

    def preview_resume(self,identity,profile_id,revision,filename,content,content_type=None):
        # Authorize and reject stale work before extraction. This preview is never published.
        existing,_=self.get(identity,profile_id)
        if type(revision) is not int or revision!=existing['revision']:
            raise profiles.ProfileConflictError('Profile changed. Reload it before uploading a resume.')
        draft,completion,analysis=profiles.prepare_draft_with_analysis(filename,content,content_type,profile_id=profile_id)
        # Extraction can be slow; recheck session, association and revision before disclosure.
        current,_=self.get(identity,profile_id)
        if current['revision']!=revision:
            raise profiles.ProfileConflictError('Profile changed during extraction. Reload and review again.')
        draft['revision']=revision
        return draft,completion,analysis
