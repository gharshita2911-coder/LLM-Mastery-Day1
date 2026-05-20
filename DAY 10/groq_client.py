"""
groq_client.py
--------------
Thin wrapper around the Groq SDK.
Handles a single prompt → response cycle and returns a structured result dict
including token counts, latency, and computed cost.
 
Usage
-----
    from groq_client import run_prompt
    result = run_prompt(model="llama-3.3-70b-versatile", prompt_id="P01", prompt_text="...")
"""

import time
from groq import Groq
from config import PRICING

def _cost_usd(model:str,input_tokens:int,output_tokens:int)->float:
    """
    Calculate the USD cost for one API call.
    Args:
        model:        Model Indentifier string.
        input_tokens: Number of prompt tokens consumed.
        output_tokens:Number of completion tokens generated.
        
    Returns:
        Cost in USD as a float.
    """
    pricing=PRICING.get(model,{})
    input_cost=(input_tokens/1_000_000)*pricing.get("input_per_million",0)
    output_cost=(output_tokens/1_000_000)*pricing.get("output_per_million",0)
    return round(input_cost+output_cost,8)

def run_prompt(
        client:Groq,
        model:str,
        prompt_id:str,
        prompt_text:str,
        category:str="",
        temperature:float=0.0,
        max_tokens:int=512
)->dict:
    """
    Send one prompt to a Groq model and capture performance metrics.
    Args:
        client:         Initialised Groq client,
        model:          Model name,
        prompt_id:      Unique prompt identifier,
        prompt_text:    the full prompt string,
        category:       prompt category label for grouping in reports,
        temperature:    Sampling temperature,
        max_tokens:     Maximum output tokens allowed.
    
    Returns:
        dict with keys:
            model,prompt_id,category,prompt_text,
            response_text,input_tokens,output_tokens,total_tokens,latency_s,cost_usd,error
    """
    result={
        "model":         model,
        "prompt_id":     prompt_id,
        "category":      category,
        "prompt_text":   prompt_text,
        "response_text": None,
        "input_tokens":  0,
        "output_tokens": 0,
        "total_tokens":  0,
        "latency_s":     0.0,
        "cost_usd":      0.0,
        "error":         None,
    }

    try:
        start=time.perf_counter()
        completion=client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":prompt_text}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        end=time.perf_counter()

        usage=completion.usage
        result["response_text"]=completion.choices[0].message.content
        result["input_tokens"]=usage.prompt_tokens
        result["output_tokens"]=usage.completion_tokens
        result["total_tokens"]=usage.total_tokens
        result["latency_s"]=round(end-start,4)
        result["cost_usd"]=_cost_usd(model,usage.prompt_tokens,usage.completion_tokens)

    except Exception as exc:
        result["error"]=str(exc)
    
    return result