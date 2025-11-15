"""
Unit tests for enum definitions.

Validates all enums match specification requirements exactly.
"""
import pytest

from apex.models.enums import AACEClass, ProjectStatus, TerrainType, ValidationStatus


class TestProjectStatus:
    """Test ProjectStatus enum."""

    def test_project_status_values(self):
        """Test ProjectStatus has all required values."""
        assert ProjectStatus.DRAFT.value == "draft"
        assert ProjectStatus.VALIDATING.value == "validating"
        assert ProjectStatus.VALIDATED.value == "validated"
        assert ProjectStatus.ESTIMATING.value == "estimating"
        assert ProjectStatus.COMPLETE.value == "complete"
        assert ProjectStatus.ARCHIVED.value == "archived"

    def test_project_status_count(self):
        """Test ProjectStatus has exactly 6 states."""
        assert len(ProjectStatus) == 6

    def test_project_status_string_enum(self):
        """Test ProjectStatus inherits from str."""
        assert isinstance(ProjectStatus.DRAFT, str)
        assert isinstance(ProjectStatus.VALIDATING, str)


class TestValidationStatus:
    """Test ValidationStatus enum."""

    def test_validation_status_values(self):
        """Test ValidationStatus has all required values."""
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.PASSED.value == "passed"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.MANUAL_REVIEW.value == "manual_review"

    def test_validation_status_count(self):
        """Test ValidationStatus has exactly 4 states."""
        assert len(ValidationStatus) == 4

    def test_validation_status_string_enum(self):
        """Test ValidationStatus inherits from str."""
        assert isinstance(ValidationStatus.PENDING, str)
        assert isinstance(ValidationStatus.PASSED, str)


class TestAACEClass:
    """Test AACEClass enum."""

    def test_aace_class_values(self):
        """Test AACEClass has all 5 classes."""
        assert AACEClass.CLASS_5.value == "class_5"
        assert AACEClass.CLASS_4.value == "class_4"
        assert AACEClass.CLASS_3.value == "class_3"
        assert AACEClass.CLASS_2.value == "class_2"
        assert AACEClass.CLASS_1.value == "class_1"

    def test_aace_class_count(self):
        """Test AACEClass has exactly 5 classes."""
        assert len(AACEClass) == 5

    def test_aace_class_string_enum(self):
        """Test AACEClass inherits from str."""
        assert isinstance(AACEClass.CLASS_1, str)
        assert isinstance(AACEClass.CLASS_5, str)

    def test_aace_class_order(self):
        """Test AACE classes can be compared (string comparison)."""
        # Note: String comparison may not give logical ordering
        # This test documents current behavior
        assert AACEClass.CLASS_1 == "class_1"
        assert AACEClass.CLASS_5 == "class_5"


class TestTerrainType:
    """Test TerrainType enum."""

    def test_terrain_type_values(self):
        """Test TerrainType has all required values."""
        assert TerrainType.FLAT.value == "flat"
        assert TerrainType.ROLLING.value == "rolling"
        assert TerrainType.MOUNTAINOUS.value == "mountainous"
        assert TerrainType.URBAN.value == "urban"
        assert TerrainType.WETLAND.value == "wetland"

    def test_terrain_type_count(self):
        """Test TerrainType has exactly 5 types."""
        assert len(TerrainType) == 5

    def test_terrain_type_string_enum(self):
        """Test TerrainType inherits from str."""
        assert isinstance(TerrainType.FLAT, str)
        assert isinstance(TerrainType.MOUNTAINOUS, str)


