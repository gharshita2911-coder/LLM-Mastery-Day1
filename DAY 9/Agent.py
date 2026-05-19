import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.agents import initialize_agent, AgentType
from langchain.callbacks.base import BaseCallbackHandler

from tools import TOOLS

load_dotenv()

class TokenTracker(BaseCallbackHandler):

    def __init__(self):

        self.reset()

    def reset(self):

        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.llm_calls = 0

    def on_llm_end(self, response, **kwargs):

        self.llm_calls += 1

        try:

            usage = response.llm_output.get(
                "token_usage",
                {}
            )

            self.prompt_tokens += usage.get(
                "prompt_tokens",
                0
            )

            self.completion_tokens += usage.get(
                "completion_tokens",
                0
            )

            self.total_tokens += usage.get(
                "total_tokens",
                0
            )

        except:

            pass

    def summary(self):

        return {

            "promptTokens": self.prompt_tokens,

            "completionTokens": self.completion_tokens,

            "totalTokens": self.total_tokens,

            "llmCalls": self.llm_calls,
        }
# ─────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────
tracker = TokenTracker()
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY"),
    callbacks=[tracker],
)

# ─────────────────────────────────────────────
# AGENT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a helpful AI assistant.

Available tools:
- web_search → for research, facts, news
- calculator → for mathematics

Rules:
1. Use web_search for factual questions.
2. Use calculator for math.
3. Never output:
   - Action: None
   - Action Input: None
4. If you already know the answer,
   directly provide:
   Final Answer: ...
5. Keep responses concise and accurate.
"""


agent_executor = initialize_agent(

    tools=TOOLS,

    llm=llm,

    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,

    verbose=True,

    return_intermediate_steps=True,

    handle_parsing_errors=True,

    agent_kwargs={
        "prefix": SYSTEM_PROMPT
    }
)
# ─────────────────────────────────────────────
# RUN AGENT
# ─────────────────────────────────────────────
def run_agent(user_message: str):

    tracker.reset()

    response = agent_executor.invoke({
        "input": user_message
    })

    tools_used = []

    if "intermediate_steps" in response:

        for action, observation in response["intermediate_steps"]:

            tools_used.append({

                "tool": action.tool,

                "input": action.tool_input,

                "output": str(observation)
            })

    return {

        "question": user_message,

        "answer": response["output"],

        "toolsUsed": tools_used,

        "toolCount": len(tools_used),

        "tokensUsed": tracker.summary()
    }