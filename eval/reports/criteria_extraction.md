# Eligibility criteria extraction accuracy

Stored LLM extractions vs hand labels (`eval/criteria_gold.json`). `dev` = schemes used while tuning the prompt; `heldout` = random sample never seen before labelling.

| Field | heldout (n=19) | dev (n=11) | all (n=30) |
|---|---|---|---|
| applicant_type | 94.7% | 90.9% | 93.3% |
| groups | 84.2% | 100.0% | 90.0% |
| education_stages | 84.2% | 90.9% | 86.7% |
| study_location | 100.0% | 100.0% | 100.0% |
| required_institution *(text-verified)* | 100.0% | 100.0% | 100.0% |
| required_states | 94.7% | 100.0% | 96.7% |
| gender | 100.0% | 100.0% | 100.0% |
| age_min *(text-verified)* | 94.7% | 100.0% | 96.7% |
| age_max *(text-verified)* | 89.5% | 100.0% | 93.3% |
| income_max_inr *(text-verified)* | 100.0% | 100.0% | 100.0% |
| social_categories *(text-verified)* | 89.5% | 90.9% | 90.0% |
| requires_bpl *(text-verified)* | 100.0% | 100.0% | 100.0% |
| requires_disability *(text-verified)* | 94.7% | 100.0% | 96.7% |
| **Text-verified fields** | **95.5%** | **98.7%** | **96.7%** |
| **Model-judgement fields** | **93.0%** | **97.0%** | **94.4%** |
| **All fields** | **94.3%** | **97.9%** | **95.6%** |

## Errors

| Scheme | Set | Field | Extracted | Acceptable |
|---|---|---|---|---|
| dacssiselosobcebc | dev | social_categories | `["OBC"]` | `[["OBC", "EBC"]]` |
| pm-yasasvitcceobcebcdnts | dev | applicant_type | `"institution"` | `["individual"]` |
| pm-yasasvitcceobcebcdnts | dev | education_stages | `["class_11_12"]` | `[["undergraduate", "postgraduate"], ["undergraduate", "postgraduate", "doctoral"]]` |
| ngra | heldout | groups | `["Farmer", "Differently Abled", "Entrepreneur", "MSME", "Researcher", "Worker", "Youth"]` | `{"core": ["Farmer"], "allowed": ["Farmer", "Worker", "Entrepreneur"]}` |
| sak-dip | heldout | education_stages | `["school", "class_11_12", "undergraduate", "postgraduate", "doctoral"]` | `[["undergraduate"], ["class_11_12"], ["class_11_12", "undergraduate"]]` |
| dsctassgcsccm | heldout | required_states | `["Kerala", "Karnataka", "Tamil Nadu", "Goa", "Andhra Pradesh", "Odisha", "West Bengal", "Madhya Pradesh", "Maharashtra", "Chhattisgarh", "Jharkhand", "Tripura", "Assam", "Nagaland", "Manipur", "Meghalaya", "Mizoram", "Arunachal Pradesh", "Sikkim", "Ladakh", "Delhi", "Puducherry", "Andaman and Nicobar Islands", "Lakshadweep"]` | `[[]]` |
| jrfbio | heldout | education_stages | `["postgraduate"]` | `[["postgraduate", "doctoral"], ["doctoral"]]` |
| jrfbio | heldout | age_max | `28` | `[33]` |
| jrfbio | heldout | social_categories | `["SC", "ST", "EWS"]` | `[[]]` |
| pmkvy-stt | heldout | groups | `["Youth", "Worker", "Entrepreneur", "Student"]` | `{"core": ["Youth"], "allowed": ["Youth", "Worker", "Student"]}` |
| stfhrdphr | heldout | education_stages | `["postgraduate", "doctoral"]` | `[[]]` |
| rpsy | heldout | age_min | `18` | `[null]` |
| rpsy | heldout | age_max | `59` | `[null]` |
| tgsctclvccmuo | heldout | groups | `["Student", "Researcher", "Worker"]` | `{"core": [], "allowed": ["Researcher", "Worker"]}` |
| tgsctclvccmuo | heldout | social_categories | `["SC", "ST", "OBC"]` | `[[]]` |
| tgsctclvccmuo | heldout | requires_disability | `true` | `[null]` |
| lbssf-els | heldout | applicant_type | `"individual"` | `["both"]` |
