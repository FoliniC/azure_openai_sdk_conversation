"""Test Utility Functions."""
import pytest
from custom_components.cronostar.utils.prefix_normalizer import (
    normalize_preset_type,
    get_effective_prefix,
    normalize_prefix,
    extract_prefix_from_entity,
    build_entity_id,
    validate_prefix_format
)
from custom_components.cronostar.utils.error_handler import (
    safe_get,
    build_error_response,
    validate_required_fields,
    validate_data_type,
    log_operation,
    ValidationError
)
from custom_components.cronostar.utils.filename_builder import build_profile_filename

def test_normalize_preset_type():
    """Test normalize_preset_type."""
    assert normalize_preset_type("heating") == "thermostat"
    assert normalize_preset_type("LIGHT") == "generic_switch"
    assert normalize_preset_type("ev") == "ev_charging"
    assert normalize_preset_type("") == "thermostat"
    assert normalize_preset_type(None) == "thermostat"
    assert normalize_preset_type("unknown") == "thermostat"

def test_get_effective_prefix():
    """Test get_effective_prefix."""
    assert get_effective_prefix("living_room") == "living_room_"
    assert get_effective_prefix(None, {"global_prefix": "bedroom"}) == "bedroom_"
    assert get_effective_prefix(None, {"entity_prefix": "kitchen"}) == "kitchen_"
    assert get_effective_prefix(None, None) == ""

def test_normalize_prefix():
    """Test normalize_prefix."""
    assert normalize_prefix("living_room") == "living_room_"
    assert normalize_prefix("bedroom_") == "bedroom_"
    assert normalize_prefix("") == ""
    assert normalize_prefix(None) == ""

def test_extract_prefix_from_entity():
    """Test extract_prefix_from_entity."""
    assert extract_prefix_from_entity("input_number.bedroom_current") == "bedroom_"
    assert extract_prefix_from_entity("input_select.living_room_profiles") == "living_room_"
    assert extract_prefix_from_entity("invalid_entity") is None
    assert extract_prefix_from_entity(None) is None

def test_build_entity_id():
    """Test build_entity_id."""
    assert build_entity_id("input_number", "bedroom", "current") == "input_number.bedroom_current"
    assert build_entity_id("input_select", "living_room_", "profiles") == "input_select.living_room_profiles"

def test_validate_prefix_format():
    """Test validate_prefix_format."""
    assert validate_prefix_format("bedroom_")[0] is True
    assert validate_prefix_format("invalid prefix!")[0] is False
    assert validate_prefix_format("1st_floor")[0] is False
    assert validate_prefix_format("a" * 51)[0] is False

def test_safe_get():
    """Test safe_get."""
    data = {"a": {"b": 1}}
    assert safe_get(data, "a", "b") == 1
    assert safe_get(data, "a", "c", default=0) == 0
    assert safe_get(data, "x") is None

def test_build_error_response():
    """Test build_error_response."""
    err = ValueError("test error")
    resp = build_error_response(err, context="testing", include_details=True)
    assert resp["success"] is False
    assert resp["error"] == "test error"
    assert resp["context"] == "testing"
    assert "details" in resp

def test_validate_required_fields():
    """Test validate_required_fields."""
    validate_required_fields({"name": "test"}, "name")
    with pytest.raises(ValidationError):
        validate_required_fields({}, "name")

def test_validate_data_type():
    """Test validate_data_type."""
    validate_data_type("test", str, "field")
    with pytest.raises(ValidationError):
        validate_data_type(123, str, "field")

def test_log_operation(caplog):
    """Test log_operation."""
    import logging
    with caplog.at_level(logging.INFO):
        log_operation("test_op", True, key="val")
        assert "✓ test_op (key=val)" in caplog.text

def test_build_profile_filename():
    """Test build_profile_filename."""
    assert build_profile_filename("thermostat", "kitchen") == "cronostar_kitchen_data.json"
    assert build_profile_filename("thermostat", "") == "cronostar_default_data.json"
    assert build_profile_filename("thermostat", "cronostar_thermostat_kitchen_") == "cronostar_thermostat_kitchen_data.json"
