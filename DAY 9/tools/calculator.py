"""Tool: Calculator
Safely evaluates mathematical expressions using python's math module.
"""

import math
from langchain_core.tools import tool

@tool
def calculator(expression:str)->str:
    """
    Evaluate a mathematical expression and return the result.
    Supports arithmetic, powers,square roots,trigonometric funtions, and more.
    Examples: '2+2', 'sqrt(144)','sin(3.14159/2)','2**10'
    """
    try:
        safe_env={k:getattr(math,k) for k in dir(math) if not k.startswith("_")}
        safe_env["abs"]=abs
        safe_env["round"]=round
        result=eval(expression,{"__builtins__":{}},safe_env)
        return f"{expression}={result}"
    except Exception as e:
        return f"Calculation error: {str(e)}"