"""Continuous readiness/assessment intervals and invalid-input behavior."""
import math

import pytest

from backend.app.services import assessment_service as assessments
from backend.app.services import readiness_service as readiness


@pytest.mark.parametrize('classifier,labels', [
    (readiness.readiness_level, ['Needs Improvement', 'Developing', 'Placement Ready', 'Strong', 'Highly Ready']),
    (assessments.assessment_level, ['Beginner', 'Developing', 'Intermediate', 'Strong', 'Advanced']),
])
@pytest.mark.parametrize('score,index', [
    (0, 0), (0.5, 0), (39, 0), (39.5, 0),
    (math.nextafter(40, -math.inf), 0), (40, 1), (math.nextafter(40, math.inf), 1),
    (59, 1), (59.5, 1), (math.nextafter(60, -math.inf), 1),
    (60, 2), (math.nextafter(60, math.inf), 2), (74, 2), (74.5, 2),
    (math.nextafter(75, -math.inf), 2), (75, 3), (math.nextafter(75, math.inf), 3),
    (89, 3), (89.5, 3), (math.nextafter(90, -math.inf), 3),
    (90, 4), (math.nextafter(90, math.inf), 4), (99.5, 4), (100, 4),
])
def test_continuous_boundaries(classifier, labels, score, index):
    assert classifier(score) == labels[index]


@pytest.mark.parametrize('classifier', [readiness.readiness_level, assessments.assessment_level])
@pytest.mark.parametrize('score', [None, '60', 'bad', True, False, -0.1, 100.1,
                                 math.nan, math.inf, -math.inf, {}, []])
def test_invalid_scores_are_rejected(classifier, score):
    with pytest.raises(ValueError, match='score'):
        classifier(score)


@pytest.mark.parametrize('levels,classifier', [
    (readiness.READINESS_LEVELS, readiness.readiness_level),
    (assessments.ASSESSMENT_LEVELS, assessments.assessment_level),
])
def test_every_tenth_has_exactly_one_interval(levels, classifier):
    for tenth in range(1001):
        score = tenth / 10
        matches = [label for low, high, label in levels
                   if low <= score < high or score == high == 100]
        assert len(matches) == 1, (score, matches)
        assert classifier(score) == matches[0]


def test_readiness_weights_are_preserved():
    assert readiness.READINESS_WEIGHTS == {'technical_skills': 30, 'projects': 20,
        'internships': 15, 'certifications': 8, 'communication': 7, 'profile_completeness': 20}
    assert assessments.ASSESSMENT_READINESS_BONUS_MAX == 5
    assert assessments.ASSESSMENT_SATISFIED_MIN_SCORE == 60