class TestEnumSerialization:
    """Test enum serialization for database compatibility."""

    def test_enums_serialize_to_strings(self):
        """Test all enums serialize to string values."""
        # ProjectStatus
        assert str(ProjectStatus.DRAFT) == "draft"
        assert ProjectStatus.DRAFT.value == "draft"

        # ValidationStatus
        assert str(ValidationStatus.PASSED) == "passed"
        assert ValidationStatus.PASSED.value == "passed"

        # AACEClass
        assert str(AACEClass.CLASS_3) == "class_3"
        assert AACEClass.CLASS_3.value == "class_3"

        # TerrainType
        assert str(TerrainType.URBAN) == "urban"
        assert TerrainType.URBAN.value == "urban"

    def test_enums_can_be_reconstructed_from_strings(self):
        """Test enums can be created from string values."""
        # ProjectStatus
        assert ProjectStatus("draft") == ProjectStatus.DRAFT
        assert ProjectStatus("complete") == ProjectStatus.COMPLETE

        # ValidationStatus
        assert ValidationStatus("pending") == ValidationStatus.PENDING
        assert ValidationStatus("passed") == ValidationStatus.PASSED

        # AACEClass
        assert AACEClass("class_1") == AACEClass.CLASS_1
        assert AACEClass("class_5") == AACEClass.CLASS_5

        # TerrainType
        assert TerrainType("flat") == TerrainType.FLAT
        assert TerrainType("wetland") == TerrainType.WETLAND

    def test_invalid_enum_values_raise_error(self):
        """Test invalid enum values raise ValueError."""
        with pytest.raises(ValueError):
            ProjectStatus("invalid_status")

        with pytest.raises(ValueError):
            ValidationStatus("not_a_status")

        with pytest.raises(ValueError):
            AACEClass("class_6")

        with pytest.raises(ValueError):
            TerrainType("underwater")


class TestEnumComparison:
    """Test enum equality and comparison."""

    def test_enum_equality(self):
        """Test enum instances are equal to themselves."""
        assert ProjectStatus.DRAFT == ProjectStatus.DRAFT
        assert ValidationStatus.PASSED == ValidationStatus.PASSED
        assert AACEClass.CLASS_3 == AACEClass.CLASS_3
        assert TerrainType.MOUNTAINOUS == TerrainType.MOUNTAINOUS

    def test_enum_inequality(self):
        """Test enum instances are not equal to different values."""
        assert ProjectStatus.DRAFT != ProjectStatus.COMPLETE
        assert ValidationStatus.PASSED != ValidationStatus.FAILED
        assert AACEClass.CLASS_1 != AACEClass.CLASS_5
        assert TerrainType.FLAT != TerrainType.MOUNTAINOUS

    def test_enum_string_equality(self):
        """Test enums equal their string values."""
        assert ProjectStatus.DRAFT == "draft"
        assert ValidationStatus.PASSED == "passed"
        assert AACEClass.CLASS_3 == "class_3"
        assert TerrainType.URBAN == "urban"

    def test_enum_membership(self):
        """Test enum membership checks."""
        assert ProjectStatus.DRAFT in ProjectStatus
        assert ValidationStatus.PENDING in ValidationStatus
        assert AACEClass.CLASS_1 in AACEClass
        assert TerrainType.WETLAND in TerrainType


class TestEnumIteration:
    """Test enum iteration capabilities."""

    def test_enum_iteration_project_status(self):
        """Test iterating over ProjectStatus."""
        statuses = list(ProjectStatus)
        assert len(statuses) == 6
        assert ProjectStatus.DRAFT in statuses
        assert ProjectStatus.ARCHIVED in statuses

    def test_enum_iteration_validation_status(self):
        """Test iterating over ValidationStatus."""
        statuses = list(ValidationStatus)
        assert len(statuses) == 4
        assert ValidationStatus.PENDING in statuses
        assert ValidationStatus.MANUAL_REVIEW in statuses

    def test_enum_iteration_aace_class(self):
        """Test iterating over AACEClass."""
        classes = list(AACEClass)
        assert len(classes) == 5
        assert AACEClass.CLASS_1 in classes
        assert AACEClass.CLASS_5 in classes

    def test_enum_iteration_terrain_type(self):
        """Test iterating over TerrainType."""
        types = list(TerrainType)
        assert len(types) == 5
        assert TerrainType.FLAT in types
        assert TerrainType.WETLAND in types
