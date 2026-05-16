import json
import requests
import time

API_URL = "http://127.0.0.1:6000/email/analyze"

ALLOWED_FIELDS = {"tone", "summary", "suggestedReply", "tokens", "cost_usd"}
ALLOWED_TONES  = {"formal", "neutral", "urgent", "casual"}

with open("test_cases.json", "r", encoding="utf-8") as f:
    test_cases = json.load(f)

results = []
valid_json_count    = 0
correct_tone_count  = 0
hallucination_count = 0
total_tokens_used   = 0
total_cost_usd      = 0.0

for test in test_cases:
    start_time = time.time()

    try:
        response = requests.post(
            API_URL,
            json={"email": test["email"]},
            timeout=90
        )

        response_time = round(time.time() - start_time, 2)
        data = response.json()

        valid_json   = isinstance(data, dict) and "error" not in data
        hallucinated = False
        tone_valid   = False

        if valid_json:
            valid_json_count += 1

            # Check for hallucinated fields
            extra = set(data.keys()) - ALLOWED_FIELDS
            if extra:
                hallucinated = True
                hallucination_count += 1

            # Check tone is valid
            if data.get("tone") in ALLOWED_TONES:
                tone_valid = True
                correct_tone_count += 1

            # Accumulate cost / tokens
            tokens = data.get("tokens", {})
            total_tokens_used += tokens.get("total", 0)
            total_cost_usd    += data.get("cost_usd", 0.0)

        results.append({
            "id":               test["id"],
            "description":      test["description"],
            "response_time_sec": response_time,
            "valid_json":       valid_json,
            "hallucinated":     hallucinated,
            "tone_valid":       tone_valid,
            "response":         data
        })

        print(f"[{test['id']:02d}] ✓ {test['description']} | {response_time}s")

    except Exception as e:
        results.append({
            "id":          test["id"],
            "description": test["description"],
            "error":       str(e)
        })
        print(f"[{test['id']:02d}] ✗ ERROR: {e}")

    time.sleep(5)  # avoid rate limits

# ---- METRICS ----
total_tests      = len(test_cases)
success_rate     = valid_json_count / total_tests * 100
avg_response_time = round(
    sum(r.get("response_time_sec", 0) for r in results) / total_tests, 2
)
avg_cost_usd = round(total_cost_usd / total_tests, 8) if total_tests else 0

summary = {
    "total_tests":         total_tests,
    "valid_json_count":    valid_json_count,
    "success_rate_pct":    round(success_rate, 2),
    "hallucination_count": hallucination_count,
    "correct_tone_count":  correct_tone_count,
    "total_tokens_used":   total_tokens_used,
    "total_cost_usd":      round(total_cost_usd, 6),
    "avg_cost_per_request_usd": avg_cost_usd,
    "avg_response_time_sec":    avg_response_time,
    "results": results
}

with open("test_results.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4, ensure_ascii=False)

print("\n" + "=" * 40)
print("TEST SUMMARY")
print("=" * 40)
print(f"Total Tests       : {total_tests}")
print(f"Valid JSON Rate   : {success_rate:.1f}%")
print(f"Hallucinated      : {hallucination_count}")
print(f"Valid Tones       : {correct_tone_count}/{total_tests}")
print(f"Total Tokens Used : {total_tokens_used}")
print(f"Total Cost (USD)  : ${total_cost_usd:.6f}")
print(f"Avg Cost/Request  : ${avg_cost_usd:.8f}")
print(f"Avg Response Time : {avg_response_time}s")
print("\nResults saved to test_results.json")
