"""Owned profile snapshots and bound history, using existing inference and domain rules."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import uuid

from pydantic import ValidationError

from ..schemas_profile import PredictionHistoryEntry
from . import assessment_service as assessments, profile_service as profiles
from . import readiness_service, eligibility_service, recommendation_service, performance_service
from .ownership_store import canonical_id, OwnershipNotFound


class AnalyticsUnavailable(Exception):
    pass


class OwnedAnalyticsService:
    def __init__(self, owned_assessments):
        self.assessments = owned_assessments

    def authorize(self, identity, profile_id):
        return self.assessments.profile_access(identity, profile_id)

    def _history(self, access, profile):
        selected=[]
        ids=set()
        keys=set()
        for entry in profile.get('prediction_history') or []:
            if not isinstance(entry,dict):
                continue
            if not (entry.get('account_id')==access.identity.account_id
                    and entry.get('profile_id')==access.profile_id
                    and type(entry.get('ownership_schema_version')) is int and entry['ownership_schema_version']==1
                    and type(entry.get('profile_ownership_version')) is int
                    and entry.get('profile_ownership_version')==access.association['association_version']):
                continue  # Never backfill/replay/project legacy or foreign history.
            try:
                checked=PredictionHistoryEntry.model_validate(entry)
                if (not canonical_id(entry.get('prediction_id')) or type(entry.get('source_revision')) is not int
                        or not 1<=entry['source_revision']<=profile['revision']
                        or not isinstance(entry.get('source_inputs'),dict)
                        or not math.isfinite(checked.placement_probability) or not 0<=checked.placement_probability<=1
                        or (checked.confidence is not None and (not math.isfinite(checked.confidence) or not 0<=checked.confidence<=1))
                        or datetime.fromisoformat(entry['timestamp']).utcoffset().total_seconds()!=0
                        or entry['prediction_id'] in ids
                        or (entry.get('request_id') is not None and entry['request_id'] in keys)):
                    raise ValueError()
            except (ValidationError,ValueError,TypeError,AttributeError):
                raise AnalyticsUnavailable() from None
            ids.add(entry['prediction_id'])
            if entry.get('request_id') is not None:
                keys.add(entry['request_id'])
            selected.append(entry)
        return selected

    def _snapshot(self, access):
        raw=access.load_profile()
        view=deepcopy(raw)
        # Read bound records only; analytics never recover or expire assessments.
        assessments._sessions_for_profile(access.profile_id,access=access)
        view['assessment_evidence']=access.evidence(raw)
        view['prediction_history']=self._history(access,raw)
        return raw,view

    def _recheck(self, access):
        if access.accept()['association_version']!=access.association['association_version']:
            raise OwnershipNotFound()

    def read(self, identity, profile_id, operation, *, company_id=None, limit=None):
        access=self.authorize(identity,profile_id)
        with profiles.profile_transaction(profile_id):
            _,view=self._snapshot(access)
            if operation=='readiness':
                result=readiness_service.readiness_for_profile(view)
            elif operation=='placement-summary':
                result=readiness_service.get_placement_summary(profile_id,snapshot=view)
            elif operation=='eligibility':
                result=eligibility_service.get_all_eligibility(profile_id,snapshot=view)
            elif operation=='company-eligibility':
                result=eligibility_service.get_eligibility(profile_id,company_id,snapshot=view)
            elif operation=='recommendations':
                result=recommendation_service.get_recommendations(profile_id,limit,snapshot=view)
            elif operation=='performance':
                result=performance_service.get_performance(profile_id,snapshot=view)
            elif operation=='skills':
                result=assessments.skills_for_profile(view)
            else:
                raise AnalyticsUnavailable()
            self._recheck(access)
            return result

    def predict(self, identity, profile_id, request_id=None):
        access=self.authorize(identity,profile_id)
        with profiles.profile_transaction(profile_id):
            raw,view=self._snapshot(access)
            history=view['prediction_history']
            if request_id is not None:
                previous=next((e for e in history if e.get('request_id')==request_id),None)
                if previous is not None:
                    completion=profiles.check_profile_completion(view)
                    inputs=completion['ml_feature_mapping']
                    if not view.get('verified') or not completion['profile_complete'] or previous['source_revision']!=view['revision'] or previous['source_inputs']!=inputs:
                        raise profiles.ProfileConflictError('This prediction request is no longer current. Start a new prediction.')
                    self._recheck(access)
                    return {**previous,'profile_id':profile_id,'ready_for_prediction':True,'prediction_history':history}
                if any(isinstance(e,dict) and e.get('request_id')==request_id for e in raw.get('prediction_history') or []):
                    # Unbound keys cannot be promoted into authenticated replay identities.
                    raise profiles.ProfileConflictError('This prediction request cannot be replayed. Start a new prediction.')
            result=profiles.prediction_for_snapshot(view)
            self._recheck(access)
            if not result['ready_for_prediction']:
                return result
            current=access.load_profile()
            if current['revision']!=raw['revision'] or profiles.check_profile_completion(current)['ml_feature_mapping']!=profiles.check_profile_completion(raw)['ml_feature_mapping']:
                raise profiles.ProfileConflictError('The profile changed. Refresh before predicting.')
            entry={key:result[key] for key in ('model_version','placement_probability','prediction','confidence')}
            entry.update(prediction_id=str(uuid.uuid4()),account_id=identity.account_id,profile_id=profile_id,
                         ownership_schema_version=1,profile_ownership_version=access.association['association_version'],
                         timestamp=datetime.now(timezone.utc).isoformat(),request_id=request_id,
                         source_revision=raw['revision'],source_inputs=profiles.check_profile_completion(raw)['ml_feature_mapping'])
            # Validate the new projection before persistence. Retain the raw historical array.
            self._history(access,{**raw,'prediction_history':[*history,entry]})
            current['prediction_history']=[*(current.get('prediction_history') or []),entry]
            self._recheck(access)
            profiles._save(current)
            result['prediction_history']=[*history,entry]
            return result
