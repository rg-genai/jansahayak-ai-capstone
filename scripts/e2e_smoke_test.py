"""Milestone M7 Live End-to-End Smoke Test: boots real FastAPI + Vite preview servers and verifies every user journey over HTTP."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def wait_for_url(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    python_exe = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    backend_port = 8011
    frontend_port = 5174
    api_base = f"http://127.0.0.1:{backend_port}"
    ui_base = f"http://127.0.0.1:{frontend_port}"

    env = os.environ.copy()
    env["MOCK_CPGRAMS_BASE_URL"] = f"{api_base}/mock-cpgrams/v1"

    backend_log = (PROJECT_ROOT / "data" / "e2e_backend.log").open("w", encoding="utf-8")
    frontend_log = (PROJECT_ROOT / "data" / "e2e_frontend.log").open("w", encoding="utf-8")

    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--workers", "1"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
    )
    frontend_proc = subprocess.Popen(
        ["cmd", "/c", f"npx vite preview --host 127.0.0.1 --port {frontend_port}"],
        cwd=str(PROJECT_ROOT / "frontend"),
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
    )

    try:
        print(f"[1/9] Waiting for FastAPI ({api_base}) & Vite Preview ({ui_base})...")
        assert wait_for_url(f"{api_base}/api/health", timeout=35.0), "Backend failed to start"
        assert wait_for_url(ui_base, timeout=25.0), "Frontend preview failed to start"

        # 1. Health check & Frontend HTML check
        health = httpx.get(f"{api_base}/api/health", timeout=10.0).json()
        assert health["status"] == "ok"
        assert health["counts"]["schemes"] == 649
        assert health["counts"]["ministries"] == 51
        assert health["index_ready"] is True
        ui_html = httpx.get(ui_base, timeout=10.0).text
        assert "JanSahayak AI" in ui_html
        print(f"  [PASS] Health OK ({health['counts']['schemes']} schemes, {health['counts']['chunks']} chunks) & Frontend HTML served.")

        sess_id = f"smoke-{uuid.uuid4().hex[:6]}"
        client = httpx.Client(base_url=api_base, timeout=90.0)

        # 2. English RAG QA via live SSE /api/chat/stream (verifies CRLF SSE frame delivery!)
        print("[2/9] Live English RAG QA via SSE /api/chat/stream (PM-KISAN)...")
        adm_tok_pre = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        adm_hdrs_pre = {"Authorization": f"Bearer {adm_tok_pre}"}
        with client.stream(
            "POST",
            "/api/chat/stream",
            headers=adm_hdrs_pre,
            json={
                "session_id": sess_id,
                "message": "What annual financial benefit do farmers receive under Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)?",
                "language": "en",
                "bypass_cache": True,
            },
        ) as r_sse:
            assert r_sse.status_code == 200
            raw_sse = r_sse.read().decode("utf-8").replace("\r\n", "\n")
        import json as _json
        d_en = None
        for blk in raw_sse.split("\n\n"):
            lines = [ln.strip() for ln in blk.split("\n") if ln.strip()]
            ev_name = next((ln[6:].strip() for ln in lines if ln.startswith("event:")), "")
            data_str = "\n".join(ln[5:].strip() for ln in lines if ln.startswith("data:"))
            if ev_name == "final" and data_str:
                d_en = _json.loads(data_str)
        assert d_en is not None, f"SSE stream did not emit final event! Raw: {raw_sse[:400]}"
        assert d_en["status"] == "ok"
        assert len(d_en["citations"]) >= 1
        assert any("myscheme.gov.in" in c["source_url"] for c in d_en["citations"])
        assert "6,000" in d_en["answer"] or "6000" in d_en["answer"]
        print(f"  [PASS] SSE English RAG QA OK | trace={d_en['trace_id']} | latency={d_en['latency_ms']}ms | citations={len(d_en['citations'])}")

        # 3. Exact Cache Hit check
        print("[3/9] Live Two-Tier Exact Cache Hit check...")
        r_cache = client.post(
            "/api/chat",
            json={
                "session_id": sess_id,
                "message": "What annual financial benefit do farmers receive under Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)?",
                "language": "en",
                "bypass_cache": False,
            },
        )
        assert r_cache.status_code == 200
        d_cache = r_cache.json()
        assert d_cache["cache_hit"] in ("exact", "semantic"), f"Expected cache hit, got {d_cache['cache_hit']}"
        print(f"  [PASS] Cache hit={d_cache['cache_hit']} in {d_cache['latency_ms']}ms!")

        # 4. Hindi Multilingual Query
        print("[4/9] Live Hindi Multilingual Query...")
        r_hi = client.post(
            "/api/chat",
            json={
                "session_id": sess_id,
                "message": "पीएम किसान सम्मान निधि योजना में किसानों को सालाना कितने पैसे मिलते हैं?",
                "language": "hi",
                "bypass_cache": True,
            },
        )
        assert r_hi.status_code == 200, r_hi.text
        d_hi = r_hi.json()
        assert d_hi["detected_lang"] == "hi"
        assert len(d_hi["citations"]) >= 1
        print(f"  [PASS] Hindi Query OK | detected_lang={d_hi['detected_lang']} | latency={d_hi['latency_ms']}ms")

        # 5. PII Aadhaar Masking live end-to-end
        print("[5/9] Live PII Aadhaar Masking check...")
        adm_tok_pre = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        adm_hdrs_pre = {"Authorization": f"Bearer {adm_tok_pre}"}
        r_pii = client.post(
            "/api/chat",
            headers=adm_hdrs_pre,
            json={
                "session_id": sess_id,
                "message": "Am I eligible for PM-KISAN? My Aadhaar is 4512 8891 3342.",
                "language": "en",
                "bypass_cache": True,
            },
        )
        assert r_pii.status_code == 200, r_pii.text
        d_pii = r_pii.json()
        assert "4512 8891 3342" not in d_pii["answer"]
        assert any("pii_masked:AADHAAR" in fl for fl in d_pii["guardrail_flags"])
        tr_pii = client.get(f"/api/traces/{d_pii['trace_id']}", headers=adm_hdrs_pre).json()["trace"]
        assert "4512 8891 3342" not in tr_pii["user_query_masked"]
        assert "[AADHAAR_MASKED:XXXX-XXXX-3342]" in tr_pii["user_query_masked"]
        print(f"  [PASS] PII Aadhaar masked in response & trace ({d_pii['trace_id']}).")

        # 6. HITL Grievance Flow: Draft -> Unconfirmed Blocked (400) -> Confirm (200) -> Track
        print("[6/9] Live HITL Grievance Flow (Draft -> Block -> Confirm -> Track)...")
        r_draft = client.post(
            "/api/grievances/draft",
            json={
                "scheme_name": "Pradhan Mantri Kisan Samman Nidhi",
                "ministry": "Ministry Of Agriculture and Farmers Welfare",
                "issue_summary": "PM-KISAN installment delayed for 2 cycles despite completed e-KYC.",
                "state": "Uttar Pradesh",
                "district": "Lucknow",
                "session_id": sess_id,
            },
        )
        assert r_draft.status_code == 200
        draft = r_draft.json()["draft"]
        assert draft["ministry_code"] == "MOAFW"
        assert draft["char_count"] <= 2000

        r_block = client.post(f"/api/grievances/{draft['draft_id']}/confirm", json={"confirmed": False})
        assert r_block.status_code == 400

        r_conf = client.post(f"/api/grievances/{draft['draft_id']}/confirm", json={"confirmed": True})
        assert r_conf.status_code == 200
        receipt = r_conf.json()["receipt"]
        reg_no = receipt["registration_number"]
        assert reg_no.startswith("MOAFW/E/2026/")
        assert receipt["assisted_handoff_packet"]["portal_url"] == "https://pgportal.gov.in/"

        r_track = client.get("/api/grievances/track", params={"registration_number": reg_no})
        assert r_track.status_code == 200
        assert r_track.json()["found"] is True
        print(f"  [PASS] HITL Draft -> 400 Block -> 200 Confirm ({reg_no}) -> Track OK.")

        # 7. Admin Login + RBAC + Traces & Export API
        print("[7/9] Live Admin/Citizen RBAC + /api/traces & export check...")
        cit_tok = client.post("/api/auth/login", json={"username": "priya", "password": "citizen123"}).json()["access_token"]
        adm_tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        assert client.get("/api/traces", headers={"Authorization": f"Bearer {cit_tok}"}).status_code == 403
        adm_hdrs = {"Authorization": f"Bearer {adm_tok}"}
        r_tr = client.get("/api/traces", params={"limit": 10}, headers=adm_hdrs)
        assert r_tr.status_code == 200
        assert r_tr.json()["total"] >= 4
        r_exp = client.get(f"/api/traces/{d_en['trace_id']}/export", params={"format": "md"}, headers=adm_hdrs)
        assert r_exp.status_code == 200 and d_en["trace_id"] in r_exp.text
        print(f"  [PASS] RBAC (Citizen=403, Admin=200) + /api/traces & MD export OK | total_traces={r_tr.json()['total']}")

        # 8. Evals Summary & Export API
        print("[8/9] Live /api/evals/summary & export check...")
        r_ev = client.get("/api/evals/summary", headers=adm_hdrs)
        assert r_ev.status_code == 200
        ev_data = r_ev.json()
        assert ev_data["available_reports"] == 4, f"Expected 4/4 eval reports, got {ev_data['available_reports']}"
        r_ev_exp = client.get("/api/evals/export/retrieval_ablation", params={"format": "md"}, headers=adm_hdrs)
        assert r_ev_exp.status_code == 200
        print(f"  [PASS] /api/evals/summary & export OK ({ev_data['available_reports']}/4 real reports loaded).")

        # 9. DPDP Right to Erasure
        print("[9/9] Live DPDP DELETE /api/sessions/{id} check...")
        r_del = client.delete(f"/api/sessions/{sess_id}")
        assert r_del.status_code == 200
        assert r_del.json()["status"] == "erased"
        print("  [PASS] DPDP Right to Erasure verified.")

        print("\n=== ALL 9 LIVE END-TO-END SMOKE TESTS PASSED! ===")
        return 0
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        for p in (backend_proc, frontend_proc):
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        backend_log.close()
        frontend_log.close()


if __name__ == "__main__":
    sys.exit(main())
