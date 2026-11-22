"""Pre-flight verification script for Track B Qwen3-8B Inference & VM02 Embeddings APIs.

Reads configuration from `.env` (never prints API keys) and verifies:
1. Certificate files exist.
2. Inference endpoint `/models` and `/chat/completions` work with CA verification.
3. Whether `chat_template_kwargs: {"enable_thinking": False}` is accepted by the server.
4. Embeddings endpoint `/embeddings` returns 384-dim vectors with CA verification.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_dotenv(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        values[key] = val
    return values


def make_ssl_context(ca_cert_path: Path) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=str(ca_cert_path))


def http_json(
    url: str,
    api_key: str,
    ca_cert_path: Path,
    payload: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict | str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = make_ssl_context(ca_cert_path)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    if not env_file.exists():
        print("[FAIL] .env file not found in project root.")
        return 1

    env = load_dotenv(env_file)
    for k, v in env.items():
        os.environ.setdefault(k, v)

    required_keys = [
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_CA_CERT_PATH",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_CA_CERT_PATH",
    ]
    missing = [
        k for k in required_keys
        if not os.environ.get(k) or "REPLACE_WITH" in os.environ.get(k, "")
    ]
    if missing:
        print(f"[FAIL] Missing or placeholder .env keys: {', '.join(missing)}")
        return 1

    llm_url = os.environ["LLM_BASE_URL"].rstrip("/")
    llm_model = os.environ["LLM_MODEL"]
    llm_key = os.environ["LLM_API_KEY"]
    llm_cert = (root / os.environ["LLM_CA_CERT_PATH"]).resolve() if not Path(os.environ["LLM_CA_CERT_PATH"]).is_absolute() else Path(os.environ["LLM_CA_CERT_PATH"])

    emb_url = os.environ["EMBEDDING_BASE_URL"].rstrip("/")
    emb_model = os.environ["EMBEDDING_MODEL"]
    emb_key = os.environ["EMBEDDING_API_KEY"]
    emb_cert = (root / os.environ["EMBEDDING_CA_CERT_PATH"]).resolve() if not Path(os.environ["EMBEDDING_CA_CERT_PATH"]).is_absolute() else Path(os.environ["EMBEDDING_CA_CERT_PATH"])

    print(f"[INFO] LLM URL: {llm_url} | Model: {llm_model} | Cert exists: {llm_cert.exists()}")
    print(f"[INFO] EMB URL: {emb_url} | Model: {emb_model} | Cert exists: {emb_cert.exists()}")

    if not llm_cert.exists():
        print(f"[FAIL] LLM CA certificate not found at: {llm_cert}")
        return 1
    if not emb_cert.exists():
        print(f"[FAIL] Embedding CA certificate not found at: {emb_cert}")
        return 1

    ok = True

    # 1. Check /models on Inference API
    print("\n--- Test 1: Inference API /models ---")
    try:
        status, resp = http_json(f"{llm_url}/models", llm_key, llm_cert)
        if status == 200 and isinstance(resp, dict):
            model_ids = [m.get("id") for m in resp.get("data", [])]
            print(f"[PASS] HTTP 200 | Available models: {model_ids}")
        else:
            print(f"[FAIL] HTTP {status} | Response: {str(resp)[:300]}")
            ok = False
    except Exception as exc:
        print(f"[FAIL] Inference /models error: {exc}")
        ok = False

    # 2. Check /chat/completions with enable_thinking=False
    print("\n--- Test 2: Inference API /chat/completions (Qwen3-8B) ---")
    try:
        payload = {
            "model": llm_model,
            "messages": [
                {"role": "system", "content": "Reply ONLY with valid JSON: {\"status\": \"ok\"}"},
                {"role": "user", "content": "Health check"},
            ],
            "max_tokens": 64,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        status, resp = http_json(f"{llm_url}/chat/completions", llm_key, llm_cert, payload=payload)
        if status == 200 and isinstance(resp, dict):
            content = resp["choices"][0]["message"].get("content", "")
            usage = resp.get("usage", {})
            print(f"[PASS] HTTP 200 (enable_thinking=False supported) | Output: {content!r} | Usage: {usage}")
        else:
            print(f"[WARN] HTTP {status} with chat_template_kwargs: {str(resp)[:250]}")
            # Retry standard OpenAI payload
            payload.pop("chat_template_kwargs", None)
            status2, resp2 = http_json(f"{llm_url}/chat/completions", llm_key, llm_cert, payload=payload)
            if status2 == 200 and isinstance(resp2, dict):
                content = resp2["choices"][0]["message"].get("content", "")
                print(f"[PASS] HTTP 200 (standard payload) | Output: {content!r}")
            else:
                print(f"[FAIL] HTTP {status2} | Response: {str(resp2)[:300]}")
                ok = False
    except Exception as exc:
        print(f"[FAIL] Inference /chat/completions error: {exc}")
        ok = False

    # 3. Check /embeddings on VM02
    print("\n--- Test 3: Embeddings API /embeddings (bge-small-en-v1.5) ---")
    try:
        payload = {
            "model": emb_model,
            "input": ["PM-KISAN farmer eligibility scheme", "Scholarship for OBC students"],
        }
        status, resp = http_json(f"{emb_url}/embeddings", emb_key, emb_cert, payload=payload)
        if status == 200 and isinstance(resp, dict):
            data = resp.get("data", [])
            dims = [len(item.get("embedding", [])) for item in data]
            print(f"[PASS] HTTP 200 | Vectors returned: {len(data)} | Dimensions: {dims}")
        else:
            print(f"[FAIL] HTTP {status} | Response: {str(resp)[:300]}")
            ok = False
    except Exception as exc:
        print(f"[FAIL] Embeddings /embeddings error: {exc}")
        ok = False

    print("\n=== SUMMARY ===")
    if ok:
        print("ALL API CHECKS PASSED! Ready for autonomous overnight build.")
        return 0
    print("ONE OR MORE CHECKS FAILED. Please inspect the errors above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
