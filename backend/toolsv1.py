# backend/tools.py
from langchain.tools import tool
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize OpenAI LLM
llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")

@tool
def llm_tool(prompt: str) -> str:
    """Generate text using an LLM based on a prompt."""
    return llm.invoke(prompt).content

@tool
def input_query_tool(query: str) -> str:
    """Capture the user's input query."""
    return query

@tool
def output_report_tool(data: str) -> str:
    """Format the final output as a report."""
    return f"Final Report:\n\n{data}"

# List of available tools
available_tools = {
    "llm_tool": llm_tool,
    "input_query_tool": input_query_tool,
    "output_report_tool": output_report_tool
}