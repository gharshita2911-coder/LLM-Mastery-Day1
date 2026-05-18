"""
classifier.py – Step 2: Classify
==================================
Strategy: fast regex rules first, Gemini fallback only for ambiguous tickets.
 
Categories: bug | feature | question | complaint | other
"""

import re 
from config import CLIENT,Completion,MODEL

_RULES=[
    ("bug",re.compile(r"crash|error|broken|fail|corrupt|not work|down|duplicate|reject|missing|500|403|404",re.I,)),
    ("feature", re.compile(r"feature|request|add|support|would love|please add|would be great|dark mode|bulk|webhook|two.factor|2fa|sso|rrule|recurring|pdf index|export|import",re.I,)),
    ("question",re.compile(r"\bhow\b|\bcan you\b|\bis there\b|\bwhat is\b|clarify|difference|help.*setup",re.I,)),
    ("complaint",re.compile( r"unacceptable|disappointed|angry|want answers|deleted.*warning|down for|status page.*operational",re.I,)),
]

_VALID_LABELS={"bug","feature","question","complaint"}
_CLASSIFY_PROMPT = """Classify this support ticket into exactly one category.
Reply with ONLY one word: bug, feature, question, or complaint.
 
Ticket: \"\"\"{text}\"\"\""""

def step2_classify(text:str,extracted:dict,use_llm_fallback:bool=True,)->tuple[str,Completion]:
    """
    Returns:
    category(str)- bug|feature|question|complaint|other
    completion(Completion)- token usage(zeros if rule matched, no LLM call)
    """
    combined=text+" "+(extracted.get("issue") or "") 
    for category,pattern in _RULES:
        if pattern.search(combined):
            return category,Completion(0,0,0)
        
    if use_llm_fallback:
        response = CLIENT.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                     "content": _CLASSIFY_PROMPT.format(text=text)
                }
            ],
        temperature=0,)
        meta=response.usage
        completion=Completion(
            prompt_token_count=getattr(meta,"prompt_token_count",None),
            candidates_token_count=getattr(meta,"candidates_token_count",None),
            total_token_count=getattr(meta,"total_token_count",None),
        )

        label=response.choices[0].message.content.strip().lower()
        if label in _VALID_LABELS:
            return label,completion
        
        return "other",completion
    return "other",Completion(0,0,0)