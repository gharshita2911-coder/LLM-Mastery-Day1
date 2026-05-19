import json
from Agent import run_agent


TEST_PROMPTS = [
    # ── calculator ──
    "What is 17 * 43 + sqrt(256)?",
    "Calculate sin(pi/4) rounded to 4 decimal places",
    "What is 2 to the power of 10?",
    # ── web_search ──
    "Search for information about LangChain framework",
    "What is the capital of Australia? Search to confirm.",
    "What is Groq AI?",
    # ── no tool needed ──
    "What is the capital of France?",
    "Explain what a REST API is in one paragraph.",
    "What are the three laws of robotics?",
    "Who wrote the Harry Potter series?",
]
 


results = []


for i, prompt in enumerate(TEST_PROMPTS, 1):

    print("\n" + "=" * 60)

    print(f"TEST {i}")

    print(f"PROMPT: {prompt}")

    try:

        response = run_agent(prompt)

        results.append(response)

        print("\nANSWER:")
        print(response["answer"])

    except Exception as e:

        print(f"ERROR: {e}")


with open("test_results.json", "w") as f:

    json.dump(results, f, indent=2)


print("\nResults saved to test_results.json")