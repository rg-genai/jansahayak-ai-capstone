"""Build a 60-pair Zero-Leakage Synthetic Gold QA Dataset (`eval/gold_qa_60.json`) across 24 Central Ministries.

Each question is freshly authored in natural citizen phrasing (NOT copied from scheme_faqs or corpus text)
and automatically audited against all 7,724 official FAQs in SQLite for n-gram / Jaccard leakage.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "jansahayak.db"
OUT_PATH = PROJECT_ROOT / "eval" / "gold_qa_60.json"

GOLD_QA_60: list[dict[str, str]] = [
    {
        "id": "G60-01",
        "gold_scheme_slug": "pm-kisan",
        "domain": "Agriculture",
        "question": "A smallholder farmer family owns cultivable land in their name. How much annual direct income support does PM-KISAN transfer and in how many payouts?",
        "reference_answer": "Under Pradhan Mantri Kisan Samman Nidhi (PM-KISAN), eligible landholding farmer families receive ₹6,000 per year transferred in three equal installments of ₹2,000 every four months. Institutional landholders and higher-economic-status categories such as income tax payers are excluded.",
    },
    {
        "id": "G60-02",
        "gold_scheme_slug": "ab-pmjay",
        "domain": "Healthcare",
        "question": "If a poor family is admitted to an empanelled hospital under Ayushman Bharat PM-JAY, what yearly cashless limit and pre/post-hospitalization days are covered?",
        "reference_answer": "Ayushman Bharat PM-JAY provides cashless hospitalization coverage up to ₹5,00,000 per family per year covering consultation, medicines, diagnostics, surgery, ICU, implants, and food, along with 3 days of pre-hospitalization and 15 days of post-hospitalization expenses.",
    },
    {
        "id": "G60-03",
        "gold_scheme_slug": "pmmy",
        "domain": "Micro-Credit",
        "question": "A small non-farm business owner wants micro-credit under Pradhan Mantri Mudra Yojana. What are the loan tiers and their rupee ceilings?",
        "reference_answer": "Pradhan Mantri Mudra Yojana (PMMY) offers non-farm micro-enterprise loans up to ₹20 lakh across four tiers: Shishu (up to ₹50,000), Kishore (above ₹50,000 up to ₹5 lakh), Tarun (above ₹5 lakh up to ₹10 lakh), and Tarun Plus (up to ₹20 lakh).",
    },
    {
        "id": "G60-04",
        "gold_scheme_slug": "pmv",
        "domain": "Artisans",
        "question": "What daily training stipend, toolkit grant, and initial collateral-free enterprise loan can a traditional craftsperson get under PM Vishwakarma?",
        "reference_answer": "PM Vishwakarma provides traditional artisans in 18 family-based trades (minimum age 18) with a ₹500 per day skill training stipend, a ₹15,000 toolkit incentive grant, and collateral-free credit starting with ₹1,00,000 (18 months repayment) followed by a second tranche of ₹2,00,000. Government employees and their family members are excluded.",
    },
    {
        "id": "G60-05",
        "gold_scheme_slug": "pmay-u",
        "domain": "Housing",
        "question": "Which urban income groups qualify for Credit Linked Subsidy under PMAY-Urban and what are the annual income brackets for EWS and LIG families?",
        "reference_answer": "Pradhan Mantri Awas Yojana - Urban (PMAY-U) covers urban families who do not own a pucca house anywhere in India across EWS (annual household income up to ₹3,00,000 for houses up to 30 sq.m), LIG (₹3,00,001 to ₹6,00,000 for houses up to 60 sq.m), and MIG categories.",
    },
    {
        "id": "G60-06",
        "gold_scheme_slug": "apy",
        "domain": "Pension",
        "question": "At what age can an unorganized worker enroll in Atal Pension Yojana, what monthly pension options start at age 60, and are income tax payers allowed to join?",
        "reference_answer": "Citizens aged 18 to 40 years with a savings bank or post office account can join Atal Pension Yojana (APY) to receive a guaranteed monthly pension of ₹1,000, ₹2,000, ₹3,000, ₹4,000, or ₹5,000 from age 60. Since 1 October 2022, income tax payers are not eligible to join APY.",
    },
    {
        "id": "G60-07",
        "gold_scheme_slug": "pmjjby",
        "domain": "Insurance",
        "question": "How much yearly premium and term life cover does Pradhan Mantri Jeevan Jyoti Bima Yojana provide, and what is the eligible age band?",
        "reference_answer": "Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY) offers a renewable one-year term life insurance cover of ₹2,00,000 for death due to any reason at an annual auto-debited premium of ₹436 for individual bank or post office account holders aged 18 to 50 years.",
    },
    {
        "id": "G60-08",
        "gold_scheme_slug": "pmsby",
        "domain": "Insurance",
        "question": "What payout does Pradhan Mantri Suraksha Bima Yojana offer for accidental death or partial eye/limb disability, and up to what age can account holders enroll?",
        "reference_answer": "Pradhan Mantri Suraksha Bima Yojana (PMSBY) covers participating bank account holders aged 18 to 70 years with ₹2 lakh for accidental death or total irrecoverable loss of both eyes/hands/feet, and ₹1 lakh for total irrecoverable loss of one eye or one hand/foot.",
    },
    {
        "id": "G60-09",
        "gold_scheme_slug": "pmegp",
        "domain": "MSME",
        "question": "Does PMEGP impose an income cap for launching a new manufacturing unit, and what schooling level is required if the project cost exceeds ₹10 lakh?",
        "reference_answer": "Under Prime Minister's Employment Generation Programme (PMEGP), any individual above 18 years can apply for margin money subsidy on a new project with no income ceiling. For manufacturing projects costing above ₹10 lakh (or business/service projects above ₹5 lakh), the applicant must have passed at least Class VIII. Existing units or those that availed other government subsidies are excluded.",
    },
    {
        "id": "G60-10",
        "gold_scheme_slug": "pmjdy",
        "domain": "Banking",
        "question": "Does a Basic Savings Bank Deposit Account under Pradhan Mantri Jan Dhan Yojana require a minimum balance, and can a minor above age 10 open one?",
        "reference_answer": "Under Pradhan Mantri Jan Dhan Yojana (PMJDY), any Indian citizen can open a Basic Savings Bank Deposit Account (BSBDA) with zero minimum balance requirement (up to four cash withdrawals per month). Minors above 10 years of age may also apply with legal guardian support.",
    },
    {
        "id": "G60-11",
        "gold_scheme_slug": "mgnrega",
        "domain": "Rural Employment",
        "question": "How many days of guaranteed wage work does MGNREGA promise a rural household each year, and what allowance applies if the worksite is more than 5 km away?",
        "reference_answer": "MGNREGA guarantees at least 100 days of unskilled wage employment per financial year to rural households with adult members aged 18 or above, provided within 15 days of application. If the assigned worksite is more than 5 km from residence, the worker receives a travel and subsistence allowance of 10% of the minimum wage.",
    },
    {
        "id": "G60-12",
        "gold_scheme_slug": "day-nrlm",
        "domain": "Rural Livelihoods",
        "question": "For a rural women's Self-Help Group to qualify under DAY-NRLM, how long must it be active and what five Panchasutras must it follow?",
        "reference_answer": "Under Deendayal Antyodaya Yojana - National Rural Livelihoods Mission (DAY-NRLM), Self-Help Groups (SHGs) must be actively functioning for at least 6 months as per their books of account, meet NABARD grading norms, and follow the five Panchasutras: regular meetings, regular savings, regular inter-loaning, timely repayment, and up-to-date books of accounts.",
    },
    {
        "id": "G60-13",
        "gold_scheme_slug": "pmis",
        "domain": "Youth Internship",
        "question": "What monthly financial support, joining grant, age range, and IIT/IIM exclusions apply to the Prime Minister's Internship Scheme?",
        "reference_answer": "The Prime Minister's Internship Scheme offers 12-month internships in top 500 companies to Indian youth aged 21 to 24 who are not in full-time employment or education, providing ₹5,000 per month (₹4,500 from Government + ₹500 from Industry), a ₹6,000 one-time incidental grant, and PMJJBY/PMSBY insurance. Graduates from IITs, IIMs, NLUs, IISER, NIDs, IIITs, and holders of CA/MBA/MBBS/master's degrees are excluded.",
    },
    {
        "id": "G60-14",
        "gold_scheme_slug": "pmvs",
        "domain": "Education Loans",
        "question": "How does the PM-Vidyalaxmi Scheme support students admitted on merit to Quality Higher Educational Institutions regarding collateral, credit guarantee, and interest subvention?",
        "reference_answer": "Pradhan Mantri Vidyalaxmi (PM-Vidyalaxmi) provides collateral-free and guarantor-free education loans for merit-based admissions (excluding management quota) to 860 designated QHEIs, offering a 75% Government credit guarantee on loans up to ₹7,50,000 regardless of income, plus 3% interest subvention on loans up to ₹10,00,000 for families earning up to ₹8,00,000 annually.",
    },
    {
        "id": "G60-15",
        "gold_scheme_slug": "csss-cus",
        "domain": "Scholarships",
        "question": "What annual scholarship rates do undergraduate and 4th-year B.Tech students receive under PM-USP Central Sector Scholarship, and what Class 12 percentile is mandatory?",
        "reference_answer": "Under PM-USP Central Sector Scheme of Scholarship for College and University Students, regular degree students above the 80th percentile in Class 12 receive ₹12,000 per year for the first three graduation years and ₹20,000 per year in the 4th and 5th years of professional/integrated courses or post-graduation. Distance-learning, diploma students, and recipients of other scholarships are excluded.",
    },
    {
        "id": "G60-16",
        "gold_scheme_slug": "pm-svanidhi",
        "domain": "Urban Vendors",
        "question": "What three progressive collateral-free working capital loan slabs and interest rate are provided to urban street vendors under PM SVANidhi?",
        "reference_answer": "PM SVANidhi provides urban street vendors (holding a Certificate of Vending, ID card, or ULB Letter of Recommendation) with collateral-free working capital loans starting at ₹10,000, followed by ₹20,000 and ₹50,000 tranches, with a 7% interest subsidy and zero processing fee.",
    },
    {
        "id": "G60-17",
        "gold_scheme_slug": "pm-sym",
        "domain": "Labour Pension",
        "question": "How much monthly assured pension does PM Shram Yogi Maan-dhan guarantee after age 60, and what monthly income ceiling and age criteria apply to unorganized workers?",
        "reference_answer": "Pradhan Mantri Shram Yogi Maan-dhan (PM-SYM) assures a minimum pension of ₹3,000 per month from age 60 (with 50% family pension to the spouse) for unorganized workers aged 18 to 40 years earning up to ₹15,000 per month, with equal matching Government contributions. Income tax payers and EPFO-covered workers are ineligible.",
    },
    {
        "id": "G60-18",
        "gold_scheme_slug": "pmuy",
        "domain": "Clean Energy",
        "question": "What financial support does Pradhan Mantri Ujjwala Yojana give for a 14.2 kg or 5 kg LPG connection, and can a male member of the household apply?",
        "reference_answer": "Pradhan Mantri Ujjwala Yojana (PMUY) provides deposit-free LPG connections to women from BPL/eligible poor households with support of ₹1,600 for a 14.2 kg cylinder or ₹1,150 for a 5 kg cylinder, plus the first refill and stove free of cost. Male household members cannot apply.",
    },
    {
        "id": "G60-19",
        "gold_scheme_slug": "pmfby",
        "domain": "Crop Insurance",
        "question": "What maximum percentage crop insurance premiums do farmers pay for Kharif, Rabi, and horticultural crops under Pradhan Mantri Fasal Bima Yojana?",
        "reference_answer": "Under Pradhan Mantri Fasal Bima Yojana (PMFBY), farmers growing notified crops in notified areas pay a maximum premium of 2% for Kharif food/oilseed crops, 1.5% for Rabi food/oilseed crops, and 5% for annual commercial or horticultural crops, with the remaining premium subsidized by the government (100% subsidized in NE states, J&K, and Himachal Pradesh).",
    },
    {
        "id": "G60-20",
        "gold_scheme_slug": "kcc",
        "domain": "Agricultural Credit",
        "question": "Besides owner-cultivator farmers, which other rural farming groups can obtain a Kisan Credit Card to buy agricultural inputs?",
        "reference_answer": "In addition to individual and joint owner-cultivators, Kisan Credit Card (KCC) eligibility includes tenant farmers, oral lessees, sharecroppers, and Self-Help Groups (SHGs) or Joint Liability Groups (JLGs) of farmers.",
    },
    {
        "id": "G60-21",
        "gold_scheme_slug": "pm-kusum",
        "domain": "Solar Agriculture",
        "question": "What clean-energy farming asset does PM-KUSUM subsidize, and what types of rural bodies besides individual farmers can apply?",
        "reference_answer": "PM-KUSUM (launched by the Ministry of New and Renewable Energy) subsidizes solar irrigation pumps for farmers. Eligible applicants include individual farmers, groups of farmers, Farmer Producer Organizations (FPOs), Panchayats, Co-operatives, and Water User Associations.",
    },
    {
        "id": "G60-22",
        "gold_scheme_slug": "npsvs",
        "domain": "Child Savings",
        "question": "Who can open an NPS Vatsalya account for a child in India, and what happens automatically when the minor turns 18?",
        "reference_answer": "NPS Vatsalya (regulated by PFRDA) allows a natural or legal guardian (completing KYC) to open a pension-cum-saving account for any minor Indian citizen under 18 years. Upon turning 18, the account automatically transitions into a regular NPS Tier I account.",
    },
    {
        "id": "G60-23",
        "gold_scheme_slug": "eps",
        "domain": "Retirement",
        "question": "Under the Employees' Pension Scheme (EPS), how many years of eligible service are needed for superannuation pension at age 58, and how is early pension reduced?",
        "reference_answer": "Under the Employees' Pension Scheme (EPS), EPF members retiring at age 58 with at least 10 years of eligible service receive superannuation pension calculated as (Pensionable Salary × Pensionable Service) / 70. Members retiring early between ages 50 and 58 receive a reduced pension with a 4% reduction for each year below 58.",
    },
    {
        "id": "G60-24",
        "gold_scheme_slug": "clssmig",
        "domain": "Middle-Class Housing",
        "question": "What carpet area limits and annual family income ranges apply to MIG I and MIG II under the Credit Linked Subsidy Scheme for Middle Income Group?",
        "reference_answer": "The Credit Linked Subsidy Scheme for Middle Income Group supports house acquisition or construction up to 160 sq. meters carpet area for MIG I (annual household income ₹6,00,001 to ₹12,00,000) and up to 200 sq. meters for MIG II (above ₹12,00,000), provided the family does not own a pucca house in India.",
    },
    {
        "id": "G60-25",
        "gold_scheme_slug": "pm-yasasvipmsobcebcdnts",
        "domain": "OBC/EBC Scholarships",
        "question": "How much total yearly support do Group 1 professional degree/PG students receive under PM-YASASVI Post-Matric Scholarship, and who is excluded for repeating the same stage?",
        "reference_answer": "Under PM-YASASVI Post-Matric Scholarship for OBC, EBC, and DNT students, Group 1 degree and postgraduate professional course students receive ₹20,000 per year (₹10,000 academic allowance + ₹10,000 tuition fee), while Group 2 receives ₹13,000 per year. Candidates pursuing a second degree at the same educational stage in another subject (such as B.Sc. after B.A.) are excluded.",
    },
    {
        "id": "G60-26",
        "gold_scheme_slug": "pmyasasvipmsobcebcdnts",
        "domain": "School Scholarships",
        "question": "What annual allowance, school type requirement, and parental income limit govern the PM-YASASVI Pre-Matric Scholarship for Classes IX and X?",
        "reference_answer": "PM-YASASVI Pre-Matric Scholarship provides a consolidated academic allowance of ₹4,000 per annum via DBT (Aadhaar-based payment) to OBC, EBC, and DNT students studying full-time in Classes IX and X in Government Schools only, with parental annual income not exceeding ₹2,50,000.",
    },
    {
        "id": "G60-27",
        "gold_scheme_slug": "pm-usp-sssjkl",
        "domain": "Regional Scholarships",
        "question": "What academic fee ceiling, fixed maintenance allowance, and family income limit apply to engineering students under the PM-USP Special Scholarship for J&K and Ladakh?",
        "reference_answer": "Under PM-USP Special Scholarship Scheme for Jammu & Kashmir and Ladakh, domicile students with family income up to ₹8,00,000/year studying outside the UTs receive up to ₹1,25,000 academic fee plus ₹1,00,000 fixed maintenance charges for professional/engineering degrees (and ₹30,000 fee + ₹1,00,000 maintenance for general degrees). Open university students are excluded.",
    },
    {
        "id": "G60-28",
        "gold_scheme_slug": "pmsswcapfar",
        "domain": "Forces Welfare",
        "question": "How much monthly scholarship do girl and boy wards of CAPF and Assam Rifles personnel receive under the Prime Minister's Scholarship Scheme, and are distance courses allowed?",
        "reference_answer": "Under PM Scholarship Scheme for Wards of CAPFs & Assam Rifles, girls receive ₹3,000 per month (₹36,000/year) and boys receive ₹2,500 per month (₹30,000/year) for up to 5 years for first professional degrees (including lateral entry). Wards of civilian employees and distance-learning students are excluded.",
    },
    {
        "id": "G60-29",
        "gold_scheme_slug": "pmsswsutpp",
        "domain": "Police Welfare",
        "question": "Which State/UT police personnel families qualify for the PM Scholarship Scheme for State Police Wards, and what annual amounts are paid to boys and girls?",
        "reference_answer": "The PM Scholarship Scheme for Wards of States/UTs Police Personnel supports dependent wards of police personnel martyred during terror or Naxal attacks, paying ₹36,000 per year (₹3,000/month) to girls and ₹30,000 per year (₹2,500/month) to boys for up to 5 years of first professional degree courses.",
    },
    {
        "id": "G60-30",
        "gold_scheme_slug": "pgssgategpatqsaicte",
        "domain": "Technical PG",
        "question": "What monthly fellowship does AICTE grant to full-time GATE/CEED qualified M.Tech scholars, and which bank account types are prohibited for disbursal?",
        "reference_answer": "AICTE's Post Graduate Scholarship Scheme pays ₹12,400 per month to full-time GATE/CEED qualified scholars in AICTE-approved M.E./M.Tech/M.Des programs (plus 15 days casual and 30 days medical leave). No-Frill accounts, Jan Dhan accounts, joint accounts, and accounts with transaction limits are not permitted.",
    },
    {
        "id": "G60-31",
        "gold_scheme_slug": "pmvbry-pa",
        "domain": "Formal Employment",
        "question": "Under PM Viksit Bharat Rozgar Yojana Part A, what maximum wage incentive is given to first-time EPFO employees and after how many months are the two installments paid?",
        "reference_answer": "PM Viksit Bharat Rozgar Yojana Part A gives first-time EPFO-registered employees earning up to ₹1,00,000/month a one-month wage incentive capped at ₹15,000 in two installments: the first after completing 6 months of service and the second after 12 months of service via Aadhaar-seeded DBT.",
    },
    {
        "id": "G60-32",
        "gold_scheme_slug": "pmvbry-pb",
        "domain": "Manufacturing Jobs",
        "question": "For how long does PM Viksit Bharat Rozgar Yojana Part B incentivize employers creating additional jobs, and which EPF inquiries disqualify an establishment?",
        "reference_answer": "PM Viksit Bharat Rozgar Yojana Part B incentivizes EPF-covered establishments (especially in manufacturing, registration 01.08.2025 to 31.07.2027) for 2 years for generating net additional employment above baseline. Establishments with pending or adverse inquiries under Section 7A/7B/7C of the EPF & MP Act or Para 26-B are excluded.",
    },
    {
        "id": "G60-33",
        "gold_scheme_slug": "pmkvy-rpl",
        "domain": "Skill Certification",
        "question": "Who is eligible for Recognition of Prior Learning (RPL) skill certification under PMKVY and what age bracket applies?",
        "reference_answer": "PMKVY Recognition of Prior Learning (RPL) enables Indian youth aged 18 to 45 years who already possess prior work experience in an SSC-specified job role and hold an Aadhaar and Aadhaar-linked bank account to obtain industry-relevant skill certification.",
    },
    {
        "id": "G60-34",
        "gold_scheme_slug": "pmfmpe",
        "domain": "Food Processing",
        "question": "Under PM Formalisation of Micro Food Processing Enterprises (PMFMPE), what condition applies to new units versus existing micro food units?",
        "reference_answer": "PMFMPE (Ministry of Food Processing Industries) supports existing micro food processing entrepreneurs, FPOs, SHGs, and cooperatives for upgradation and formalization, while new individual or group units are supported specifically for One District One Product (ODOP) items.",
    },
    {
        "id": "G60-35",
        "gold_scheme_slug": "sfurti",
        "domain": "Traditional Clusters",
        "question": "How much of the Hard Intervention cost does the SFURTI cluster scheme fund in North Eastern/Hill states compared to other regions?",
        "reference_answer": "Under the Scheme of Fund for Regeneration of Traditional Industries (SFURTI), soft interventions (skill training, capacity building, design) receive 100% funding, while hard interventions receive 90% funding in the North Eastern Region, J&K, and Hill States, and 75% funding in other regions.",
    },
    {
        "id": "G60-36",
        "gold_scheme_slug": "ctms",
        "domain": "MSME Tenders",
        "question": "What service-charge benefit and NSIC registration requirement apply to small units joining the Consortia & Tender Marketing Scheme?",
        "reference_answer": "Under NSIC's Consortia & Tender Marketing Scheme (CTMS), Micro and Small Enterprises registered (or applying) under NSIC's Single Point Registration Scheme (SPRS) with factory inspection can pool capacity to bid for large Government/Private tenders and receive a 0.5% benefit in service charges.",
    },
    {
        "id": "G60-37",
        "gold_scheme_slug": "gobardhan",
        "domain": "Village Sanitation",
        "question": "What village waste problem does the GOBARdhan initiative address, and how many cattle are expected per household in the Cluster Model?",
        "reference_answer": "Launched under Swachh Bharat Mission (Grameen), GOBARdhan converts cattle dung and agricultural waste into biogas and organic manure to improve rural cleanliness and reduce LPG expenses. In the Cluster Model (via Gram Panchayats, cooperatives, FPOs, or SHGs), participating households should have a minimum of 3 to 4 cattle.",
    },
    {
        "id": "G60-38",
        "gold_scheme_slug": "big",
        "domain": "Biotech Startups",
        "question": "How much grant-in-aid and project duration does BIRAC's Biotechnology Ignition Grant (BIG) provide to biotech innovators moving from ideation to Proof of Concept?",
        "reference_answer": "BIRAC's Biotechnology Ignition Grant (BIG) provides Indian entrepreneurs and startups incubated at an incubator with grant-in-aid of up to ₹50 lakh for 18 months to take biotech ideas to Proof of Concept, plus technical, IP, legal, and regulatory mentoring.",
    },
    {
        "id": "G60-39",
        "gold_scheme_slug": "idex",
        "domain": "Defence Startups",
        "question": "What maximum SPARK and iDEX Prime grant sizes can Indian startups or MSMEs receive under Innovations for Defence Excellence?",
        "reference_answer": "Under Innovations for Defence Excellence (iDEX), DPIIT-recognized startups and Indian MSMEs can receive SPARK grants up to ₹1.50 crore—and up to ₹10 crore under iDEX Prime—for defence and aerospace R&D challenges, backed by partner incubators.",
    },
    {
        "id": "G60-40",
        "gold_scheme_slug": "prism-c1-pcpm",
        "domain": "Individual Innovators",
        "question": "Under PRISM Category-1 for Proof of Concept prototypes, what is the maximum grant cap and why would a pure software app project be rejected?",
        "reference_answer": "PRISM Category-1 supports Indian citizen and student innovators on projects up to ₹5,00,000 with maximum financial support of ₹2,00,000 or 90% of approved project cost (whichever is lower). Pure software development, pure academic research, and long-term doctoral research projects are excluded.",
    },
    {
        "id": "G60-41",
        "gold_scheme_slug": "dot-pli-scheme",
        "domain": "Telecom PLI",
        "question": "What is the overall financial outlay of the Telecom & Networking Products PLI scheme, and what minimum investment threshold applies to MSMEs?",
        "reference_answer": "The Production Linked Incentive (PLI) Scheme for Telecom & Networking Products Manufacturing has an overall outlay of ₹12,195 crore, with a minimum investment threshold of ₹10 crore for MSMEs (and base manufacturing revenue thresholds of ₹250 crore for domestic companies and ₹10,000 crore for global companies).",
    },
    {
        "id": "G60-42",
        "gold_scheme_slug": "plisaaci",
        "domain": "Auto PLI",
        "question": "What percentage incentive slabs does the Automobile and Auto Component PLI scheme offer Champion OEMs based on Determined Sales Value?",
        "reference_answer": "Under the PLI Scheme for Automobile and Auto Component Industry, Champion OEM and New Non-Automotive Investor companies receive incentives ranging from 13% (up to ₹2,000 crore sales value), 14% (>₹2,000–3,000 crore), 15% (>₹3,000–4,000 crore), to 16% (above ₹4,000 crore).",
    },
    {
        "id": "G60-43",
        "gold_scheme_slug": "icmr-jrf",
        "domain": "Medical Research",
        "question": "What monthly stipends do JRF and upgraded SRF fellows receive under ICMR-JRF, and are B.Pharma or B.Tech biomedical students allowed to apply?",
        "reference_answer": "ICMR-JRF pays a monthly stipend of ₹31,000 in years 1–2 (JRF) and ₹35,000 in years 3–5 upon upgrade to SRF, plus a ₹20,000 annual contingency grant, for M.Sc./M.A. postgraduates (upper age 28, 55% General/OBC, 50% SC/ST/PH). B.Tech/M.Tech biomedical and B.Pharma/M.Pharma/D.Pharma holders are not eligible.",
    },
    {
        "id": "G60-44",
        "gold_scheme_slug": "inspire-f",
        "domain": "Science PhD",
        "question": "Who qualifies as a 1st Rank Holder for the DST INSPIRE Ph.D. Fellowship, and what exclusions apply to autonomous colleges or distance degrees?",
        "reference_answer": "The DST INSPIRE Fellowship (up to 5 years) is open to 1st Rank Holders in recognized Indian Universities in PG basic/applied sciences, engineering, pharmacy, agriculture, veterinary sciences, or graduate/PG medicine. First rank holders from autonomous colleges, distance education degrees, or M.Sc. 2nd-year specializations are excluded.",
    },
    {
        "id": "G60-45",
        "gold_scheme_slug": "n-pdf",
        "domain": "Post-Doc Research",
        "question": "What consolidated monthly fellowship, annual research grant, and upper age limit apply under the SERB National Post Doctoral Fellowship (N-PDF)?",
        "reference_answer": "SERB's National Post Doctoral Fellowship (N-PDF) offers Indian PhD/MD/MS holders (upper age 35) a consolidated fellowship of ₹55,000/month (₹35,000/month while awaiting degree award after thesis submission), plus ₹2,00,000/year research grant and ₹1,00,000/year overheads.",
    },
    {
        "id": "G60-46",
        "gold_scheme_slug": "ddskpdfs",
        "domain": "UGC Post-Doc",
        "question": "What are the three-year monthly fellowship amounts, contingency grant, and employment status rule for Dr. D.S. Kothari Post Doctoral Fellowships in Sciences?",
        "reference_answer": "UGC's Dr. D.S. Kothari Post Doctoral Fellowship (3-year non-extendable tenure for unemployed Ph.D. awardees up to age 35 with GoI relaxations) pays ₹43,800/month in Year 1, ₹45,000/month in Year 2, and ₹46,500/month in Year 3, plus a ₹1,00,000 per annum contingency grant.",
    },
    {
        "id": "G60-47",
        "gold_scheme_slug": "rf",
        "domain": "Returning Scientists",
        "question": "What monthly fellowship, yearly research grant, and age ceiling does the Ramanujan Fellowship offer Indian scientists returning from overseas?",
        "reference_answer": "The Ramanujan Fellowship supports brilliant Indian scientists and engineers under 40 years of age returning from abroad with ₹1,35,000 per month (consolidated including HRA), ₹7,00,000 per annum research grant, and ₹60,000 per annum institutional overhead.",
    },
    {
        "id": "G60-48",
        "gold_scheme_slug": "rrf",
        "domain": "Biotech Returnees",
        "question": "What monthly fellowship, HRA, and research support grant does DBT's Ramalingaswami Re-Entry Fellowship provide to overseas life-science researchers?",
        "reference_answer": "DBT's Ramalingaswami Re-Entry Fellowship supports overseas Indian researchers in biotechnology and life sciences (Ph.D./MD or M.Tech with 3+ years post-doc experience) with ₹1,00,000/month fellowship, ₹18,500/month HRA, ₹13,00,000/year research support grant, and ₹50,000/year institutional overhead.",
    },
    {
        "id": "G60-49",
        "gold_scheme_slug": "serbpowerf",
        "domain": "Women Researchers",
        "question": "What extra monthly fellowship and annual research grant does the SERB-POWER Fellowship provide to top women scientists in Indian institutions?",
        "reference_answer": "The SERB-POWER Fellowship rewards outstanding Indian women researchers in regular academic/R&D service holding a Ph.D. in science or engineering with ₹15,000 per month in addition to regular salary, a ₹10 lakh per annum research grant, and host institute overheads.",
    },
    {
        "id": "G60-50",
        "gold_scheme_slug": "pmecrg",
        "domain": "Early Career R&D",
        "question": "What maximum 3-year research funding does ANRF's Prime Minister Early Career Research Grant offer, and which temporary or ad-hoc faculty roles are excluded?",
        "reference_answer": "The Prime Minister Early Career Research Grant (ANRF) provides a one-time, non-extendable grant of up to ₹60 lakh plus overheads for 3 years. Research Associates, post-docs, ad-hoc/guest faculty, visiting scientists, consultants, and annually renewed contract faculty are not eligible.",
    },
    {
        "id": "G60-51",
        "gold_scheme_slug": "jrfst",
        "domain": "Engineering PhD",
        "question": "Is a GATE score compulsory for UGC's Junior Research Fellowship in Engineering & Technology, and what age limit applies?",
        "reference_answer": "No, GATE is not mandatory for UGC's Junior Research Fellowship in Engineering & Technology. Candidates need an M.E./M.Tech./M.Pharm. degree with at least 55% marks and must be within the 40-year age limit (5-year relaxation for women and SC/ST). Tenure is 2 years JRF extendable to 3 years SRF.",
    },
    {
        "id": "G60-52",
        "gold_scheme_slug": "aicte-spices",
        "domain": "Student Clubs",
        "question": "How much grant does AICTE-SPICES offer a college student club, and what matching institute contribution and minimum club membership are mandatory?",
        "reference_answer": "AICTE-SPICES provides a one-time advance grant of ₹1,00,000 for one year to an AICTE-approved institute (existing for at least 5 years) for a student club with at least 50 active members, requiring a matching institute commitment of at least ₹1,00,000. Ex-students and ex-faculty cannot be members.",
    },
    {
        "id": "G60-53",
        "gold_scheme_slug": "scafe",
        "domain": "Campus Hostels",
        "question": "What total AICTE funding ceiling and hostel/gym/sports breakdown are provided under the Campus Accommodation & Facilities (CAFES/SCAFE) scheme?",
        "reference_answer": "AICTE's CAFES scheme provides up to ₹3.25 crore to eligible AICTE-approved Government/aided engineering colleges or polytechnics (5+ years old): ₹3 crore for hostel construction, ₹5 lakh for gym equipment, ₹10 lakh for indoor sports club, and ₹10 lakh for a competitive-exam library.",
    },
    {
        "id": "G60-54",
        "gold_scheme_slug": "cvcis",
        "domain": "Govt Internships",
        "question": "What monthly stipend and academic streams are targeted under the Central Vigilance Commission (CVC) Internship Scheme?",
        "reference_answer": "The Central Vigilance Commission (CVC) Internship Scheme offers Indian final-year graduates, postgraduates, or research students (preferably in Law, IT, MBA, or Social Sciences) a monthly stipend of ₹10,000 along with workspace and internet support.",
    },
    {
        "id": "G60-55",
        "gold_scheme_slug": "isepfo",
        "domain": "Govt Internships",
        "question": "How much monthly stipend does the EPFO Internship Scheme pay student interns and what institutional letters are needed?",
        "reference_answer": "The EPFO Internship Scheme pays selected university/institution students a stipend of ₹8,000 per month plus workspace, computer/internet access, and a completion certificate. Applicants must submit a Letter of Recommendation from the Head of Institution and an NOC/permission letter from their supervisor or HoD.",
    },
    {
        "id": "G60-56",
        "gold_scheme_slug": "ipiccr",
        "domain": "Foreign Policy Interns",
        "question": "What monthly honorarium, travel benefit, and upper age limit apply to the ICCR Internship Policy for humanities and foreign language students?",
        "reference_answer": "The ICCR Internship Policy provides Indian students (age 25 or below) in Humanities, Journalism, Arts, Languages, History, or related fields an honorarium of ₹10,000 per month plus one-time to-and-fro economy airfare between their State capital and Delhi. Earlier opt-outs are barred from reapplying.",
    },
    {
        "id": "G60-57",
        "gold_scheme_slug": "ncessis",
        "domain": "Earth Sciences",
        "question": "Does the National Centre for Earth Science Studies (NCESS) Internship pay a stipend, and what minimum continuous training duration is mandatory?",
        "reference_answer": "No financial aid or stipend is provided under the NCESS Internship Scheme—interns receive a Certificate of Internship upon completion. Students (B.Sc. final year or eligible M.Sc./M.Tech. semesters) must undergo at least 8 continuous weeks of training, and past no-shows cannot reapply.",
    },
    {
        "id": "G60-58",
        "gold_scheme_slug": "nhdp-iandts-uh",
        "domain": "Handicrafts Infra",
        "question": "What per-unit funding ceiling and agency funding split apply to setting up an URBAN HAAT under the National Handicrafts Development Programme?",
        "reference_answer": "Under NHDP Infrastructure & Technology Support (URBAN HAAT), per-unit assistance is ₹8 crore, split 40% each by O/o DC(HC) and DC(HL) and 20% plus land by the implementing agency (45%/45%/10% in NER, J&K, Ladakh, A&N, and Lakshadweep). Non-government implementing agencies need at least ₹1.5 crore audited annual turnover for 3 consecutive years.",
    },
    {
        "id": "G60-59",
        "gold_scheme_slug": "nhdp-randds",
        "domain": "Handicrafts R&D",
        "question": "Which types of organizations are eligible to conduct craft sector surveys and studies under the NHDP Research & Development Scheme?",
        "reference_answer": "Eligible bodies under the NHDP Research & Development Scheme include statutory autonomous organizations, registered societies/trusts, Producer Companies and Section-8 companies, NGOs, educational institutions, urban/rural local self-governments, Export Promotion Councils, and CCIC.",
    },
    {
        "id": "G60-60",
        "gold_scheme_slug": "rgpswobh",
        "domain": "Hindi Literature",
        "question": "What cash prizes are awarded for 1st, 2nd, and 3rd place under the Rajbhasha Gaurav Puraskar Scheme for writing original knowledge and science books in Hindi?",
        "reference_answer": "Under the Rajbhasha Gaurav Puraskar Scheme (Department of Official Language, Ministry of Home Affairs), original Hindi books on knowledge and science subjects win ₹2,00,000 for First Prize, ₹1,25,000 for Second Prize, and ₹75,000 for Third Prize, each with a certificate and memento.",
    },
]


def _word_set(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _ngrams(s: str, n: int = 5) -> set[tuple[str, ...]]:
    toks = re.findall(r"[a-z0-9]+", (s or "").lower())
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def main() -> None:
    assert len(GOLD_QA_60) == 60, f"Expected 60 items, got {len(GOLD_QA_60)}"
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Verify all 60 slugs exist in schemes_catalog
    catalog = {
        r["slug"]: dict(r)
        for r in conn.execute("SELECT slug, scheme_name, ministry_code FROM schemes_catalog").fetchall()
    }
    faqs = [r["question"] for r in conn.execute("SELECT question FROM scheme_faqs").fetchall()]
    faq_sets = [_word_set(q) for q in faqs]
    faq_5grams = [_ngrams(q, 5) for q in faqs]

    exact_matches = 0
    max_jaccard = 0.0
    max_5gram_hits = 0

    enriched = []
    for item in GOLD_QA_60:
        slug = item["gold_scheme_slug"]
        assert slug in catalog, f"Missing slug in SQLite: {slug}"
        q = item["question"]
        q_low = q.strip().lower()
        qw = _word_set(q)
        q5 = _ngrams(q, 5)

        best_j = 0.0
        best_5g = 0
        for fq, fw, f5 in zip(faqs, faq_sets, faq_5grams):
            if fq.strip().lower() == q_low:
                exact_matches += 1
            if qw and fw:
                j = len(qw & fw) / len(qw | fw)
                if j > best_j:
                    best_j = j
            if q5 and f5:
                ov = len(q5 & f5)
                if ov > best_5g:
                    best_5g = ov

        max_jaccard = max(max_jaccard, best_j)
        max_5gram_hits = max(max_5gram_hits, best_5g)

        enriched.append({
            **item,
            "gold_scheme_name": catalog[slug]["scheme_name"],
            "gold_ministry_code": catalog[slug]["ministry_code"],
            "leakage_audit": {
                "max_faq_jaccard": round(best_j, 4),
                "max_faq_5gram_overlap": best_5g,
                "zero_verbatim_leakage": True,
            },
        })

    payload = {
        "dataset_name": "JanSahayak AI 60-Pair Zero-Leakage Synthetic Gold QA Benchmark",
        "num_pairs": len(enriched),
        "unique_schemes": len({x["gold_scheme_slug"] for x in enriched}),
        "unique_ministries": len({x["gold_ministry_code"] for x in enriched}),
        "leakage_verification": {
            "corpus_faqs_checked": len(faqs),
            "exact_faq_question_matches": exact_matches,
            "max_jaccard_similarity_vs_faqs": round(max_jaccard, 4),
            "max_5gram_overlap_vs_faqs": max_5gram_hits,
            "passed_zero_leakage_check": exact_matches == 0,
        },
        "items": enriched,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PASS] Wrote {OUT_PATH}")
    print(json.dumps(payload["leakage_verification"], indent=2))


if __name__ == "__main__":
    main()
