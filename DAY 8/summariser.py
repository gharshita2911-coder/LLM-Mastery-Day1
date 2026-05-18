"""
summarizer.py – Step 3: Summarize
===================================
Asks Gemini to write a single concise sentence (≤ 20 words) that an
agent can read at a glance in a ticket queue.
 
Returns both the summary string and token usage for this call.
"""
 
from config import CLIENT,Completion,MODEL

_SUMMARISE_PROMPT="""Write a single concise sentence(max 20 words) summarising this support ticket for an agent queue. No preamble, no quotes.
Category: {category}
Ticket: \"\"\"{text}\"\"\""""

def step3_summarise(text:str,category:str)->tuple[str,Completion]:
    """Returns:
    summary(str) - one-line agent summary
    completion(Completion)- token usage for this call
     """
    
    response = CLIENT.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": _SUMMARISE_PROMPT.format(
                text=text,
                category=category
            )}],
    temperature=0,)

    meta       = response.usage
    completion = Completion(
        prompt_token_count=     getattr(meta, "prompt_token_count",     None),
        candidates_token_count= getattr(meta, "candidates_token_count", None),
        total_token_count=      getattr(meta, "total_token_count",      None),
    )
 
    summary = (response.choices[0].message.content.strip().strip("\"'"))
    return summary, completion
 