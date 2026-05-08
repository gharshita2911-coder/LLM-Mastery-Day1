import json
import requests
import time

API_URL = "http://127.0.0.1:4000/extract"

# Load test cases
with open("test_cases.json", "r", encoding="utf-8") as file:
    test_cases = json.load(file)

results = []

valid_json_count = 0
hallucination_count = 0

allowed_fields = {
    "name",
    "email",
    "summary",
    "sentiment"
}

for test in test_cases:

    start_time = time.time()

    try:
        response = requests.post(
            API_URL,
                json={
                    "text": test["text"]
                },
            timeout=10
            )

        response_time = round(
            time.time() - start_time,
            2
        )

        data = response.json()

        # Check valid JSON
        valid_json = isinstance(data, dict)

        # Check hallucinated fields
        allowed_fields = {
            "name",
            "email",
            "summary",
            "sentiment"
        }

        # Ignore failed/error responses
        if "error" in data:

            hallucinated = False

        else:

            extra_fields = (
                set(data.keys()) - allowed_fields
            )

            hallucinated = len(extra_fields) > 0
        if valid_json:
            valid_json_count += 1

        if hallucinated:
            hallucination_count += 1

        results.append({
            "id": test["id"],
            "response_time_sec": response_time,
            "valid_json": valid_json,
            "hallucinated_fields": hallucinated,
            "response": data
        })
        time.sleep(5)  # To avoid hitting rate limits

    except Exception as e:

        results.append({
            "id": test["id"],
            "error": str(e)
        })

# Save results
with open("test_cases.json", "r", encoding="utf-8") as file:
    test_cases = json.load(file)
# Metrics
total_tests = len(test_cases)

success_rate = (
    valid_json_count / total_tests
) * 100

average_time = round(
    sum(
        r.get("response_time_sec", 0)
        for r in results
    ) / total_tests,
    2
)

# SAVE RESULTS

try:

    with open(
        "test_results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nResults saved to test_results.json")

except Exception as e:

    print("\nError saving file:")
    print(str(e))
print("\n===== TEST RESULTS =====")

print(f"Total Tests: {total_tests}")
print(f"Valid JSON Success Rate: {success_rate}%")
print(f"Hallucinated Fields Count: {hallucination_count}")
print(f"Average Response Time: {average_time} sec")