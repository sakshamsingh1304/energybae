"""
validation.py — Post-extraction validation and cleanup for MSEDCL bill data.

Normalizes consumer numbers, validates ranges, and flags suspicious values.
"""

import re
from typing import Optional


def clean_consumer_number(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a consumer number to exactly 12 digits.

    Handles common OCR/AI issues:
    - Spaces: "4393 2009 5567" → "439320095567"
    - Dashes: "4393-2009-5567" → "439320095567"
    - Leading/trailing whitespace
    - Non-digit characters mixed in

    Returns:
        12-digit string, or the raw value if it can't be normalized
    """
    if raw is None:
        return None

    raw_str = str(raw).strip()

    # Remove all non-digit characters
    digits_only = re.sub(r"\D", "", raw_str)

    # STRICT GGN BLOCKER: If it's a 15 digit number or starts with multiple zeros, it's the GGN. Reject it.
    if len(digits_only) == 15 or digits_only.startswith("0000"):
        return None

    if len(digits_only) == 12:
        return digits_only

    # If we got 11 or 13 digits, it's likely a minor OCR error
    # Return what we have but flag it
    if len(digits_only) >= 10:
        return digits_only

    # If very few digits, return original (might be a different format)
    return raw_str


def clean_sanctioned_load(raw: Optional[str]) -> Optional[str]:
    """
    Normalize sanctioned load to format like "3.30KW".

    Handles:
    - Missing "KW" suffix
    - Lowercase "kw" or "Kw"
    - Extra spaces: "3.30 KW" → "3.30KW"
    """
    if raw is None:
        return None

    raw_str = str(raw).strip()

    # Extract numeric part
    match = re.search(r"(\d+\.?\d*)\s*(kw|KW|Kw|kW)?", raw_str, re.IGNORECASE)
    if match:
        number = match.group(1)
        return f"{number}KW"

    return raw_str


def clean_bill_amount(raw) -> Optional[float]:
    """
    Normalize bill amount to a float.

    Handles:
    - String amounts: "₹320.45" → 320.45
    - Comma-separated: "3,335.34" → 3335.34
    - Already numeric values
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return float(raw)

    raw_str = str(raw).strip()
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[₹Rs.,\s]", "", raw_str)

    # Re-add decimal point if we removed it (handle "320.45" case)
    # Better approach: only remove commas, keep decimal
    cleaned = str(raw).strip()
    cleaned = re.sub(r"[₹Rs\s]", "", cleaned)
    cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_monthly_units(units) -> Optional[int]:
    """Ensure monthly units is an integer."""
    if units is None:
        return None
    try:
        return int(float(units))
    except (ValueError, TypeError):
        return None


def validate_and_clean(data: dict) -> dict:
    """
    Validate and clean extracted bill data.

    Performs:
    1. Consumer number normalization (12-digit cleanup)
    2. Sanctioned load format normalization
    3. Bill amount type normalization
    4. Monthly consumption validation (range checks)
    5. Flags added for any suspicious values

    Args:
        data: Raw extracted data dict from the AI

    Returns:
        Cleaned data dict with an additional '_warnings' list
    """
    cleaned = dict(data)  # shallow copy
    warnings = []

    # ── Consumer Number ──
    raw_number = data.get("consumer_number")
    cleaned_number = clean_consumer_number(raw_number)
    cleaned["consumer_number"] = cleaned_number

    if cleaned_number and not re.match(r"^\d{12}$", str(cleaned_number)):
        warnings.append(
            f"Consumer number '{cleaned_number}' is not 12 digits — please verify."
        )

    # ── Sanctioned Load ──
    raw_load = data.get("sanctioned_load")
    cleaned["sanctioned_load"] = clean_sanctioned_load(raw_load)

    # Validate load is reasonable (0.5 to 50 KW for residential)
    if cleaned["sanctioned_load"]:
        load_match = re.search(r"(\d+\.?\d*)", cleaned["sanctioned_load"])
        if load_match:
            load_val = float(load_match.group(1))
            if load_val > 50 or load_val < 0.1:
                warnings.append(
                    f"Sanctioned load {load_val}KW seems unusual — please verify."
                )

    # ── Bill Amount ──
    cleaned["bill_amount"] = clean_bill_amount(data.get("bill_amount"))

    if cleaned["bill_amount"] is not None:
        if cleaned["bill_amount"] < 0:
            warnings.append("Bill amount is negative — please verify.")
        elif cleaned["bill_amount"] > 100000:
            warnings.append(
                f"Bill amount ₹{cleaned['bill_amount']:,.2f} seems very high — please verify."
            )

    # ── Monthly Consumption ──
    raw_history = data.get("monthly_consumption", [])
    cleaned_history = []

    for entry in raw_history:
        month = entry.get("month", "Unknown")
        units = clean_monthly_units(entry.get("units"))

        if units is not None:
            if units > 3000:
                warnings.append(
                    f"Month {month}: {units} units seems very high — please verify."
                )
            elif units < 0:
                warnings.append(
                    f"Month {month}: {units} units is negative — please verify."
                )

        cleaned_history.append({"month": month, "units": units})

    cleaned["monthly_consumption"] = cleaned_history

    if len(cleaned_history) < 6:
        warnings.append(
            f"Only {len(cleaned_history)} months extracted — MSEDCL bills typically show 12 months."
        )

    # ── Consumer Name ──
    if not cleaned.get("consumer_name"):
        warnings.append("Consumer name could not be extracted.")

    # ── Connection Type ──
    if not cleaned.get("connection_type"):
        warnings.append("Connection type / tariff code could not be extracted.")

    cleaned["_warnings"] = warnings
    return cleaned
