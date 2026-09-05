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
    lookup_entry_matches_item,
    normalize_co_csv_bill_number,
    resolve_veteran_impact_for_item,
)

MA_H2463_FUNERAL_VACCINE_TEXT = (
    "An Act relative to proper classification of health care workers during a "
    "public health emergency. "
    "Chapter 111 of the General Laws is hereby amended by inserting after "
    "section 5A 1/2, the following section: Section 5A 3/4 - Notwithstanding any "
    "general or special law to contrary, Whenever the commissioner determines that "
    "the inoculation of the general public by, or the administration to the general "
    "public of, any antitoxin, serum, vaccine or other analogous product is essential "
    "in the interest of the public health, and that supply for universal "
    "administration is insufficient, the department shall ensure that funeral home "
    "directors and funeral workers are included in the same category as health care "
    "providers in terms of prioritization of access."
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


def test_classify_red_from_veteran_behavioral_health_crisis_expansion():
    result = classify_veteran_impact(
        "Behavioral Health Crisis Services Expansion for veterans and military families"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "behavioral health crisis" in result["reason"].lower()
    assert "Healthcare & Mental Health" in result["factors"]


def test_behavioral_health_crisis_without_veteran_context_is_not_flagged():
    assert classify_veteran_impact(
        "Behavioral Health Crisis Services Expansion for community clinics"
    ) is None


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


@pytest.mark.parametrize(
    "text",
    [
        "State employee pension reform and contribution rates",
        "Establish hiring preference for local residents in public works",
        "Expand drug treatment court and diversion programs statewide",
        "A resolution to honor community volunteers and civic leaders",
        "Designate State Route 12 as the Main Street Memorial Highway",
        "Professional licensing and certification reciprocity for nurses",
        "Employment preference for state contractors and apprenticeships",
        "Ceremonial recognition commemorating local first responders",
    ],
)
def test_generic_terms_alone_do_not_flag_veteran(text):
    """Ambiguous keywords must not mark a bill veteran-related without context."""
    assert classify_veteran_impact(text) is None


def test_veteran_context_plus_pension_is_red():
    result = classify_veteran_impact("Expand veteran pension and compensation benefits")
    assert result is not None
    assert result["level"] == "red"
    assert "pension" in result["reason"].lower() or "compensation" in result["reason"].lower()


def test_veteran_context_plus_hiring_preference_is_yellow():
    result = classify_veteran_impact("Hiring preference for honorably discharged veterans")
    assert result is not None
    assert result["level"] == "yellow"
    assert "hiring preference" in result["reason"].lower()


def test_veteran_context_plus_diversion_is_yellow():
    result = classify_veteran_impact("Veterans treatment court diversion and sentencing alternatives")
    assert result is not None
    assert result["level"] == "yellow"


def test_veteran_context_plus_honor_is_green():
    result = classify_veteran_impact("A resolution to honor military veterans from this state")
    assert result is not None
    assert result["level"] == "green"


def test_veteran_context_plus_designate_memorial_is_green():
    result = classify_veteran_impact(
        "Designate State Route 12 as the Veterans Memorial Highway"
    )
    assert result is not None
    assert result["level"] == "green"


def test_strong_phrases_still_work_without_extra_markers():
    assert classify_veteran_impact("Expand GI Bill education benefits")["level"] == "red"
    assert classify_veteran_impact("Establish a veterans court program")["level"] == "yellow"
    assert classify_veteran_impact("Improve VA health clinic access")["level"] == "red"


def test_ai_veteran_tagging_gates_generic_keywords():
    """AI/topic tagging establishes relatedness so gated terms can color."""
    result = classify_veteran_impact(
        "Expand pension and hiring preference programs",
        has_veteran_tagging=True,
    )
    assert result is not None
    assert result["level"] in ("red", "yellow")


def test_classify_armed_forces_resolution_green():
    result = classify_veteran_impact(
        "HCONRES 68: To direct the removal of United States Armed Forces from hostilities"
    )
    assert result is not None
    assert result["level"] == "green"


def test_classify_yellow_from_va_secretary_study_directive():
    result = classify_veteran_impact(
        "To direct the Secretary of Veterans Affairs to study wait times "
        "for disability claims."
    )
    assert result is not None
    assert result["level"] == "yellow"
    assert "secretary of veterans affairs to study" in result["reason"].lower()
    assert "Studies & Reports" in result["factors"]


def test_classify_yellow_from_va_secretary_conduct_a_study():
    result = classify_veteran_impact(
        "A bill to direct the Secretary of Veterans Affairs to conduct a study "
        "on rural veterans' access to care."
    )
    assert result is not None
    assert result["level"] == "yellow"
    assert "Studies & Reports" in result["factors"]


def test_generic_study_without_va_secretary_is_not_yellow():
    assert classify_veteran_impact("A bill to study water quality in state parks") is None


def test_va_study_with_gi_bill_stays_red():
    result = classify_veteran_impact(
        "To direct the Secretary of Veterans Affairs to study GI Bill payment delays"
    )
    assert result is not None
    assert result["level"] == "red"


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


def test_ma_h2463_funeral_vaccine_not_veteran():
    """MA H2463 (funeral workers + vaccine priority) must not be veteran-colored."""
    assert classify_veteran_impact(MA_H2463_FUNERAL_VACCINE_TEXT) is None


def test_stale_lookup_cross_session_collision_ignored():
    """
    Stale MA|H 2463 yellow from an older 'firearm licensing' bill must not
    color the current-session funeral/vaccine H2463.
    """
    stale_lookup = {
        "MA|H 2463": {
            "level": "yellow",
            "factors": ["Employment & Education"],
            "source": "rules",
            "veteran_related": True,
            "reason": "Classified yellow based on matched keywords: licensing.",
            "title": "An Act relative to firearm licensing renewals during a state of emergency",
            "bill_number_norm": "H 2463",
        }
    }
    current = {
        "title": "H 2463: An Act relative to proper classification of health care workers "
                 "during a public health emergency",
        "bill_number": "H 2463",
        "state": "MA",
        "source": "State (Massachusetts)",
        "summary": MA_H2463_FUNERAL_VACCINE_TEXT,
    }
    assert not lookup_entry_matches_item(stale_lookup["MA|H 2463"], current)
    assert resolve_veteran_impact_for_item(current, stale_lookup) is None


@pytest.mark.parametrize(
    "order",
    [
        "old_first",
        "new_first",
    ],
)
def test_lookup_prefers_newer_bill_and_clears_stale(order):
    """Newer non-veteran bill with the same number clears an older classification."""
    older_veteran = {
        "state": "MA",
        "bill_number": "H 2463",
        "title": "An Act relative to veteran hiring preference and licensing",
        "summary": "Veterans employment preference and professional licensing",
        "latest_action_date": "2022-09-08",
    }
    newer_unrelated = {
        "state": "MA",
        "bill_number": "H 2463",
        "title": "An Act relative to proper classification of health care workers "
                 "during a public health emergency",
        "summary": MA_H2463_FUNERAL_VACCINE_TEXT,
        "latest_action_date": "2026-07-31",
    }
    bills = (
        [older_veteran, newer_unrelated]
        if order == "old_first"
        else [newer_unrelated, older_veteran]
    )
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=bills,
    )
    assert build_bill_lookup_key("MA", "H 2463") not in lookup


def test_true_burial_benefit_still_red():
    result = classify_veteran_impact(
        "Expand veterans burial benefits and national cemetery access"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "burial" in result["reason"].lower()


def test_classify_red_from_military_sexual_trauma():
    result = classify_veteran_impact("Military Sexual Trauma Accountability Act")
    assert result is not None
    assert result["level"] == "red"
    assert "military sexual trauma" in result["reason"].lower()


def test_classify_red_from_mst_mental_health_retroactive_benefits():
    result = classify_veteran_impact(
        "A bill to provide for the retroactive payment of benefits for veterans "
        "with covered mental health conditions based on military sexual trauma, "
        "and for other purposes"
    )
    assert result is not None
    assert result["level"] == "red"


def test_classify_red_from_retroactive_veteran_benefits():
    result = classify_veteran_impact(
        "Retroactive payment of benefits for veterans denied earlier claims"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "retroactive" in result["reason"].lower()


def test_classify_red_from_suicide_and_veterans_affairs_committee():
    result = classify_veteran_impact(
        "Improving Personal Risk Assessments to Prevent Suicide Act. "
        "Read twice and referred to the Committee on Veterans' Affairs."
    )
    assert result is not None
    assert result["level"] == "red"
    assert "suicide" in result["reason"].lower()


def test_classify_red_from_ipv_with_veteran_context():
    result = classify_veteran_impact(
        "Intimate partner violence screening for members of the Armed Forces and veterans"
    )
    assert result is not None
    assert result["level"] == "red"
    assert "intimate partner violence" in result["reason"].lower()


def test_classify_red_from_suicidal_ideation_veterans():
    result = classify_veteran_impact(
        "Programs addressing suicidal ideation and suicide among veterans"
    )
    assert result is not None
    assert result["level"] == "red"


def test_ipv_without_veteran_context_is_not_colored():
    assert classify_veteran_impact(
        "Intimate partner violence prevention grants for civilian community programs"
    ) is None


def test_suicide_without_veteran_context_is_not_colored():
    assert classify_veteran_impact(
        "A bill to expand suicide prevention hotlines for the general public"
    ) is None


def test_va_committee_referral_defaults_green():
    """House/Senate/state Veterans' Affairs referrals get a color; default green."""
    result = classify_veteran_impact(
        "A bill relating to state procurement. "
        "Referred to the Committee on Veterans' Affairs."
    )
    assert result is not None
    assert result["level"] == "green"


def test_state_veterans_committee_defaults_green():
    result = classify_veteran_impact(
        "An act concerning procurement of office supplies. "
        "Assigned to the State, Veterans, and Military Affairs Committee.",
    )
    assert result is not None
    assert result["level"] == "green"


def test_stale_rules_lookup_is_rescored_with_current_keywords():
    """Rules lookup from before MST keywords should not keep an outdated green."""
    key = build_bill_lookup_key(None, "S 4877")
    stale = {
        key: {
            "level": "green",
            "source": "rules",
            "veteran_related": True,
            "title": "Military Sexual Trauma Accountability Act",
            "bill_number_norm": "S 4877",
        }
    }
    item = {
        "title": "S 4877: Military Sexual Trauma Accountability Act",
        "bill_number": "S 4877",
        "level": "federal",
        "source": "Congress.gov API",
    }
    impact = resolve_veteran_impact_for_item(item, stale)
    assert impact is not None
    assert impact["level"] == "red"


def test_committee_list_on_record_colors_card():
    record = {
        "title": "Procurement transparency amendments",
        "summary": "",
        "latest_action": "Introduced",
        "committees": [{"name": "House Committee on Veterans' Affairs"}],
        "bill_number": "HR 100",
        "level": "federal",
    }
    lookup = build_veteran_impact_lookup(
        co_data={"bills": {}},
        normalized_bills=[record],
    )
    key = build_bill_lookup_key(None, "HR 100")
    assert key in lookup
    assert lookup[key]["level"] == "green"


def test_noaa_ndaa_sexual_assault_bill_is_not_veteran_colored():
    """HR 2406 amends NDAA but is about NOAA personnel, not veterans/MST."""
    text = (
        "National Oceanic and Atmospheric Administration Sexual Harassment and "
        "Assault Prevention Improvements Act of 2025. "
        "To amend the National Defense Authorization Act for Fiscal Year 2017 to "
        "address sexual harassment and sexual assault involving National Oceanic "
        "and Atmospheric Administration personnel, and for other purposes. "
        "Placed on the Union Calendar, Calendar No. 662."
    )
    assert classify_veteran_impact(text) is None

