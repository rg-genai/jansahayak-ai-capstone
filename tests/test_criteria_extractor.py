"""Grounding checks for LLM-extracted eligibility criteria (no LLM calls; real scheme text from the DB)."""

from __future__ import annotations

from backend.db.repositories import Repository
from backend.retrieval.criteria_extractor import (
    EligibilityCriteria,
    RestrictionCheck,
    _amounts_in,
    apply_restriction_checks,
    ground_criteria,
    quote_in_source,
    restriction_claims,
)


def _scheme(slug: str) -> dict:
    return Repository().get_scheme(slug)


def test_amounts_parsed_in_indian_formats():
    amounts = _amounts_in("income not exceeding Rs. 1.50 lakh; up to ₹ 2,50,000/-; Rs. 8.00 Lakh; 4.5 lakhs")
    assert {150000, 250000, 800000, 450000} <= amounts


def test_outside_the_union_territory_is_not_abroad():
    """The 8B model twice marked the J&K scheme ('higher education outside the Union Territories') as abroad."""
    c = EligibilityCriteria(education_stages=["undergraduate"], study_location="abroad")
    grounded, fixes = ground_criteria(c, _scheme("pm-usp-sssjkl"))
    assert grounded.study_location == "india" and fixes


def test_real_abroad_scheme_keeps_abroad():
    c = EligibilityCriteria(education_stages=["postgraduate", "doctoral"], study_location="abroad")
    grounded, fixes = ground_criteria(c, _scheme("dacssiselosobcebc"))
    assert grounded.study_location == "abroad" and not fixes


def test_income_kept_only_if_written_in_text():
    ok, fixes = ground_criteria(EligibilityCriteria(income_max_inr=150000), _scheme("csspostmsossi"))  # "Rs. 1.50 lakh"
    assert ok.income_max_inr == 150000 and not fixes
    bad, fixes = ground_criteria(EligibilityCriteria(income_max_inr=123456), _scheme("csspostmsossi"))
    assert bad.income_max_inr is None and "income_max_inr" in bad.unclear and fixes


def test_unsupported_category_institution_and_flags_dropped():
    c = EligibilityCriteria(social_categories=["SC", "OBC"], required_institution="IIT Bombay",
                            requires_disability=True, requires_bpl=True)
    grounded, fixes = ground_criteria(c, _scheme("csss-cus"))  # PM-USP: open category, no single institution
    assert "SC" not in grounded.social_categories
    assert grounded.required_institution is None
    assert grounded.requires_disability is None and grounded.requires_bpl is None
    assert len(fixes) >= 3


def test_non_study_scheme_has_no_study_location_and_other_requirements_capped():
    c = EligibilityCriteria(study_location="india", other_requirements=["a", "b", "c", "d", "e"])
    grounded, _ = ground_criteria(c, _scheme("pm-kisan"))
    assert grounded.study_location == "any"
    assert len(grounded.other_requirements) == 3


def test_other_requirements_keep_only_real_must_haves():
    """Seen in the 10-scheme test: permissions and income restatements listed as requirements."""
    c = EligibilityCriteria(other_requirements=[
        "pursuing post-matriculation or post-secondary courses",
        "eligible if failed undergraduate/post-graduate exams",
        "eligible for correspondence courses",
        "parents/guardians' income not exceeding ₹ 2,50,000/- per annum",
        "regular attendance of not less than 60%",
    ])
    grounded, fixes = ground_criteria(c, _scheme("csspostmsossi"))
    assert grounded.other_requirements == [
        "pursuing post-matriculation or post-secondary courses", "regular attendance of not less than 60%"]
    assert any("dropped 3" in f for f in fixes)


def test_institution_type_is_not_a_single_institution():
    c = EligibilityCriteria(required_institution="AICTE approved institutions")
    source = {"scheme_name": "x", "eligibility": "Faculty of AICTE approved institutions may apply."}
    grounded, fixes = ground_criteria(c, source)
    assert grounded.required_institution is None
    assert grounded.other_requirements[0] == "AICTE approved institutions" and fixes
    one, fixes = ground_criteria(EligibilityCriteria(required_institution="University of Delhi"), _scheme("fssdu"))
    assert one.required_institution == "University of Delhi" and not fixes


