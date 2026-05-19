"""
tools/__init__.py
Exports the active TOOLS list used by the agent.
"""

from tools.calculator import calculator
from tools.webSearch import web_search

TOOLS = [
    web_search,
    calculator,
]