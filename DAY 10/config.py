"""
config.py
---------
Central configuration for the Groq model comparison study.
Edit MODELS, PROMPTS, or pricing constants here without touching other files.
"""
#MODELS under comparison
MODELS=["llama-3.3-70b-versatile","llama-3.1-8b-instant"]

#--GROQ rpicing (USD per 1000000 tokens, 2026)
PRICING={
    "llama-3.3-70b-versatile":{
        "input_per_million":0.59,
        "output_per_million":0.79,
    },
    "llama-3.1-8b-instant":{
        "input_per_million":0.05,
        "output_per_million":.08,
    },
}

 
# ── Test prompts (15 prompts across varied categories) ───────────────────────
PROMPTS = [
    # --- Factual / Knowledge ---
    {
        "id": "P01",
        "category": "Factual",
        "text": "What is the capital of Australia, and what is its population?",
    },
    {
        "id": "P02",
        "category": "Factual",
        "text": "Explain the difference between TCP and UDP protocols in networking.",
    },
    {
        "id": "P03",
        "category": "Factual",
        "text": "Who invented the World Wide Web and in what year?",
    },
 
    # --- Reasoning / Logic ---
    {
        "id": "P04",
        "category": "Reasoning",
        "text": (
            "A bat and a ball together cost $1.10. The bat costs $1.00 more than the ball. "
            "How much does the ball cost? Show your reasoning."
        ),
    },
    {
        "id": "P05",
        "category": "Reasoning",
        "text": (
            "If all Bloops are Razzles and all Razzles are Lazzles, are all Bloops definitely Lazzles? "
            "Explain your logic."
        ),
    },
    {
        "id": "P06",
        "category": "Reasoning",
        "text": (
            "You have three boxes: one contains only apples, one only oranges, and one contains both. "
            "All labels are wrong. You can pick one fruit from one box. How do you correctly label all boxes?"
        ),
    },
 
    # --- Coding ---
    {
        "id": "P07",
        "category": "Coding",
        "text": (
            "Write a Python function that accepts a list of integers and returns the two numbers "
            "that add up to a given target. Include a brief docstring."
        ),
    },
    {
        "id": "P08",
        "category": "Coding",
        "text": "Write a SQL query to find the top 5 customers by total order value from an `orders` table.",
    },
    {
        "id": "P09",
        "category": "Coding",
        "text": "Explain what a REST API is and provide a minimal Python Flask example with one GET endpoint.",
    },
 
    # --- Summarisation ---
    {
        "id": "P10",
        "category": "Summarisation",
        "text": (
            "Summarise the following in three bullet points:\n\n"
            "Artificial intelligence (AI) is transforming industries by automating complex tasks, "
            "enabling smarter decision-making, and creating new business models. From healthcare "
            "diagnostics to financial fraud detection, AI tools are increasingly embedded in "
            "critical workflows. However, concerns around bias, data privacy, and job displacement "
            "continue to challenge widespread adoption."
        ),
    },
    {
        "id": "P11",
        "category": "Summarisation",
        "text": (
            "In one paragraph, summarise the key ideas of the Agile software development methodology "
            "and how it differs from Waterfall."
        ),
    },
 
    # --- Creative Writing ---
    {
        "id": "P12",
        "category": "Creative",
        "text": "Write a two-sentence horror story.",
    },
    {
        "id": "P13",
        "category": "Creative",
        "text": "Write a short product tagline (max 10 words) for a reusable coffee cup brand.",
    },
 
    # --- Instruction Following ---
    {
        "id": "P14",
        "category": "Instruction",
        "text": (
            "List exactly five benefits of regular exercise. "
            "Format each as: '<number>. <benefit>: <one-sentence explanation>'."
        ),
    },
    {
        "id": "P15",
        "category": "Instruction",
        "text": (
            "Translate the following sentence into French, Spanish, and German. "
            "Label each translation clearly.\n\n"
            "Sentence: 'The quick brown fox jumps over the lazy dog.'"
        ),
    },
]

RAW_RESULTS_FILE="raw_results.json"
REPORT_FILE="model_comparison.md"