import json
import requests

API_URL="http://127.0.0.1:5000/lead"

with open("test_cases.json",'r',encoding="utf-8") as file:
    test_cases=json.load(file)

results=[]
correct_predictions=0

for test in test_cases:
    response=requests.post(API_URL,json={"message":test["prompt"]})

    response_data=response.json()
    print(response_data)
    actual_action=response_data.get("action")
    expected_action=test["expected_action"]
    passed=actual_action==expected_action

    if passed:
        correct_predictions+=1
    results.append({
        "prompt": test["prompt"],
        "expected_action": expected_action,
        "actual_action": actual_action,
        "args": response_data.get("args"),
        "tokens": response_data.get("tokens"),
        "passed": passed
    })
total_tests=len(test_cases)
accuracy=correct_predictions/total_tests*100

summary={
    "total_tests": total_tests,
    "correct_predictions": correct_predictions,
    "accuracy": accuracy,
    "results": results
}

with open("test_results.json","w",encoding="utf-8") as file:
    json.dump(summary,file,indent=4,ensure_ascii=False)


print("\nTest Results\n")

for result in results:

    print(json.dumps({
        "prompt": result["prompt"],
        "expected_action": result["expected_action"],
        "actual_action": result["actual_action"],
        "args": result["args"],
        "passed": result["passed"]
    }, indent=4, ensure_ascii=False))

print("\n"+"="*30) 
print(f"Accuracy: {accuracy:.2f}%")