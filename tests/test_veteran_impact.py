"""Tests for veteran impact classification and CO import helpers."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.veteran_impact import (  # noqa: E402
    build_bill_lookup_key,
    build_impact_reason,
    build_veteran_impact_lookup,
    classify_veteran_impact,
    collect_feed_bills_for_veteran_lookup,
    infer_item_state,
    is_va_facility_naming,
    normalize_co_csv_bill_number,
    resolve_veteran_impact_for_item,
)


def test_normalize_co_csv_bill_number():
    assert normalize_co_csv_bill_number("HB26-1002") == ("HB26-1002", "HB 1002")
    assert normalize_co_csv_bill_number("sb26-047") == ("SB26-047", "SB 047")


def test_classify_red_from_gi_bill():
    result = classify_veteran_impact("Expand GI Bill education benefits for veterans")
    assert result is not None
    assert result["level"] == "red"
    assert "Benefits & Compensation" in result["factors"]
    assert "reason" in result
    assert "gi bill" in result["reason"].lower()
    assert "red" in result["reason"].lower()


def test_classify_red_from_va_appropriations_title():
    result = classify_veteran_impact("Take Care of America's Veterans Act")
    assert result is not None
    assert result["level"] == "red"
    assert "Appropriations & Funding" in result["factors"]
    assert "take care of america" in result["reason"].lower()


def test_classify_red_from_hr_9237_full_title():
    result = classify_veteran_impact("H.R. 9237 – Take Care of America's Veterans Act")
    assert result is not None
    assert result["level"] == "red"
    assert result["reason"]


def test_classify_yellow_from_employment_preference():
    result = classify_veteran_impact("Veterans employment preference in state hiring")
    assert result is not None
    assert result["level"] == "yellow"
    assert "employment preference" in result["reason"].lower()


def test_classify_red_from_tbi():
    result = classify_veteran_impact(
        "Expand veterans health programs for traumatic brain injury (TBI) care"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "Healthcare & Mental Health" in result["factors"]
    assert "tbi" in result["reason"].lower()


def test_classify_red_from_suicide_prevention():
    result = classify_veteran_impact(
        "Veterans suicide prevention and outreach funding for VA health clinics"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "suicide prevention" in result["reason"].lower()


def test_classify_red_from_ptsd():
    result = classify_veteran_impact("PTSD treatment expansion for veterans")
    assert result is not None
    assert result["level"] == "red"
    assert "ptsd" in result["reason"].lower()


def test_classify_yellow_from_generic_mental_health():
    """Generic mental health is YELLOW; veteran-specific clinical terms are RED."""
    result = classify_veteran_impact(
        "Expand veterans mental health counseling and peer support access"
    )
    assert result is not None
    assert result["level"] == "yellow"
    assert "mental health" in result["reason"].lower()
    assert "Healthcare & Mental Health" in result["factors"]


def test_classify_red_from_housing():
    result = classify_veteran_impact("Homeless veteran housing voucher program")
    assert result is not None
    assert result["level"] == "red"
    assert "Housing & Homelessness" in result["factors"]


def test_classify_red_from_disability_rating():
    result = classify_veteran_impact(
        "Adjust service-connected disability rating schedule for veterans"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "Disability Ratings" in result["factors"]


def test_classify_yellow_from_veterans_court():
    result = classify_veteran_impact("Establish a veterans court diversion program")
    assert result is not None
    assert result["level"] == "yellow"
    assert "Criminal Justice / Courts" in result["factors"]


def test_classify_yellow_from_military_spouse():
    result = classify_veteran_impact("Military spouse licensing reciprocity for veterans families")
    assert result is not None
    assert result["level"] == "yellow"
    assert "military spouse" in result["reason"].lower()


def test_classify_green_from_memorial():
    result = classify_veteran_impact("Honoring Post-9/11 Veterans memorial resolution")
    assert result is not None
    assert result["level"] == "green"
    assert "memorial" in result["reason"].lower() or "honor" in result["reason"].lower()


def test_classify_green_from_va_clinic_naming():
    title = (
        'To designate the community-based outpatient clinic of the Department of '
        'Veterans Affairs in Lafayette, Louisiana, as the "Rodney C. Hamilton Sr. VA Clinic".'
    )
    assert is_va_facility_naming(title)
    result = classify_veteran_impact(title)
    assert result is not None
    assert result["level"] == "green"
    assert "Facility Naming" in result["factors"]
    assert "clinic" in result["reason"].lower() or "facility" in result["reason"].lower()


def test_classify_green_from_va_outpatient_rename():
    title = (
        "To name the Department of Veterans Affairs community-based outpatient clinic "
        'in Newton, New Jersey, as the "Anthony \'Tony\' J. Gallopo VA Clinic".'
    )
    result = classify_veteran_impact(title)
    assert result is not None
    assert result["level"] == "green"


def test_classify_green_from_va_multispecialty_clinic_naming():
    title = (
        "To name the Department of Veterans Affairs multispecialty clinic in Marietta, "
        'Georgia, as the "Colonel Michael H. Boyce Department of Veterans Affairs '
        'Multispecialty Clinic".'
    )
    assert is_va_facility_naming(title)
    result = classify_veteran_impact(title)
    assert result is not None
    assert result["level"] == "green"
    assert "Facility Naming" in result["factors"]


def test_va_appropriations_stays_red_after_clinic_naming_rules():
    result = classify_veteran_impact("Take Care of America's Veterans Act")
    assert result is not None
    assert result["level"] == "red"


def test_csv_level_overrides_rules():
    result = classify_veteran_impact("Generic elections bill", csv_level="Red")
    assert result is not None
    assert result["level"] == "red"
    assert result["source"] == "csv"
    assert "colorado veteran tracker" in result["reason"].lower()
    assert "csv" in result["reason"].lower()


def test_build_impact_reason_includes_keywords_and_factors():
    reason = build_impact_reason(
        "red",
        factors=["Benefits & Compensation"],
        matched_keywords=["gi bill", "veterans benefit"],
    )
    assert "red (high impact)" in reason
    assert "gi bill" in reason
    assert "Benefits & Compensation" in reason


def test_build_lookup_from_co_data():
    co_data = {
        "bills": {
            "HB26-1002": {
                "bill_number_csv": "HB26-1002",
                "bill_number_norm": "HB 1002",
                "title": "Honoring Post-9/11 Veterans",
                "veteran_related": True,
                "impact_level": "green",
                "status": "Became Law",
            }
        }
    }
    lookup = build_veteran_impact_lookup(co_data=co_data, normalized_bills=[])
    assert lookup["CO|HB26-1002"]["level"] == "green"
    assert lookup[build_bill_lookup_key("CO", "HB 1002")]["level"] == "green"
    assert lookup["CO|HB26-1002"]["reason"]
    assert "csv" in lookup["CO|HB26-1002"]["reason"].lower()


def test_resolve_veteran_impact_for_feed_item():
    lookup = {
        "CO|HB26-1002": {"level": "green", "factors": [], "source": "csv", "veteran_related": True},
    }
    item = {
        "title": "HB 1002: Honoring Post-9/11 Veterans",
        "bill_number": "HB 1002",
        "source": "State (Colorado)",
        "state": "CO",
    }
    impact = resolve_veteran_impact_for_item(item, lookup)
    assert impact is not None
    assert impact["level"] == "green"


def test_non_veteran_bill_returns_none():
    assert classify_veteran_impact("Property tax assessment reform") is None


def test_classify_armed_forces_resolution_green():
    result = classify_veteran_impact(
        "HCONRES 68: To direct the removal of United States Armed Forces from hostilities"
    )
    assert result is not None
    assert result["level"] == "green"


def test_build_lookup_ks_bill():
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=[{
            "state": "KS",
            "bill_number": "HB 2273",
            "title": "Recognizing Kansas veterans for their service",
            "summary": "A resolution honoring military veterans",
            "latest_action": "Referred to committee",
        }],
    )
    key = build_bill_lookup_key("KS", "HB 2273")
    assert lookup[key]["level"] == "green"
    assert lookup[key]["source"] == "rules"


def test_build_lookup_federal_bill():
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=[{
            "level": "federal",
            "bill_number": "HR 1041",
            "title": "Veterans 2nd Amendment Protection Act",
            "summary": "To amend title 38, United States Code, regarding veterans benefits",
            "latest_action": "Referred to committee",
        }],
    )
    key = build_bill_lookup_key(None, "HR 1041")
    assert key in lookup
    assert lookup[key]["level"] in ("red", "yellow", "green")


def test_build_lookup_from_feed_item():
    feed_items = collect_feed_bills_for_veteran_lookup(
        history_items=[{
            "title": "SB 1234: Veterans employment preference act",
            "bill_number": "SB 1234",
            "source": "State (Arizona)",
            "state": "AZ",
            "summary": "Employment preference for Arizona veterans",
        }],
        legislation_items=[],
    )
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=[],
        feed_items=feed_items,
    )
    key = build_bill_lookup_key("AZ", "SB 1234")
    assert lookup[key]["level"] == "yellow"


def test_resolve_federal_feed_item():
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=[{
            "level": "federal",
            "bill_number": "S 3311",
            "title": "Veterans Affairs Peer Review Neutrality Act",
            "summary": "VA peer review process for veterans health care",
        }],
    )
    item = {
        "title": "S 3311: Veterans Affairs Peer Review Neutrality Act",
        "bill_number": "S 3311",
        "source": "Congress.gov API",
        "summary": "VA peer review process for veterans health care",
    }
    impact = resolve_veteran_impact_for_item(item, lookup)
    assert impact is not None
    assert impact["level"] in ("red", "yellow", "green")


def test_infer_item_state_from_source():
    assert infer_item_state({"source": "State (Utah)"}) == "UT"
    assert infer_item_state({"source": "Congress.gov API", "level": "federal"}) == "Federal"
