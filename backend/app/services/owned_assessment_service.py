"""Assessment access uses the existing session and authoritative profile association."""
from pathlib import Path
import json
from pydantic import ValidationError
from ..schemas_profile import StudentProfile

from . import assessment_service as assessments
from .ownership_store import canonical_id, OwnershipNotFound
from .retry_integrity import fingerprint,request_identity


class AssessmentAccess:
    def __init__(self, profiles, identity, profile_id):
        self.profiles, self.identity, self.profile_id = profiles, identity, profile_id
        self.records = {}
        self.association = self.accept()

    def accept(self):
        association = self.profiles.store.authorize(
            self.identity, self.profile_id, unavailable_as_not_found=False)
        self.profiles._require_file(self.profile_id)
        return association

    def matches(self, session, assessment_id=None):
        return (isinstance(session, dict) and canonical_id(session.get('assessment_id'))
                and (assessment_id is None or session['assessment_id'] == assessment_id)
                and session.get('account_id') == self.identity.account_id
                and session.get('profile_id') == self.profile_id
                and type(session.get('ownership_schema_version')) is int
                and session['ownership_schema_version'] == 1
                and type(session.get('profile_ownership_version')) is int
                and session['profile_ownership_version'] == self.association['association_version'])

    def validate(self, session, assessment_id=None):
        association = self.accept()
        if association['association_version'] != self.association['association_version'] or not self.matches(session, assessment_id):
            raise assessments.AssessmentNotFoundError('Assessment not found.')
        if (assessments._attempt_number(session) < 1 or session.get('skill') not in assessments.SUPPORTED_SKILLS
                or session.get('status') not in {'IN_PROGRESS','SUBMITTING','COMPLETED','EXPIRED'}
                or not isinstance(session.get('questions'), list) or not session['questions']):
            raise assessments.AssessmentStorageError('Assessment storage is temporarily unavailable.')
        self.records[session['assessment_id']] = session

    def bind(self, session):
        session.update(account_id=self.identity.account_id, ownership_schema_version=1,
                       profile_ownership_version=self.association['association_version'])
        if getattr(self,'start_receipt',None) is not None:
            session['start_receipt']=self.start_receipt
        self.validate(session)

    def profile(self, profile):
        self.accept()
        try:
            checked = StudentProfile.model_validate(profile)
            if checked.profile_id != self.profile_id or not checked.revision or checked.revision < 1:
                raise OwnershipNotFound()
        except ValidationError:
            raise OwnershipNotFound() from None

    def load_profile(self):
        self.accept()  # Reauthorize before loading private JSON, including under the domain lock.
        try:
            profile = assessments._load_profile(self.profile_id)
            self.profile(profile)
            return profile
        except (ValueError, TypeError, AttributeError, KeyError):
            raise OwnershipNotFound() from None

    def evidence(self, profile):
        # Keep legacy/unbound evidence stored, but never project it or use it for quota.
        selected = []
        for entry in profile.get('assessment_evidence') or []:
            if not isinstance(entry, dict):
                continue
            record = self.records.get(entry.get('assessment_id'))
            if not record or record['status'] not in {'SUBMITTING','COMPLETED'}:
                continue
            self.validate(record)
            report = record.get('score_report') or {}
            if (entry.get('account_id') == self.identity.account_id
                    and entry.get('skill') == record['skill'] and entry.get('attempt') == record['attempt']
                    and entry.get('timestamp') == record.get('submitted_at')
                    and entry.get('score') == report.get('score') and entry.get('level') == report.get('level')
                    and entry.get('source') == 'assessment' and entry.get('verified') is True):
                selected.append(entry)
            else:
                raise assessments.AssessmentStorageError('Assessment evidence is inconsistent.')
        return selected


class OwnedAssessmentService:
    def __init__(self, profiles):
        self.profiles = profiles

    def profile_access(self, identity, profile_id):
        return AssessmentAccess(self.profiles, identity, profile_id)

    def assessment_access(self, identity, assessment_id):
        if not canonical_id(assessment_id):
            raise assessments.AssessmentNotFoundError('Assessment not found.')
        path = Path(assessments._session_path(assessment_id))
        if not path.is_file() or path.is_symlink():
            raise assessments.AssessmentNotFoundError('Assessment not found.')
        # Non-mutating discovery, using the existing session reader lock. Never sync here.
        try:
            session = assessments._load_session(assessment_id)
        except json.JSONDecodeError:
            raise assessments.AssessmentNotFoundError('Assessment not found.') from None
        if not isinstance(session, dict) or session.get('account_id') != identity.account_id:
            raise assessments.AssessmentNotFoundError('Assessment not found.')
        access = self.profile_access(identity, session.get('profile_id'))
        access.validate(session, assessment_id)
        return access

    def start(self, identity, profile_id, skill, num_questions=None,request_id=None):
        access = self.profile_access(identity, profile_id)
        with assessments._profile_transaction(profile_id):
            profile=access.load_profile()
            if request_id is not None:
                key=request_identity(identity,'assessment-start',profile_id,request_id)
                digest=fingerprint([skill,num_questions])
                for session in assessments._sessions_for_profile(profile_id,access=access):
                    receipt=session.get('start_receipt')
                    if not isinstance(receipt,dict) or receipt.get('key')!=key:
                        continue
                    if receipt.get('payload')!=digest or receipt.get('revision')!=profile['revision']:
                        raise assessments.AssessmentCompletedError('This assessment request is no longer current.')
                    result=self.get(identity,session['assessment_id'])
                    if result['status']!='IN_PROGRESS':
                        raise assessments.AssessmentCompletedError('This assessment request is already complete.')
                    return result
                access.start_receipt={'key':key,'payload':digest,'revision':profile['revision']}
            return assessments.start_assessment(profile_id, skill, num_questions, access=access)

    def get(self, identity, assessment_id):
        access = self.assessment_access(identity, assessment_id)
        result = assessments.get_assessment(assessment_id, access.profile_id, access=access)
        if result['status'] == 'EXPIRED':
            raise assessments.AssessmentExpiredError('This assessment has expired. Start a new assessment.')
        return result

    def submit(self, identity, assessment_id, profile_id, answers,request_id=None):
        access = self.assessment_access(identity, assessment_id)
        if profile_id != access.profile_id:
            raise assessments.AssessmentNotFoundError('Assessment not found.')
        with assessments._profile_transaction(profile_id):
            session=assessments._load_session(assessment_id)
            access.validate(session,assessment_id)
            access.load_profile()
            if session['status'] in {'SUBMITTING','COMPLETED'} and session.get('answers')!=answers:
                raise assessments.AssessmentCompletedError('This assessment has already accepted a submission.')
            if request_id is not None:
                key=request_identity(identity,'assessment-submit',assessment_id,request_id)
                digest=fingerprint(answers)
                receipt=session.get('submission_receipt')
                if receipt is not None and (not isinstance(receipt,dict) or receipt.get('key')!=key or receipt.get('payload')!=digest):
                    raise assessments.AssessmentCompletedError('This assessment has already accepted a submission.')
                access.submission_receipt={'key':key,'payload':digest}
            return assessments.submit_assessment(assessment_id, profile_id, answers, access=access)

    def history(self, identity, profile_id):
        access = self.profile_access(identity, profile_id)
        return {'profile_id':profile_id, 'assessments':assessments.get_assessment_history(profile_id, access=access)}
