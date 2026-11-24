"""Continuous percentage classification without rounding or defensive mislabelling."""
import math
from numbers import Real


def valid_percentage(score):
    if isinstance(score, bool) or not isinstance(score, Real):
        return False
    try:
        return math.isfinite(score) and 0 <= score <= 100
    except (OverflowError, TypeError, ValueError):
        return False


def classify_percentage(score, levels):
    """Intervals are lower-inclusive/upper-exclusive, with 100 included."""
    if not valid_percentage(score):
        raise ValueError('score must be a finite number between 0 and 100')
    for low, high, label in levels:
        if low <= score < high or score == high == 100:
            return label
    raise ValueError('score has no configured level')
