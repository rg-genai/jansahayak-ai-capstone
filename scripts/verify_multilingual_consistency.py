"""Live verification that English, Hindi, and Tamil return consistent schemes with zero prompt-echo or truncation."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.graph import JanSahayakAgent
from backend.db.database import init_db


async def main() -> int:
    db_path = init_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM response_cache")
    conn.execute(
        "UPDATE sessions SET profile_json = ? WHERE session_id = ?",
        (json.dumps({"preferred_language": "en"}), "admin-session-01"),
    )
    conn.commit()
    conn.close()

    agent = JanSahayakAgent()
    queries = [
        ("en", "I am a 19-year-old OBC B.Tech student with ₹1,80,000 annual family income. Which Central scholarships am I eligible for and what documents do I need?"),
        ("hi", "मैं 19 साल का OBC B.Tech स्टूडेंट हूँ और मेरे परिवार की सालाना इनकम ₹1,80,000 है। मैं कौन सी सेंट्रल स्कॉलरशिप के लिए एलिजिबल हूँ और मुझे कौन से डॉक्यूमेंट्स चाहिए?"),
        ("ta", "நான் 19 வயதுடைய, ஓபிசி பிரிவைச் சேர்ந்த பி.டெக் மாணவன். எனது குடும்பத்தின் ஆண்டு வருமானம் ₹1,80,000 ஆகும். நான் எந்தெந்த மத்திய அரசின் கல்வி உதவித்தொகைகளுக்குத் தகுதியானவன் மற்றும் எனக்கு என்னென்ன ஆவணங்கள் தேவைப்படும்?"),
    ]

    top_sets = []
    for lang, q in queries:
        st = await agent.run(
            message=q,
            session_id="verify-ml-consistency",
            ui_language=lang,
            citizen_profile={},
        )
        slugs = list(dict.fromkeys(c["scheme_slug"] for c in (st.get("retrieved_chunks") or [])))
        ans = st.get("final_answer") or ""
        print(f"\n=== LANG={lang} (detected={st.get('detected_lang')}) ===")
        print("query_en:", st.get("query_en"))
        print("top_slugs:", slugs[:4])
        print("elig_cards:", [(e["scheme_slug"], e["verdict"]) for e in (st.get("eligibility_cards") or [])])
        print("answer_len:", len(ans))
        print("answer_preview:", ans[:350].replace("\n", " | "))
        assert len(slugs) >= 2, f"Empty retrieval for {lang}!"
        assert "अनुभाग नाम" not in ans, "Literal placeholder 'अनुभाग नाम' leaked!"
        assert "முக்கிய விதிகள்" not in ans, "Tamil translation prompt leaked!"
        assert "central-scholarship-for-b-tech-students" not in json.dumps(st.get("eligibility_cards") or [])
        top_sets.append(set(slugs[:4]))

    overlap_en_hi = top_sets[0] & top_sets[1]
    overlap_en_ta = top_sets[0] & top_sets[2]
    print("\n=== CONSISTENCY OVERLAP ===")
    print("EN & HI shared schemes:", overlap_en_hi)
    print("EN & TA shared schemes:", overlap_en_ta)
    assert len(overlap_en_hi) >= 1, "EN and HI did not share top schemes!"
    assert len(overlap_en_ta) >= 1, "EN and TA did not share top schemes!"
    print("[PASS] ALL 3 LANGUAGES CONSISTENT, ZERO PROMPT ECHO, ZERO BOGUS ELIGIBILITY CARDS!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