def test_ebc_and_dnt_categories_accepted_when_in_text():
    c = EligibilityCriteria(social_categories=["OBC", "EBC", "DNT"])
    grounded, fixes = ground_criteria(c, _scheme("pm-yasasvitcceobcebcdnts"))
    assert grounded.social_categories == ["OBC", "EBC", "DNT"] and not fixes


def test_state_list_dropped_when_text_names_no_state():
    """dsctassgcsccm: 'traditional coffee-growing states' was expanded into 24 invented states."""
    c = EligibilityCriteria(required_states=["Kerala", "Karnataka", "Delhi", "Ladakh"])
    grounded, fixes = ground_criteria(c, _scheme("dsctassgcsccm"))
    assert grounded.required_states == [] and "required_states" in grounded.unclear and fixes
    jk = EligibilityCriteria(required_states=["Jammu and Kashmir", "Ladakh"])
    kept, fixes = ground_criteria(jk, _scheme("pm-usp-sssjkl"))
    assert kept.required_states == ["Jammu and Kashmir", "Ladakh"] and not fixes


def _source(slug: str) -> str:
    scheme = _scheme(slug)
    return " ".join(str(scheme.get(k) or "") for k in ("scheme_name", "brief_description", "eligibility", "exclusions"))


def test_only_restricting_values_are_verified():
    c = EligibilityCriteria(social_categories=["SC"], requires_disability=True, age_max=30, income_max_inr=100000)
    assert set(restriction_claims(c)) == {"social_categories", "requires_disability", "age_max"}
    assert restriction_claims(EligibilityCriteria(income_max_inr=100000, age_min=18)) == {}


def test_quote_must_exist_in_scheme_text():
    source = _source("jrfbio")
    assert quote_in_source("applicant should NOT be more then 28 years for General and EWS category candidates", source)
    assert not quote_in_source("This fellowship is only for SC/ST candidates.", source)
    assert not quote_in_source("", source)


def test_jrfbio_category_age_limit_is_not_a_category_restriction():
    """jrfbio: '28 years for general and EWS ... 33 years for SC/ST/PH' was extracted as SC/ST-only, age_max 28."""
    c = EligibilityCriteria(social_categories=["SC", "ST"], age_max=28)
    checks = {
        "social_categories": RestrictionCheck(holds_for_all_applicants=False, quote=""),
        "age_max": RestrictionCheck(holds_for_all_applicants=False, highest_limit=33,
                                    quote="Applicant should not be more then 28 years for general"),
    }
    verified, fixes = apply_restriction_checks(c, checks, _source("jrfbio"))
    assert verified.social_categories == [] and "social_categories" in verified.unclear
    assert verified.age_max == 33
    assert len(fixes) == 2


def test_tgsct_confirmation_with_invented_quote_is_rejected():
    """tgsctclvccmuo lists SC/ST/OBC teachers as ONE kind of eligible applicant; a made-up quote must not keep it."""
    c = EligibilityCriteria(social_categories=["SC", "ST", "OBC"], requires_disability=True)
    fake = RestrictionCheck(holds_for_all_applicants=True, quote="The grant is only for SC/ST/OBC teachers.")
    verified, _ = apply_restriction_checks(c, {"social_categories": fake, "requires_disability": None},
                                           _source("tgsctclvccmuo"))
    assert verified.social_categories == [] and verified.requires_disability is None


def test_confirmed_restriction_with_real_quote_is_kept():
    c = EligibilityCriteria(age_max=28)
    check = RestrictionCheck(holds_for_all_applicants=True, quote="should not be more then 28 years for general")
    verified, fixes = apply_restriction_checks(c, {"age_max": check}, _source("jrfbio"))
    assert verified.age_max == 28 and fixes == []


def test_higher_age_limit_not_in_text_is_ignored():
    c = EligibilityCriteria(age_max=28)
    check = RestrictionCheck(holds_for_all_applicants=False, highest_limit=45, quote="")
    verified, _ = apply_restriction_checks(c, {"age_max": check}, _source("jrfbio"))
    assert verified.age_max is None and "age_max" in verified.unclear
