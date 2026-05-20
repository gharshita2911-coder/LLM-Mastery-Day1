"""
run_tests.py
------------
Entry point for the Groq model comparison benchmark.
 
What it does
------------
1. Reads MODELS and PROMPTS from config.py.
2. Runs every prompt against every model using groq_client.run_prompt().
3. Saves raw results to results/raw_results.json.
4. Prints a live progress table to stdout.
 
Usage
-----
    export GROQ_API_KEY="gsk_..."
    python run_tests.py
 
Output
------
    raw_results.json   -one record per (model * prompt) pair
"""

import json
import os
import sys

from groq import Groq
from config import MODELS,PROMPTS,RAW_RESULTS_FILE
from groq_client import run_prompt

def _print_header()->None:
    print("\n"+"="*72)
    print("  Groq Model Comparison-Benchmark runner")
    print("="*72)
    print(f"  Models  :  {','.join(MODELS)}")
    print(f"  Prompts :  {len(PROMPTS)}")
    print(f"  Total   :  {len(MODELS)*len(PROMPTS)} API Calls")
    print("="*72)

def _print_result_row(idx:int,total:int,result:dict)->None:
    status = "✓" if result["error"] is None else "✗"
    print(
        f"  [{idx:>3}/{total}] {status}  "
        f"{result['model']:<22}  "
        f"{result['prompt_id']}  "
        f"lat={result['latency_s']:.3f}s  "
        f"tok={result['total_tokens']:>4}  "
        f"cost=${result['cost_usd']:.6f}"
    )
    if result["error"]:
        print(f"          ERROR: {result['error']}")

def main()->None:
    api_key=os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    
    _print_header()

    client=Groq(api_key=api_key)
    all_results:list[dict]=[]
    total_calls=len(MODELS)*len(PROMPTS)
    call_index=0

    for model in MODELS:
        print(f"\n── Model: {model} {'─' * (50 - len(model))}")
        for prompt in PROMPTS:
            call_index += 1
            result = run_prompt(
                client=client,
                model=model,
                prompt_id=prompt["id"],
                prompt_text=prompt["text"],
                category=prompt.get("category", ""),
            )
            all_results.append(result)
            _print_result_row(call_index, total_calls, result)

        with open(RAW_RESULTS_FILE,"w",encoding="utf-8") as fh:
            json.dump(all_results,fh,indent=2,ensure_ascii=False)


    print(f"\n{'=' * 72}")
    print(f"  ✓  Raw results saved → {RAW_RESULTS_FILE}")
    print(f"{'=' * 72}\n")

if __name__=="__main__":
    main()        