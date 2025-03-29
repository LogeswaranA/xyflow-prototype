# backend/tools.py
from langchain.tools import tool
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import requests
import json
from jsonpath_ng import parse

load_dotenv(override=True)

# Initialize OpenAI LLM
llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")
@tool
def llm_tool(input_data: dict) -> str:
    """Generate text using an LLM based on a prompt, optionally using context."""
    prompt = input_data.get("prompt", "")
    context = input_data.get("context", None)
    if context:
        full_prompt = f"Context: {context}\n\nQuestion: {prompt}"
    else:
        full_prompt = prompt
    return llm.invoke(full_prompt).content

@tool
def input_query_tool(query: str) -> str:
    """Capture the user's input query."""
    return query

@tool
def output_report_tool(data: str) -> str:
    """Format the final output as a report."""
    return f"Final Report:\n\n{data}"

@tool
def fetch_from_rest_api_tool(input_data: dict) -> str:
    """Fetch data from a REST API and return it as a string."""
    url = input_data.get("url", "")
    method = input_data.get("method", "GET")
    headers = input_data.get("headers", "{}")
    body = input_data.get("body", "{}")
    try:
        headers_dict = json.loads(headers) if headers else {}
        body_dict = json.loads(body) if body else {}
        if method.upper() == "GET":
            response = requests.get(url, headers=headers_dict)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers_dict, json=body_dict)
        else:
            return f"Error: Unsupported HTTP method {method}"
        response.raise_for_status()
        return json.dumps(response.json())
    except Exception as e:
        return f"Error fetching from REST API: {str(e)}"

@tool
def filter_context_tool(input_data: dict) -> str:
    """Filter the context data using a JSON path or key."""
    filter_key = input_data.get("filter_key", "")
    context = input_data.get("context", None)
    if not context:
        return "Error: No context data available to filter"
    try:
        context_data = json.loads(context)
        jsonpath_expr = parse(filter_key)
        matches = [match.value for match in jsonpath_expr.find(context_data)]
        if not matches:
            return f"Error: No data found for filter key {filter_key}"
        result = matches if len(matches) > 1 else matches[0]
        return json.dumps(result)
    except Exception as e:
        return f"Error filtering context: {str(e)}"

# List of available tools
available_tools = {
    "llm_tool": llm_tool,
    "input_query_tool": input_query_tool,
    "output_report_tool": output_report_tool,
    "fetch_from_rest_api_tool": fetch_from_rest_api_tool,
    "filter_context_tool": filter_context_tool
}