"""
Enumeration types for the APEX application.

All enums use string values for database compatibility.
"""
from enum import Enum


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    DRAFT = "draft"
    VALIDATING = "validating"
    VALIDATED = "validated"
    ESTIMATING = "estimating"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class ValidationStatus(str, Enum):
    """Document validation status."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class AACEClass(str, Enum):
    """
    AACE International estimate classification (Class 1-5).

    Class 5: Conceptual (±50%)
    Class 4: Feasibility (±30%)
    Class 3: Budget (±20%)
    Class 2: Control (±15%)
    Class 1: Check Estimate (±10%)
    """

    CLASS_5 = "class_5"
    CLASS_4 = "class_4"
    CLASS_3 = "class_3"
    CLASS_2 = "class_2"
    CLASS_1 = "class_1"


class TerrainType(str, Enum):
    """Terrain classification for transmission line projects."""

    FLAT = "flat"
    ROLLING = "rolling"
    MOUNTAINOUS = "mountainous"
    URBAN = "urban"
    WETLAND = "wetland"
