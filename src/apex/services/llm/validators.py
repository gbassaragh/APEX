"""
LLM response validation and parsing utilities.

CRITICAL: Validates LLM outputs for structure, content quality, and hallucination detection.
All validation functions are defensive and handle malformed/unexpected responses gracefully.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Hallucination marker patterns (case-insensitive)
HALLUCINATION_PATTERNS = [
    r"i don'?t know",
    r"i can'?t (help|assist|determine|provide)",
    r"as an ai",
    r"i'?m (not able|unable) to",
    r"i don'?t have (access|information|data)",
    r"beyond my (knowledge|capabilities|scope)",
    r"i cannot (access|retrieve|provide)",
    r"no information available",
    r"insufficient (data|information|context)",
    r"not enough (data|information|context)",
]


def validate_narrative_response(response: str, min_length: int = 100) -> bool:
    """
    Validate LLM-generated narrative for completeness and quality.

    Args:
        response: LLM-generated narrative text
        min_length: Minimum acceptable character length (default: 100)

    Returns:
        True if narrative meets quality standards, False otherwise

    Validation Criteria:
        - Length >= min_length characters
        - No hallucination markers present
        - Contains actual content (not just whitespace/newlines)
        - Not empty or placeholder text
    """
    if not response or not isinstance(response, str):
        logger.warning("Narrative validation failed: empty or non-string response")
        return False

    # Strip whitespace for content check
    content = response.strip()

    # Check minimum length
    if len(content) < min_length:
        logger.warning(f"Narrative validation failed: length {len(content)} < minimum {min_length}")
        return False

    # Check for hallucination markers
    if check_hallucination_markers(content):
        logger.warning("Narrative validation failed: hallucination markers detected")
        return False

    # Check for placeholder patterns
    placeholder_patterns = [
        r"\[.*?\]",  # [placeholder], [TODO], [insert text here]
        r"\{.*?\}",  # {placeholder}
        r"xxx+",  # xxx, xxxx
        r"TODO",  # TODO
        r"FIXME",  # FIXME
        r"TBD",  # TBD
    ]

    for pattern in placeholder_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            logger.warning(f"Narrative validation failed: placeholder pattern '{pattern}' found")
            return False

    # Check for reasonable word count (narratives should have substance)
    word_count = len(content.split())
    if word_count < 20:  # Arbitrary but reasonable minimum
        logger.warning(f"Narrative validation failed: only {word_count} words")
        return False

    logger.info(f"Narrative validation passed: {len(content)} chars, {word_count} words")
    return True


def validate_assumptions_list(assumptions: List[str]) -> List[str]:
    """
    Validate and clean assumptions list from LLM.

    Args:
        assumptions: Raw list of assumption strings from LLM

    Returns:
        Cleaned list of valid assumptions (empty items and duplicates removed)

    Cleaning Steps:
        1. Remove None/empty strings
        2. Strip whitespace
        3. Remove duplicates (case-insensitive)
        4. Remove placeholder text
        5. Validate minimum substance (>10 characters)
    """
    if not assumptions or not isinstance(assumptions, list):
        logger.warning("Assumptions validation: received empty or non-list input")
        return []

    cleaned = []
    seen_lowercase = set()

    for assumption in assumptions:
        if not assumption or not isinstance(assumption, str):
            continue

        # Strip whitespace
        cleaned_text = assumption.strip()

        # Skip if too short (likely not substantive)
        if len(cleaned_text) < 10:
            logger.debug(f"Skipping short assumption: '{cleaned_text}'")
            continue

        # Check for placeholder patterns
        if re.search(r"(TODO|FIXME|TBD|\[.*?\]|\{.*?\})", cleaned_text, re.IGNORECASE):
            logger.debug(f"Skipping placeholder assumption: '{cleaned_text}'")
            continue

        # Remove duplicates (case-insensitive)
        lowercase = cleaned_text.lower()
        if lowercase in seen_lowercase:
            logger.debug(f"Skipping duplicate assumption: '{cleaned_text}'")
            continue

        seen_lowercase.add(lowercase)
        cleaned.append(cleaned_text)

    logger.info(
        f"Assumptions validated: {len(assumptions)} → {len(cleaned)} (removed {len(assumptions) - len(cleaned)})"
    )
    return cleaned


def validate_exclusions_list(exclusions: List[str]) -> List[str]:
    """
    Validate and clean exclusions list from LLM.

    Args:
        exclusions: Raw list of exclusion strings from LLM

    Returns:
        Cleaned list of valid exclusions (empty items and duplicates removed)

    Cleaning Steps:
        1. Remove None/empty strings
        2. Strip whitespace
        3. Remove duplicates (case-insensitive)
        4. Remove placeholder text
        5. Validate minimum substance (>10 characters)

    Note: Same logic as validate_assumptions_list but kept separate for clarity
          and potential future divergence.
    """
    if not exclusions or not isinstance(exclusions, list):
        logger.warning("Exclusions validation: received empty or non-list input")
        return []

    cleaned = []
    seen_lowercase = set()

    for exclusion in exclusions:
        if not exclusion or not isinstance(exclusion, str):
            continue

        # Strip whitespace
        cleaned_text = exclusion.strip()

        # Skip if too short (likely not substantive)
        if len(cleaned_text) < 10:
            logger.debug(f"Skipping short exclusion: '{cleaned_text}'")
            continue

        # Check for placeholder patterns
        if re.search(r"(TODO|FIXME|TBD|\[.*?\]|\{.*?\})", cleaned_text, re.IGNORECASE):
            logger.debug(f"Skipping placeholder exclusion: '{cleaned_text}'")
            continue

        # Remove duplicates (case-insensitive)
        lowercase = cleaned_text.lower()
        if lowercase in seen_lowercase:
            logger.debug(f"Skipping duplicate exclusion: '{cleaned_text}'")
            continue

        seen_lowercase.add(lowercase)
        cleaned.append(cleaned_text)

    logger.info(
        f"Exclusions validated: {len(exclusions)} → {len(cleaned)} (removed {len(exclusions) - len(cleaned)})"
    )
    return cleaned


def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response.

    Handles common LLM response patterns:
        - JSON wrapped in markdown code blocks (```json ... ```)
        - JSON with surrounding text/explanation
        - Multiple JSON blocks (returns first valid one)
        - Malformed JSON (attempts to fix common issues)

    Args:
        response: Raw LLM response potentially containing JSON

    Returns:
        Parsed JSON as dictionary

    Raises:
        ValueError: If no valid JSON found in response
        json.JSONDecodeError: If JSON is malformed and cannot be fixed
    """
    if not response or not isinstance(response, str):
        raise ValueError("Empty or non-string response provided")

    # Strategy 1: Try parsing entire response as JSON
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass  # Expected if response has surrounding text

    # Strategy 2: Extract JSON from markdown code blocks
    # Pattern: ```json ... ``` or ``` ... ```
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    code_blocks = re.findall(code_block_pattern, response, re.DOTALL | re.IGNORECASE)

    for block in code_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # Strategy 3: Find JSON object/array patterns in text
    # Look for { ... } or [ ... ]
    json_patterns = [
        r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",  # Nested objects (simple)
        r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]",  # Nested arrays (simple)
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if parsed:  # Ensure not empty
                    logger.info("Successfully extracted JSON from embedded pattern")
                    return parsed
            except json.JSONDecodeError:
                continue

    # Strategy 4: Try to fix common JSON formatting issues
    # Remove common prefixes/suffixes that LLMs add
    cleaned = response.strip()
    prefixes_to_remove = [
        "Here is the JSON:",
        "Here's the JSON:",
        "Output:",
        "Result:",
        "JSON:",
    ]

    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # All strategies failed
    raise ValueError(
        f"Could not extract valid JSON from response. "
        f"Response length: {len(response)}, "
        f"First 100 chars: {response[:100]}"
    )


