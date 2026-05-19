from tavily import TavilyClient
import os
from langchain_core.tools import tool
@tool
def web_search(query:str)->str:
    """
    Search the web for any information -
    current news, historical evets , future scheduled events, or general facts or weather reports.
    Use this  whenever the question requires information beyond your training data
    Summarise the information in maximum 100 words(if information is greater than 100 words).
    """
    try:
        client=TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response=client.search(query=query,search_depth="basic",max_results=5,)
        results=[]
        for r in response.get("results",[]):
            results.append(f"• {r['title']}: {r['content']}")
            results.append(f"Source:{r['url']}")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"
    