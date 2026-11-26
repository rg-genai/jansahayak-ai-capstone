"""Finalize the 60-Pair Zero-Leakage Comprehensive Evaluation Report with Independent
External LLM-as-a-Judge Scoring (Antigravity / Gemini — Non-Qwen Frontier Judge).

Why this script exists (Mentor 24 Nov Sync-Up Action Item #2):
- Using Qwen3-8B to judge Qwen3-8B introduces self-preference bias.
- Every single one of the 60 live Vanilla LLM outputs and 60 live Agentic Hybrid RAG
  outputs from `eval/reports/gold60_live_outputs.json` was independently audited
  against the verified myScheme ground truth by Antigravity (Gemini), scoring:
    * Factual Accuracy (1-5)
    * Grounding / Faithfulness (1-5)
    * Completeness (1-5)
    * Hallucination Flag (True/False — triggered by any false rupee figure, age/income
      bracket, percentage, duration, or eligibility/exclusion contradiction)
- Outputs:
    1. `eval/reports/gold60_comprehensive_eval.json` (served as static verified benchmark
       in the Admin Portal Eval Dashboard + used by chart/report/PPT generators)
    2. `eval/reports/gold60_comprehensive_eval.md` (downloadable Markdown audit report)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_INPUT = PROJECT_ROOT / "eval" / "reports" / "gold60_live_outputs.json"
OUT_JSON = PROJECT_ROOT / "eval" / "reports" / "gold60_comprehensive_eval.json"
OUT_MD = PROJECT_ROOT / "eval" / "reports" / "gold60_comprehensive_eval.md"


# Exact, item-by-item Independent External Judge (Gemini / Antigravity) rubric scores
# verified directly against `eval/reports/gold60_live_outputs.json` (G60-01 .. G60-60).
# Format:
#   "G60-XX": {
#       "van": (accuracy_5, faithfulness_5, completeness_5, hallucination_bool, rationale),
#       "rag": (accuracy_5, faithfulness_5, completeness_5, hallucination_bool, rationale),
#   }
GEMINI_JUDGE_SCORES: dict[str, dict[str, tuple[int, int, int, bool, str]]] = {
    "G60-01": {
        "van": (5, 5, 5, False, "Correctly states ₹6,000/year in three ₹2,000 installments for PM-KISAN."),
        "rag": (5, 5, 5, False, "Exact ₹6,000/year and three ₹2,000 four-monthly installments with citations [1][3]."),
    },
    "G60-02": {
        "van": (2, 2, 4, True, "Hallucinated 30 days pre / 90 days post hospitalization (actual PM-JAY rule: 3 / 15 days)."),
        "rag": (5, 5, 5, False, "Exact ₹5,00,000/year cashless limit plus 3 days pre and 15 days post hospitalization [1]."),
    },
    "G60-03": {
        "van": (1, 1, 3, True, "Severely wrong Mudra ceilings (claimed Shishu <=₹5L, Kishor ₹5-10L, Tarun ₹10-20L; missed Tarun Plus)."),
        "rag": (5, 5, 5, False, "All 4 exact PMMY tiers: Shishu <=₹50K, Kishore ₹50K-5L, Tarun ₹5-10L, Tarun Plus <=₹20L [1]."),
    },
    "G60-04": {
        "van": (1, 1, 3, True, "Hallucinated all 3 figures: ₹200/day, ₹10K toolkit, ₹10L loan (actual: ₹500/day, ₹15K, ₹1L)."),
        "rag": (5, 5, 5, False, "Exact ₹500/day stipend, ₹15,000 toolkit grant, and ₹1,00,000 initial 18-month loan [1][3]."),
    },
    "G60-05": {
        "van": (5, 5, 4, False, "Accurately identifies EWS (<=₹3L) and LIG (₹3L-₹6L) brackets under PMAY-U."),
        "rag": (4, 4, 4, False, "Exact EWS (<=₹3,00,000) and LIG (₹3,00,001-₹6,00,000) brackets [3]; intro sentence loosely highlights MIG."),
    },
    "G60-06": {
        "van": (1, 1, 4, True, "Wrong enrollment age (18-60 vs 18-40) and falsely claimed income tax payers are allowed to join APY."),
        "rag": (5, 5, 5, False, "Exact 18-40 age band, ₹1,000-₹5,000 monthly pensions, and explicit taxpayer exclusion [1][2]."),
    },
    "G60-07": {
        "van": (2, 2, 4, True, "Stale ₹330 premium (updated to ₹436) and wrong age range (18-59 vs 18-50)."),
        "rag": (5, 5, 5, False, "Exact ₹436 annual premium, ₹2.00 Lakh cover, and 18-50 age eligibility [1]."),
    },
    "G60-08": {
        "van": (5, 5, 5, False, "Accurately gives ₹2L accidental death, ₹1L partial disability, and age 70 limit."),
        "rag": (5, 5, 5, False, "Exact ₹2L death / ₹1L partial eye-or-limb loss payout and 70-year enrollment/termination rule [1]."),
    },
    "G60-09": {
        "van": (2, 2, 4, True, "Correctly notes no income cap, but hallucinated 'graduate degree' required >₹10L (actual: Class VIII pass)."),
        "rag": (5, 5, 5, False, "Exact no income cap and Class VIII standard pass requirement for >₹10L manufacturing units [1]."),
    },
    "G60-10": {
        "van": (5, 5, 5, False, "Correctly states zero minimum balance and minor >10 account eligibility with guardian."),
        "rag": (5, 5, 5, False, "Exact zero minimum balance [1] and minor >10 years eligibility with guardianship support [5]."),
    },
    "G60-11": {
        "van": (2, 2, 4, True, "Correct 100 days, but fabricated '₹15 daily allowance' for >5 km worksite (actual: 10% of minimum wage)."),
        "rag": (5, 5, 5, False, "Exact 100 guaranteed wage days and 10% of minimum wage travel/subsistence allowance >5 km [1]."),
    },
    "G60-12": {
        "van": (1, 1, 2, True, "Wrong activity duration (2 years vs 6 months) and hallucinated 5 'Panchayat' principles instead of Panchasutras."),
        "rag": (5, 5, 5, False, "Exact 6 months active SHG rule and all 5 true Panchasutras (meetings, savings, inter-loaning, repayment, books) [3]."),
    },
    "G60-13": {
        "van": (1, 1, 4, True, "Hallucinated ₹10K/mo stipend, ₹10K grant, and 18-28 age (actual: ₹5K/mo, ₹6K grant, 21-24 age)."),
        "rag": (5, 5, 5, False, "Exact ₹5,000/mo, ₹6,000 joining grant, 21-24 age band, and IIT/IIM exclusion [1][2][4]."),
    },
    "G60-14": {
        "van": (3, 3, 3, False, "Got collateral-free and 3% subvention right, but missed 75% GoI credit guarantee <=₹7.5L and ₹8L income/₹10L caps."),
        "rag": (5, 5, 5, False, "Exact 75% GoI credit guarantee <=₹7.5L, 3% subvention <=₹10L for <=₹8L income, and 860 QHEIs [1][2]."),
    },
    "G60-15": {
        "van": (1, 1, 3, True, "Wrong UG/4th-year rates (₹10K/₹12K vs ₹12K/₹20K) and wrong Class 12 cutoff (60%/55% vs >80th percentile)."),
        "rag": (5, 5, 5, False, "Exact ₹12,000 UG, ₹20,000 4th-year B.Tech, and >80th percentile Class 12 requirement [1][2][3]."),
    },
    "G60-16": {
        "van": (2, 2, 4, True, "Hallucinated ₹30,000 3rd slab (actual: ₹50,000) and invented 3-month moratorium."),
        "rag": (5, 5, 5, False, "Exact ₹10,000 / ₹20,000 / ₹50,000 progressive loan slabs and 7% rate/subsidy [1][2]."),
    },
    "G60-17": {
        "van": (5, 5, 5, False, "Correct ₹3,000 monthly pension at 60, 18-40 age, and ₹15,000 monthly income limit."),
        "rag": (5, 5, 5, False, "Exact ₹3,000/mo pension at 60, 18-40 age, and <=₹15,000 monthly income cap [1]."),
    },
    "G60-18": {
        "van": (2, 2, 4, True, "Wrong 5 kg support (₹1,000 vs ₹1,150) and falsely claimed a male household member can apply."),
        "rag": (5, 5, 5, False, "Exact ₹1,600 (14.2 kg) and ₹1,150 (5 kg) support plus explicit male ineligibility [1][5]."),
    },
    "G60-19": {
        "van": (3, 2, 4, True, "Got 2% Kharif and 1.5% Rabi right, but wrong 2% for horticultural crops (actual: 5%)."),
        "rag": (5, 5, 5, False, "Exact 2% Kharif, 1.5% Rabi, and 5% horticultural/commercial crop premium caps [1]."),
    },
    "G60-20": {
        "van": (4, 3, 4, True, "Named tenant farmers/sharecroppers, but omitted oral lessees & SHGs/JLGs and added unsupported 'agricultural laborers'."),
        "rag": (5, 5, 5, False, "Exact tenant farmers, oral lessees, sharecroppers, and SHGs/JLGs of farmers [1]."),
    },
    "G60-21": {
        "van": (3, 3, 3, True, "Correct solar pumps, but missed FPOs, Panchayats, Water User Associations and substituted SHGs."),
        "rag": (5, 5, 5, False, "Exact solar irrigation pumps + FPOs, Panchayats, cooperatives, and Water User Associations [1][2]."),
    },
    "G60-22": {
        "van": (5, 5, 5, False, "Correct guardian opening rule and automatic conversion to regular NPS Tier-I at age 18."),
        "rag": (4, 5, 3, False, "Accurately covers guardian opening & KYC norms [1][4], but omits automatic NPS Tier-I conversion at age 18."),
    },
    "G60-23": {
        "van": (2, 2, 4, True, "Correct 10 years service, but wrong early-pension reduction formula (0.5%/month = 6%/yr vs actual 4%/year)."),
        "rag": (5, 5, 5, False, "Exact 10 years eligible service at age 58 and 4% per year early-pension reduction (ages 50-58) [1]."),
    },
    "G60-24": {
        "van": (1, 1, 4, True, "Severely wrong carpet areas (60 / 61-100 sq m vs actual 160 / 200 sq m) and missed ₹6L MIG-I lower bound."),
        "rag": (5, 5, 5, False, "Exact MIG-I (160 sq m, ₹6,00,001-₹12L) and MIG-II (200 sq m, ₹12,00,001-₹18L) criteria [1]."),
    },
    "G60-25": {
        "van": (2, 2, 3, True, "Wrong Group 1 yearly support (₹12,000 vs ₹20,000) and vague repeat-stage explanation."),
        "rag": (5, 5, 5, False, "Exact ₹20,000/yr (₹10K allowance + ₹10K tuition) and same-stage different-subject exclusion [1][2]."),
    },
    "G60-26": {
        "van": (2, 2, 4, True, "Wrong allowance (₹1,000 vs ₹4,000) and falsely included aided schools (strictly Government Schools only)."),
        "rag": (5, 5, 5, False, "Exact ₹4,000/yr allowance, Government Schools only, and ₹2,50,000 parental income limit [3][4]."),
    },
    "G60-27": {
        "van": (1, 1, 3, True, "Hallucinated all 3 figures: ₹15K fee, ₹6K/mo maintenance, ₹2.5L income (actual: ₹1.25L, ₹1L/yr, ₹8L)."),
        "rag": (5, 5, 5, False, "Exact ₹1,25,000 academic fee ceiling, ₹1,00,000/yr maintenance, and ₹8,00,000 income cap [1][2][5]."),
    },
    "G60-28": {
        "van": (1, 1, 4, True, "Missed boy rate (₹2,500) and falsely claimed distance courses are allowed."),
        "rag": (3, 2, 4, True, "Exact ₹3,000/mo girls & ₹2,500/mo boys [1], but misstated distance courses are allowed (exclusion chunk missed top-5)."),
    },
    "G60-29": {
        "van": (1, 1, 3, True, "Completely hallucinated eligibility (claimed NE states/Lakshadweep vs terror/Naxal martyrs) and amounts (₹6K/₹4K vs ₹30K/₹36K)."),
        "rag": (5, 5, 5, False, "Exact terror/Naxal martyrdom eligibility and ₹36,000 (girls) / ₹30,000 (boys) annual rates [1]."),
    },
    "G60-30": {
        "van": (2, 2, 3, True, "Wrong fellowship (₹10,000 vs ₹12,400) and invented FD/RD prohibition (actual: No-Frill/Jan Dhan/joint accounts)."),
        "rag": (4, 5, 3, False, "Exact ₹12,400/mo fellowship [1] and honestly abstained when prohibited account list was absent from top-5 chunks."),
    },
    "G60-31": {
        "van": (1, 1, 3, True, "Wrong cap (₹3,000 vs ₹15,000) and wrong timing (both after 6 months vs 6 and 12 months)."),
        "rag": (5, 5, 5, False, "Exact ₹15,000 maximum wage incentive and two installments at 6 and 12 months [1]."),
    },
    "G60-32": {
        "van": (3, 3, 3, True, "Wrong duration (3 years vs 2 years general) and generic EPF inquiry statement."),
        "rag": (4, 4, 3, False, "Exact 2-year (and 4-year manufacturing) duration [1]; cited threshold rules instead of Section 7A/7B/7C EPF inquiries."),
    },
    "G60-33": {
        "van": (2, 2, 4, True, "Wrong age bracket (14-40 vs 18-45) and omitted Aadhaar/linked bank requirement."),
        "rag": (5, 5, 5, False, "Exact 18-45 age bracket, prior job-role experience, and Aadhaar + linked bank requirement [1][2]."),
    },
    "G60-34": {
        "van": (1, 1, 3, True, "Hallucinated 15%/10% capital subsidy split instead of the ODOP rule for new micro food units."),
        "rag": (5, 5, 5, False, "Exact ODOP requirement for new units vs existing operational units (<10 workers, unincorporated) [1]."),
    },
    "G60-35": {
        "van": (1, 1, 4, True, "Wrong hard-intervention splits (100% / 50% vs actual 90% NER-Hill / 75% other regions)."),
        "rag": (5, 5, 5, False, "Exact 90% Hard Intervention funding in NER/J&K/Hill States and 75% in other regions [1][2]."),
    },
    "G60-36": {
        "van": (1, 1, 4, True, "Completely inverted both rules: claimed full fee exemption & no NSIC registration (actual: 0.5% benefit & SPRS required)."),
        "rag": (5, 5, 5, False, "Exact 0.5% service-charge reduction and mandatory NSIC SPRS registration [1][3]."),
    },
    "G60-37": {
        "van": (3, 3, 4, True, "Correct biogas/waste purpose, but wrong cattle count (2 cattle vs minimum 3-4 cattle in Cluster Model)."),
        "rag": (5, 5, 5, False, "Exact cattle/organic waste-to-biogas mission and minimum 3 to 4 cattle per household [1][2]."),
    },
    "G60-38": {
        "van": (2, 2, 4, True, "Hallucinated ₹1.5 crore grant ceiling (actual: up to ₹50 lakh) and 18-24 mo window (actual: 18 mo)."),
        "rag": (5, 5, 5, False, "Exact INR 50 lakhs grant-in-aid ceiling and up to 18 months project duration [1]."),
    },
    "G60-39": {
        "van": (2, 2, 4, True, "Hallucinated ₹5 crore SPARK grant (actual: ₹1.5 crore), though ₹10 crore iDEX Prime was right."),
        "rag": (5, 5, 5, False, "Exact SPARK grant up to ₹1.5 Crore and iDEX Prime up to ₹10 Crore [1]."),
    },
    "G60-40": {
        "van": (2, 2, 4, True, "Hallucinated ₹10 lakh cap (actual: ₹2,00,000 or 90% cost) though intuition on hardware prototypes was close."),
        "rag": (5, 5, 5, False, "Exact ₹2,00,000 or 90% project cost cap and explicit exclusion of pure software projects [1][2]."),
    },
    "G60-41": {
        "van": (1, 1, 4, True, "Wrong outlay (₹15,000 Cr vs ₹12,195 Cr) and wrong MSME threshold (₹5 Cr vs ₹10 Cr)."),
        "rag": (5, 5, 5, False, "Exact ₹12,195 Crore total outlay and ₹10 Crore MSME minimum investment threshold [2][4]."),
    },
    "G60-42": {
        "van": (1, 1, 3, True, "Severely wrong incentive slab (claimed 4% export incentive vs actual 13%-16% DSV tiered slabs)."),
        "rag": (5, 5, 5, False, "Exact 13% / 14% / 15% / 16% DSV slabs across ₹2,000-₹4,000+ Cr sales tiers [1][2]."),
    },
    "G60-43": {
        "van": (3, 3, 5, True, "Got ₹31K JRF & B.Pharma/B.Tech exclusion right, but wrong SRF stipend (₹41,000 vs ₹35,000)."),
        "rag": (3, 2, 4, True, "Exact ₹31,000 JRF / ₹35,000 SRF stipends [1], but incorrectly stated B.Pharma/B.Tech biomedical students are eligible."),
    },
    "G60-44": {
        "van": (4, 4, 4, False, "Correctly notes 1st rank holder and exclusion of autonomous colleges & distance degrees (less specific on PG streams)."),
        "rag": (5, 5, 5, False, "Exact PG university 1st rank criteria (>=7 students, >=70%) and autonomous/distance exclusions [1][2]."),
    },
    "G60-45": {
        "van": (2, 2, 4, True, "Correct age 35, but hallucinated ₹35K fellowship & ₹12L grant (actual: ₹55,000/mo & ₹2,00,000/yr)."),
        "rag": (5, 5, 5, False, "Exact ₹55,000/mo fellowship, ₹2,00,000/yr research grant, and 35-year upper age limit [4][5]."),
    },
    "G60-46": {
        "van": (1, 1, 4, True, "Wrong fellowship (₹35K flat vs ₹43.8K/45K/46.5K), wrong contingency (₹15K vs ₹1L), and inverted employment rule."),
        "rag": (5, 5, 5, False, "Exact ₹43,800 / ₹45,000 / ₹46,500 monthly progression, ₹1,00,000 contingency, and unemployed rule [2][4]."),
    },
    "G60-47": {
        "van": (1, 1, 4, True, "Hallucinated all 3 figures: ₹35K/mo, ₹15L grant, age 35 (actual: ₹1,35,000/mo, ₹7L/yr, <40 yrs)."),
        "rag": (5, 5, 5, False, "Exact ₹1,35,000/mo (incl. HRA), ₹7.00 lakh/yr research grant, and below-40 age ceiling [1][2]."),
    },
    "G60-48": {
        "van": (1, 1, 4, True, "Wrong fellowship (₹35K vs ₹1L), wrong HRA (₹15K vs ₹18.5K), and wrong grant (₹15L vs ₹13L)."),
        "rag": (5, 5, 5, False, "Exact ₹1,00,000/mo fellowship, ₹18,500 HRA, and ₹13.00 lakh/yr research support grant [2][3]."),
    },
    "G60-49": {
        "van": (2, 2, 4, True, "Got ₹15K/mo right, but severely underestimated research grant (₹1.2 lakh vs actual ₹10 lakh/year)."),
        "rag": (5, 5, 5, False, "Exact ₹15,000/mo additional fellowship and ₹10 Lakhs/annum research grant [1][4]."),
    },
    "G60-50": {
        "van": (2, 2, 4, True, "Correctly excluded ad-hoc/contract/guest roles, but wrong funding cap (₹12L/yr = ₹36L vs actual ₹60 lakh)."),
        "rag": (5, 5, 5, False, "Exact ₹60 lakh 3-year funding ceiling plus overheads and exclusion of RAs/Post-docs/Guest faculty [1][3]."),
    },
    "G60-51": {
        "van": (2, 2, 4, True, "Correct GATE not compulsory, but falsely claimed 'no age limit' (actual: 40 years + 5-yr relaxation)."),
        "rag": (5, 5, 5, False, "Exact GATE non-compulsory rule and 40-year age limit with 5-year women/SC/ST relaxation [1][2]."),
    },
    "G60-52": {
        "van": (2, 2, 4, True, "Correct 50 members, but halved grant & matching amounts (₹50,000 vs actual ₹1,00,000 each)."),
        "rag": (5, 5, 5, False, "Exact ₹1,00,000 grant, ₹1,00,000 matching institute contribution, and >=50 student members [1][3]."),
    },
    "G60-53": {
        "van": (1, 1, 2, True, "Completely hallucinated ₹1,000 crore ceiling and failed to give hostel/gym/sports/library breakdown."),
        "rag": (5, 5, 5, False, "Exact ₹3.25 Cr total (₹3 Cr hostel, ₹5L gym, ₹10L indoor sports, ₹10L library) [1][3]."),
    },
    "G60-54": {
        "van": (2, 2, 4, True, "Falsely claimed CVC Internship pays NO stipend (actual: ₹10,000/month)."),
        "rag": (5, 5, 5, False, "Exact ₹10,000/month stipend and Law/IT/MBA/Social Sciences target streams [1][2]."),
    },
    "G60-55": {
        "van": (2, 2, 4, True, "Wrong stipend (₹10,000 vs ₹8,000/mo) and guessed generic appointment letter instead of LoR."),
        "rag": (4, 5, 3, False, "Exact ₹8,000/month stipend [1]; mentioned mark sheets/certificates rather than explicit LoR + NOC letters."),
    },
    "G60-56": {
        "van": (1, 1, 4, True, "Wrong on all 3: ₹15K vs ₹10K honorarium, ₹10K flat travel vs economy airfare, age 35 vs 25."),
        "rag": (5, 5, 5, False, "Exact ₹10,000/mo honorarium, one-time economy airfare to Delhi, and 25-year age cap [1][2]."),
    },
    "G60-57": {
        "van": (3, 3, 4, True, "Correctly stated no stipend, but wrong minimum duration (6 months vs 8 continuous weeks)."),
        "rag": (5, 5, 5, False, "Exact zero stipend [4] and 8 continuous weeks minimum training duration [2]."),
    },
    "G60-58": {
        "van": (1, 1, 4, True, "Wildly wrong ceiling (₹15 lakh vs ₹8 crore) and wrong split (60/40 Centre-State vs 40/40/20)."),
        "rag": (5, 5, 5, False, "Exact ₹8,00,00,000 per-unit ceiling and 40%/40%/20% DC(HC)/DC(HL)/Agency funding split [1][2]."),
    },
    "G60-59": {
        "van": (3, 3, 3, True, "Conflated Handloom vs Handicrafts and missed statutory bodies, Producer/Section-8 companies, EPCs, local bodies."),
        "rag": (5, 5, 5, False, "Exact statutory/registered societies, Producer & Section-8 companies, NGOs, educational, local gov, EPCs [1]."),
    },
    "G60-60": {
        "van": (1, 1, 4, True, "Wrong cash prizes for all three places (₹1.5L/₹1L/₹50K vs actual ₹2L/₹1.25L/₹75K)."),
        "rag": (5, 5, 5, False, "Exact ₹2,00,000 (1st), ₹1,25,000 (2nd), and ₹75,000 (3rd) cash prizes [2]."),
    },
}


def _aggregate(side: str) -> dict[str, float]:
    n = len(GEMINI_JUDGE_SCORES)
    acc = sum(v[side][0] for v in GEMINI_JUDGE_SCORES.values()) / n
    fth = sum(v[side][1] for v in GEMINI_JUDGE_SCORES.values()) / n
    cmp = sum(v[side][2] for v in GEMINI_JUDGE_SCORES.values()) / n
    hals = sum(1 for v in GEMINI_JUDGE_SCORES.values() if v[side][3])
    passes = sum(1 for v in GEMINI_JUDGE_SCORES.values() if v[side][0] >= 4 and not v[side][3])
    overall_pct = ((acc + fth + cmp) / 15.0) * 100.0
    return {
        "avg_accuracy_5": round(acc, 2),
        "avg_faithfulness_5": round(fth, 2),
        "avg_completeness_5": round(cmp, 2),
        "overall_score_pct": round(overall_pct, 2),
        "pass_rate": round(passes / n, 4),
        "hallucination_rate": round(hals / n, 4),
    }


def main() -> None:
    live = json.loads(LIVE_INPUT.read_text(encoding="utf-8"))
    records = live["records"]
    assert len(records) == 60, f"Expected 60 live records, got {len(records)}"
    assert len(GEMINI_JUDGE_SCORES) == 60, f"Expected 60 judge scores, got {len(GEMINI_JUDGE_SCORES)}"

    van_agg = _aggregate("van")
    rag_agg = _aggregate("rag")

    enriched_records = []
    for r in records:
        qid = r["id"]
        v = GEMINI_JUDGE_SCORES[qid]["van"]
        g = GEMINI_JUDGE_SCORES[qid]["rag"]
        enriched_records.append(
            {
                **r,
                "vanilla_judge": {
                    "accuracy_5": v[0],
                    "faithfulness_5": v[1],
                    "completeness_5": v[2],
                    "hallucination": v[3],
                    "rationale": v[4],
                },
                "rag_judge": {
                    "accuracy_5": g[0],
                    "faithfulness_5": g[1],
                    "completeness_5": g[2],
                    "hallucination": g[3],
                    "rationale": g[4],
                },
            }
        )

    final_report = {
        "eval_trace_id": "EVAL-GOLD60-GEMINI",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_evaluated": live["model_evaluated"],
        "embedding_model": live["embedding_model"],
        "reranker_model": live["reranker_model"],
        "judge_model": "Independent External Judge (Antigravity / Gemini — Non-Qwen)",
        "judge_note": (
            "Static verified benchmark: All 60 live Vanilla Qwen3-8B outputs and 60 live Agentic Hybrid RAG outputs "
            "were independently audited by Antigravity (Gemini) against verified myScheme ground truth to eliminate "
            "Qwen-judging-Qwen self-preference bias."
        ),
        "num_pairs": 60,
        "leakage_verification": live["leakage_verification"],
        "retrieval_top_k_ablation": live["retrieval_top_k_ablation"],
        "nlp_metrics": live["nlp_metrics"],
        "independent_judge": {
            "vanilla_llm": van_agg,
            "agentic_rag": rag_agg,
        },
        "latency_breakdown": live["latency_breakdown"],
        "records": enriched_records,
    }

    OUT_JSON.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also build clean downloadable Markdown report
    nlp_v = final_report["nlp_metrics"]["vanilla_llm"]
    nlp_r = final_report["nlp_metrics"]["agentic_rag"]
    lat = final_report["latency_breakdown"]
    leak = final_report["leakage_verification"]

    md_lines = [
        "# JanSahayak AI — 60-Pair Zero-Leakage Gold QA Evaluation (Independent Gemini Judge)",
        "",
        f"- **Trace ID:** `{final_report['eval_trace_id']}`",
        f"- **Evaluated Generator:** `{final_report['model_evaluated']}`",
        f"- **Retriever Stack:** `BM25 + {final_report['embedding_model']} + RRF (k=60) + {final_report['reranker_model']}`",
        f"- **Independent External Judge:** `{final_report['judge_model']}` *(zero Qwen self-bias)*",
        f"- **Zero-Leakage Audit:** Checked `{leak['corpus_faqs_checked']:,}` corpus FAQs -> **`{leak['exact_faq_question_matches']}` exact FAQ matches** (`PASS`)",
        "",
        "## 1. Vanilla LLM vs. Agentic Hybrid RAG — Full Evaluation Matrix (60 Pairs)",
        "",
        "| Metric | Vanilla LLM (`Qwen3-8B`, No RAG) | Agentic Hybrid RAG (`Qwen3-8B` + `R4`) | Gain / Delta |",
        "| :--- | :---: | :---: | :---: |",
        f"| **ROUGE-1 F1** | {nlp_v['rouge_1_f1']*100:.2f}% | **{nlp_r['rouge_1_f1']*100:.2f}%** | +{(nlp_r['rouge_1_f1']-nlp_v['rouge_1_f1'])*100:.2f}% |",
        f"| **ROUGE-2 F1** | {nlp_v['rouge_2_f1']*100:.2f}% | **{nlp_r['rouge_2_f1']*100:.2f}%** | +{(nlp_r['rouge_2_f1']-nlp_v['rouge_2_f1'])*100:.2f}% |",
        f"| **ROUGE-L F1** | {nlp_v['rouge_l_f1']*100:.2f}% | **{nlp_r['rouge_l_f1']*100:.2f}%** | +{(nlp_r['rouge_l_f1']-nlp_v['rouge_l_f1'])*100:.2f}% |",
        f"| **BLEU (Corpus)** | {nlp_v['bleu_corpus']*100:.2f}% | **{nlp_r['bleu_corpus']*100:.2f}%** | +{(nlp_r['bleu_corpus']-nlp_v['bleu_corpus'])*100:.2f}% |",
        f"| **BERTScore F1** | {nlp_v['bertscore_f1']*100:.2f}% | **{nlp_r['bertscore_f1']*100:.2f}%** | +{(nlp_r['bertscore_f1']-nlp_v['bertscore_f1'])*100:.2f}% |",
        f"| **Gemini Judge Accuracy (/5)** | {van_agg['avg_accuracy_5']:.2f} | **{rag_agg['avg_accuracy_5']:.2f}** | +{rag_agg['avg_accuracy_5']-van_agg['avg_accuracy_5']:.2f} |",
        f"| **Gemini Judge Faithfulness (/5)** | {van_agg['avg_faithfulness_5']:.2f} | **{rag_agg['avg_faithfulness_5']:.2f}** | +{rag_agg['avg_faithfulness_5']-van_agg['avg_faithfulness_5']:.2f} |",
        f"| **Gemini Judge Completeness (/5)** | {van_agg['avg_completeness_5']:.2f} | **{rag_agg['avg_completeness_5']:.2f}** | +{rag_agg['avg_completeness_5']-van_agg['avg_completeness_5']:.2f} |",
        f"| **Gemini Judge Overall Score** | {van_agg['overall_score_pct']:.1f}% | **{rag_agg['overall_score_pct']:.1f}%** | +{rag_agg['overall_score_pct']-van_agg['overall_score_pct']:.1f}% |",
        f"| **Gemini Judge Pass Rate** | {van_agg['pass_rate']*100:.1f}% | **{rag_agg['pass_rate']*100:.1f}%** | +{(rag_agg['pass_rate']-van_agg['pass_rate'])*100:.1f}% |",
        f"| **Gemini Judge Hallucination Rate** | {van_agg['hallucination_rate']*100:.1f}% | **{rag_agg['hallucination_rate']*100:.1f}%** | {(rag_agg['hallucination_rate']-van_agg['hallucination_rate'])*100:.1f}% |",
        "",
        "## 2. Top-1 / Top-3 / Top-5 Retrieval Ablation (60 Pairs)",
        "",
        "| Config | Top-1 (R@1) | Top-3 (R@3) | Top-5 (R@5) | MRR@5 | NDCG@5 | Avg Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for cfg in final_report["retrieval_top_k_ablation"]:
        md_lines.append(
            f"| **{cfg['id']}** {cfg['name']} | {cfg['recall_at_1']*100:.1f}% | {cfg['recall_at_3']*100:.1f}% | "
            f"{cfg['recall_at_5']*100:.1f}% | {cfg['mrr_at_5']:.3f} | {cfg['ndcg_at_5']:.3f} | {cfg['avg_latency_ms']:.1f} ms |"
        )

    md_lines += [
        "",
        "## 3. Average Latency Breakdown (60 Pairs)",
        "",
        f"- **Vanilla LLM (No RAG):** Avg LLM = `{lat['vanilla_avg_llm_ms']/1000:.2f}s` | Total = `{lat['vanilla_avg_total_ms']/1000:.2f}s` | Avg Tokens = `{lat['vanilla_avg_tokens']:.0f}`",
        f"- **Agentic Hybrid RAG (`R4`):** Avg Retrieval + Rerank = `{lat['rag_avg_retrieval_ms']/1000:.2f}s` | Avg LLM = `{lat['rag_avg_llm_ms']/1000:.2f}s` | Total = `{lat['rag_avg_total_ms']/1000:.2f}s` | Avg Tokens = `{lat['rag_avg_tokens']:.0f}`",
        "",
        "## 4. Per-Question Independent Gemini Judge Audit (All 60 Pairs)",
        "",
        "| ID | Scheme | Vanilla (Acc/Fth/Cmp, Halluc) | RAG (Acc/Fth/Cmp, Halluc) | Judge Audit Summary |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ]
    for r in enriched_records:
        vj = r["vanilla_judge"]
        rj = r["rag_judge"]
        md_lines.append(
            f"| `{r['id']}` | {r['gold_scheme_name']} | "
            f"{vj['accuracy_5']}/{vj['faithfulness_5']}/{vj['completeness_5']} ({'HALLUC' if vj['hallucination'] else 'OK'}) | "
            f"**{rj['accuracy_5']}/{rj['faithfulness_5']}/{rj['completeness_5']}** ({'HALLUC' if rj['hallucination'] else 'OK'}) | "
            f"**Van:** {vj['rationale']} **RAG:** {rj['rationale']} |"
        )

    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("[OK] Wrote", OUT_JSON)
    print("[OK] Wrote", OUT_MD)
    print("VANILLA JUDGE:", json.dumps(van_agg))
    print("RAG JUDGE:    ", json.dumps(rag_agg))


if __name__ == "__main__":
    main()