def check_hallucination_markers(response: str) -> bool:
    """
    Check if LLM response contains hallucination markers.

    Hallucination markers indicate the model is uncertain or unable to complete
    the request (e.g., "I don't know", "I can't help", "as an AI...").

    Args:
        response: LLM response text

    Returns:
        True if hallucination markers detected, False otherwise

    Detection Patterns:
        - "I don't know"
        - "I can't help/assist/determine"
        - "As an AI..."
        - "I'm not able/unable to"
        - "I don't have access/information"
        - "Beyond my knowledge/capabilities"
        - "I cannot access/retrieve/provide"
        - "No information available"
        - "Insufficient data/information"
        - "Not enough data/information"
    """
    if not response or not isinstance(response, str):
        return False

    response_lower = response.lower()

    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, response_lower):
            logger.warning(f"Hallucination marker detected: pattern '{pattern}' matched")
            return True

    return False


def validate_json_structure(
    data: Dict[str, Any], required_fields: List[str], optional_fields: Optional[List[str]] = None
) -> bool:
    """
    Validate JSON structure against expected schema.

    Args:
        data: Parsed JSON data
        required_fields: List of required field names
        optional_fields: List of optional field names (for validation only)

    Returns:
        True if structure is valid, False otherwise

    Validation:
        - All required fields present
        - No unexpected fields (if optional_fields provided)
        - Required fields are not None/empty
    """
    if not isinstance(data, dict):
        logger.warning("JSON structure validation failed: data is not a dictionary")
        return False

    # Check required fields
    for field in required_fields:
        if field not in data:
            logger.warning(f"JSON structure validation failed: missing required field '{field}'")
            return False

        # Check that required fields have values (not None/empty)
        if data[field] is None:
            logger.warning(f"JSON structure validation failed: required field '{field}' is None")
            return False

        # For string fields, check not empty
        if isinstance(data[field], str) and not data[field].strip():
            logger.warning(
                f"JSON structure validation failed: required field '{field}' is empty string"
            )
            return False

        # For list fields, check not empty
        if isinstance(data[field], list) and len(data[field]) == 0:
            logger.warning(
                f"JSON structure validation failed: required field '{field}' is empty list"
            )
            return False

    # If optional fields specified, check for unexpected fields
    if optional_fields is not None:
        expected_fields = set(required_fields + optional_fields)
        actual_fields = set(data.keys())
        unexpected = actual_fields - expected_fields

        if unexpected:
            logger.warning(f"JSON structure validation: unexpected fields {unexpected}")
            # Don't fail validation for unexpected fields, just log warning

    logger.info(f"JSON structure validation passed: {len(required_fields)} required fields present")
    return True
