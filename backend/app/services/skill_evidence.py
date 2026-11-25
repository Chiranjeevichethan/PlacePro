"""Read-only skill evidence policy shared by all backend consumers.

See docs/skill-evidence-policy.md. Claims, measured scores and historical
originals stay separate; only a shared sufficiency projection grants credit.
"""
from datetime import datetime, timezone
import re

from .score_levels import valid_percentage
from .skill_taxonomy import normalize_skill, skill_category

ASSESSMENT_SATISFIED_MIN_SCORE = 60
ASSESSMENT_READINESS_BONUS_MAX = 5


def _path_source(profile, path):
    provenance = profile.get('provenance') or {}
    for source in ('user', 'resume'):
        for candidate in provenance.get(source, []):
            if isinstance(candidate, str) and (candidate == path or
                    path.startswith(candidate + '.') or candidate.startswith(path + '.')):
                return source
    return 'profile'


def collect_profile_skill_evidence(profile):
    """Current mentions only; resume originals never resurrect removed claims."""
    entries = {}

    def add(raw, source, path, canonicals=None):
        if not isinstance(raw, str) or not raw.strip():
            return
        for skill in dict.fromkeys(canonicals if canonicals is not None else normalize_skill(raw)):
            key = (skill, source, path)
            entry = entries.setdefault(key, {'skill': skill, 'category': skill_category(skill),
                'source': source, 'verified': profile.get('verified') is True,
                'original': raw.strip(), 'originals': [], 'path': path, 'timestamp': None})
            if raw.strip() not in entry['originals']:
                entry['originals'].append(raw.strip())

    for category, values in (profile.get('skills') or {}).items():
        if isinstance(values, list):
            path = f'skills.{category}'
            for raw in values:
                add(raw, _path_source(profile, path), path)
    for section in ('projects', 'internships', 'experience'):
        for index, item in enumerate(profile.get(section) or []):
            if not isinstance(item, dict):
                continue
            for raw in item.get('technologies') or []:
                add(raw, section, f'{section}.{index}.technologies')
    for index, cert in enumerate(profile.get('certifications') or []):
        if not isinstance(cert, dict) or not isinstance(cert.get('name'), str):
            continue
        name = cert['name']
        skills = normalize_skill(name)
        if not skills:
            skills = [skill for token in re.split(r'[^A-Za-z0-9+#.]+', name)
                      for skill in normalize_skill(token)]
        add(name, 'certifications', f'certifications.{index}.name', skills)
    return list(entries.values())


def _completion_time(value):
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _assessment_order(entry):
    try:
        attempt = max(0, int(entry.get('attempt') or 0))
    except (ValueError, TypeError, OverflowError):
        attempt = 0
    return (_completion_time(entry.get('timestamp')), attempt,
            str(entry.get('assessment_id') or ''))


def assessment_evidence_status(entry):
    if entry.get('source') != 'assessment' or not valid_percentage(entry.get('score')):
        return 'INVALID'
    if entry.get('verified') is not True:
        return 'UNCONFIRMED'
    return 'SATISFIED' if entry['score'] >= ASSESSMENT_SATISFIED_MIN_SCORE else 'INSUFFICIENT'


def _latest_assessments(profile):
    latest = {}
    for index, entry in enumerate(profile.get('assessment_evidence') or []):
        if not isinstance(entry, dict):
            continue
        for skill in dict.fromkeys(normalize_skill(entry.get('skill'))):
            candidate = {**entry, 'skill': skill, 'category': skill_category(skill),
                         'original': entry.get('skill'), 'path': f'assessment_evidence.{index}'}
            previous = latest.get(skill)
            if previous is None or _assessment_order(candidate) > _assessment_order(previous):
                latest[skill] = candidate
    return latest


def latest_assessment_evidence(profile):
    """Latest trusted numeric evidence, never a fallback to an older passing score."""
    return [entry for entry in _latest_assessments(profile).values()
            if assessment_evidence_status(entry) in {'SATISFIED', 'INSUFFICIENT'}]


def resolve_skill_evidence(profile):
    claims = collect_profile_skill_evidence(profile)
    latest = _latest_assessments(profile)
    by_skill = {}
    for entry in claims:
        by_skill.setdefault(entry['skill'], []).append(entry)
    result = {}
    accepted = []
    for skill in dict.fromkeys([*by_skill, *latest]):
        mentions = by_skill.get(skill, [])
        confirmed = [entry for entry in mentions if entry['verified']]
        assessed = latest.get(skill)
        assessed_status = assessment_evidence_status(assessed) if assessed else None
        trusted = assessed_status in {'SATISFIED', 'INSUFFICIENT'}
        status = assessed_status if trusted else ('SATISFIED' if confirmed else
                 assessed_status or 'UNCONFIRMED')
        support = [*mentions, *([assessed] if assessed else [])]
        result[skill] = {'status': status, 'score': assessed['score'] if trusted else None,
                         'assessment': assessed, 'evidence': support,
                         'profile_confirmed': bool(confirmed)}
        if status == 'SATISFIED':
            accepted.extend(confirmed)
            if trusted:
                accepted.append(assessed)
    return {'skills': result, 'accepted_entries': accepted,
            'satisfied_skills': {skill for skill, item in result.items() if item['status'] == 'SATISFIED'}}


def skill_status(resolved, skill):
    """Multi-skill aliases require each named skill; unknown names stay missing."""
    names = normalize_skill(skill) or [skill]
    statuses = [resolved['skills'].get(name, {}).get('status', 'MISSING') for name in names]
    for status in ('MISSING', 'INVALID', 'UNCONFIRMED', 'INSUFFICIENT'):
        if status in statuses:
            return status
    return 'SATISFIED'


def assessment_readiness_bonus(resolved):
    # A combined HTML/CSS assessment supports two skills but contributes once.
    qualifying = {}
    for skill, info in resolved['skills'].items():
        assessed = info['assessment']
        if assessed and assessment_evidence_status(assessed) == 'SATISFIED':
            key = assessed.get('assessment_id') or skill
            qualifying[key] = assessed['score']
    if not qualifying:
        return 0.0
    average = sum(qualifying.values()) / len(qualifying)
    return round(min(ASSESSMENT_READINESS_BONUS_MAX,
                     average / 100 * ASSESSMENT_READINESS_BONUS_MAX), 1)
