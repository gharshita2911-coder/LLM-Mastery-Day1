import json
import requests
import time
import os
import sys

UPLOAD_URL = "http://127.0.0.1:7000/upload"
ASK_URL    = "http://127.0.0.1:7000/ask"
DOCS_DIR   = "sample_docs"

# ── Step 1: Upload both documents ─────────────────────────────────────────
print("=" * 50)
print("STEP 1: Uploading documents...")
print("=" * 50)

upload_failed = False

for filename in ["hr_policy.txt", "novacrm_docs.txt"]:
    path = os.path.join(DOCS_DIR, filename)

    if not os.path.exists(path):
        print(f"  [ERROR] File not found: {path}")
        print(f"          Make sure sample_docs/ folder is next to run_tests.py")
        upload_failed = True
        continue

    try:
        with open(path, "rb") as f:
            resp = requests.post(
                UPLOAD_URL,
                files={"document": (filename, f, "text/plain")},
                timeout=60
            )
        data = resp.json()

        if resp.status_code == 200:
            print(f"  [OK] {filename} -> {data.get('chunks_stored')} chunks stored (doc_id: {data.get('doc_id')})")
        else:
            print(f"  [FAILED {resp.status_code}] {filename}")
            print(f"           Error  : {data.get('error', 'unknown')}")
            print(f"           Details: {data.get('details', '-')}")
            upload_failed = True

    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot connect to {UPLOAD_URL}")
        print(f"          Is the server running?  python app.py")
        upload_failed = True
    except Exception as e:
        print(f"  [ERROR] {filename} -> {e}")
        upload_failed = True

if upload_failed:
    print()
    print("Upload failed. Fix the errors above before running tests.")
    print("Common causes:")
    print("  1. Server not running          -> python app.py")
    print("  2. GEMINI_API_KEY_1 not in .env -> add your key")
    print("  3. sample_docs/ folder missing  -> must be in same directory")
    sys.exit(1)

print()
time.sleep(2)

# ── Step 2: Load test cases ───────────────────────────────────────────────
with open("test_cases.json", "r", encoding="utf-8") as f:
    test_cases = json.load(f)

results             = []
correct_count       = 0
hallucination_count = 0
total_tokens        = 0
total_cost          = 0.0

CANNOT_FIND_PHRASE = "cannot find relevant information"

print("=" * 50)
print("STEP 2: Running 20 Q&A tests...")
print("=" * 50)

for test in test_cases:
    start = time.time()

    try:
        resp = requests.post(
            ASK_URL,
            json={"question": test["question"]},
            timeout=60
        )
        elapsed = round(time.time() - start, 2)
        data    = resp.json()

        if resp.status_code != 200:
            print(f"  [{test['id']:02d}] API ERROR {resp.status_code} | {data.get('error', data)}")
            results.append({"id": test["id"], "question": test["question"], "error": data.get("error", str(data))})
            time.sleep(4)
            continue

        answer  = data.get("answer", "")
        sources = data.get("sources", [])
        tokens  = data.get("tokens") or {}
        cost    = data.get("cost_usd", 0.0)

        total_tokens += tokens.get("total", 0)
        total_cost   += cost

        answer_lower = answer.lower()
        keyword      = test["expected_keyword"].lower()

        if test["expected_type"] == "answerable":
            correct      = keyword in answer_lower
            hallucinated = CANNOT_FIND_PHRASE in answer_lower
        else:
            correct      = CANNOT_FIND_PHRASE in answer_lower
            hallucinated = (CANNOT_FIND_PHRASE not in answer_lower and len(answer.strip()) > 20)

        if correct:
            correct_count += 1
        if hallucinated:
            hallucination_count += 1

        status = "PASS" if correct else "FAIL"
        hall   = " [HALLUCINATION]" if hallucinated else ""
        print(f"  [{test['id']:02d}] {status}{hall} | {elapsed}s | {test['question'][:65]}...")

        results.append({
            "id":               test["id"],
            "question":         test["question"],
            "expected_type":    test["expected_type"],
            "expected_keyword": test["expected_keyword"],
            "answer":           answer,
            "sources":          sources,
            "correct":          correct,
            "hallucinated":     hallucinated,
            "response_time_sec": elapsed,
            "tokens":           tokens,
            "cost_usd":         cost
        })

    except requests.exceptions.ConnectionError:
        print(f"  [{test['id']:02d}] CONNECTION ERROR - is server still running?")
        results.append({"id": test["id"], "question": test["question"], "error": "connection error"})
    except Exception as e:
        print(f"  [{test['id']:02d}] ERROR: {e}")
        results.append({"id": test["id"], "question": test["question"], "error": str(e)})

    time.sleep(4)

# ── Metrics ───────────────────────────────────────────────────────────────
total_tests       = len(test_cases)
accuracy          = correct_count / total_tests * 100
hallucination_pct = hallucination_count / total_tests * 100
avg_time          = round(sum(r.get("response_time_sec", 0) for r in results) / total_tests, 2)
avg_cost          = round(total_cost / total_tests, 8) if total_tests else 0

summary = {
    "total_tests":           total_tests,
    "correct":               correct_count,
    "accuracy_pct":          round(accuracy, 2),
    "hallucinations":        hallucination_count,
    "hallucination_pct":     round(hallucination_pct, 2),
    "total_tokens_used":     total_tokens,
    "total_cost_usd":        round(total_cost, 6),
    "avg_cost_per_request":  avg_cost,
    "avg_response_time_sec": avg_time,
    "results":               results
}

with open("test_results.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4, ensure_ascii=False)

print()
print("=" * 50)
print("FINAL METRICS")
print("=" * 50)
print(f"  Total Tests        : {total_tests}")
print(f"  Correct            : {correct_count}")
print(f"  Accuracy           : {accuracy:.1f}%")
print(f"  Hallucinations     : {hallucination_count}")
print(f"  Hallucination Rate : {hallucination_pct:.1f}%  (target < 10%)")
print(f"  Total Tokens Used  : {total_tokens}")
print(f"  Total Cost (USD)   : ${total_cost:.6f}")
print(f"  Avg Cost/Request   : ${avg_cost:.8f}")
print(f"  Avg Response Time  : {avg_time}s")
print()
print("Results saved to test_results.json")
