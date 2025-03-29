# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from langgraph.graph import StateGraph, END
from typing import Dict, Any, TypedDict
import json
from tools import available_tools

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000")

# Define the state for LangGraph
class GraphState(TypedDict):
    data: str  # The data being passed between nodes
    api_key: str  # API key for llm_tool
    context: str  # Context data from fetch_from_rest_api_tool

# Load/save workflows from/to JSON file
WORKFLOW_FILE = "workflows.json"

def load_workflows():
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            content = f.read().strip()
            print(f"Loading workflows from {WORKFLOW_FILE}: {content}")
            if not content:
                return {}
            return json.loads(content)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {WORKFLOW_FILE}: {str(e)}")
        return {}

def save_workflows(workflows):
    try:
        with open(WORKFLOW_FILE, 'w') as f:
            json.dump(workflows, f, indent=2)
            print(f"Saved workflows to {WORKFLOW_FILE}: {workflows}")
    except Exception as e:
        print(f"Error saving workflows to {WORKFLOW_FILE}: {str(e)}")

# API to get available tools
@app.route('/tools', methods=['GET'])
def get_tools():
    tools = [
        {"name": "input_query_tool", "description": "Capture the user's input query.", "parameters": [{"name": "query", "label": "Input Query", "type": "text"}]},
        {"name": "llm_tool", "description": "Generate text using an LLM based on a prompt.", "parameters": [
            {"name": "prompt", "label": "Prompt", "type": "text"},
            {"name": "apiKey", "label": "API Key", "type": "text"},
        ]},
        {"name": "output_report_tool", "description": "Format the final output as a report.", "parameters": [{"name": "data", "label": "Data", "type": "textarea"}]},
        {"name": "fetch_from_rest_api_tool", "description": "Fetch data from a REST API and store it as context.", "parameters": [
            {"name": "url", "label": "API URL", "type": "text"},
            {"name": "method", "label": "HTTP Method (GET/POST)", "type": "text"},
            {"name": "headers", "label": "Headers (JSON)", "type": "textarea"},
            {"name": "body", "label": "Body (JSON, for POST)", "type": "textarea"}
        ]},
        {"name": "filter_context_tool", "description": "Filter the context data using a JSON path or key.", "parameters": [
            {"name": "filter_key", "label": "Filter Key (e.g., $.name)", "type": "text"}
        ]}
    ]
    return jsonify(tools)

# API to save a workflow
@app.route('/save-workflow', methods=['POST'])
def save_workflow():
    data = request.json
    workflow_id = data.get('id', 'workflow1')
    workflows = load_workflows()
    workflows[workflow_id] = {
        "nodes": data['nodes'],
        "edges": data['edges']
    }
    save_workflows(workflows)
    return jsonify({"message": "Workflow saved", "id": workflow_id})

# API to execute the workflow using LangGraph
@app.route('/execute-workflow', methods=['POST'])
def execute_workflow():
    data = request.json
    workflow_id = data.get('workflowId', 'workflow1')
    user_input = data.get('input', '')

    workflows = load_workflows()
    if workflow_id not in workflows:
        return jsonify({"error": "Workflow not found"}), 404

    workflow = workflows[workflow_id]
    nodes = {node['id']: node for node in workflow['nodes']}
    edges = workflow['edges']

    # Build the LangGraph workflow
    graph = StateGraph(GraphState)

    # Check for duplicate node IDs
    seen_node_ids = set()
    for node_id in nodes.keys():
        if node_id in seen_node_ids:
            return jsonify({"error": f"Duplicate node ID found: {node_id}"}), 400
        seen_node_ids.add(node_id)

    # Add nodes to the graph
    for node_id, node in nodes.items():
        tool_name = node['data']['label']
        parameters = node['data'].get('parameters', {})
        print(f"Adding node: {node_id} with tool: {tool_name}, parameters: {parameters}")

        def node_function(state: GraphState) -> GraphState:
            print(f"Executing node: {node_id} with tool: {tool_name}, state: {state}")
            # Emit a "processing" event for this node
            print(f"Emitting node_processing event for node: {node_id}, status: processing")
            socketio.emit('node_processing', {'nodeId': node_id, 'status': 'processing'})
            socketio.sleep(1)  # Simulate processing time for visibility

            tool = available_tools.get(tool_name)
            if not tool:
                print(f"Emitting node_processing event for node: {node_id}, status: error (tool not found)")
                socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                return {"data": f"Error: Tool {tool_name} not found", "api_key": state.get('api_key', ''), "context": state.get('context', '')}

            try:
                if tool_name == "llm_tool":
                    api_key = parameters.get('apiKey', state.get('api_key', ''))
                    if not api_key:
                        print(f"Emitting node_processing event for node: {node_id}, status: error (API key missing)")
                        socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                        return {"data": "Error: API Key required for llm_tool", "api_key": state.get('api_key', ''), "context": state.get('context', '')}
                    state['api_key'] = api_key
                    input_data = {"prompt": parameters.get('prompt', state['data']), "context": state.get('context', '')}
                    print(f"Invoking llm_tool with input: {input_data}")
                    result = tool.invoke(input_data)
                elif tool_name == "fetch_from_rest_api_tool":
                    url = parameters.get('url', '')
                    if not url:
                        print(f"Emitting node_processing event for node: {node_id}, status: error (URL missing)")
                        socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                        return {"data": "Error: API URL required", "api_key": state.get('api_key', ''), "context": state.get('context', '')}
                    headers = parameters.get('headers', '{}')
                    body = parameters.get('body', '{}')
                    try:
                        json.loads(headers)
                    except json.JSONDecodeError as e:
                        print(f"Emitting node_processing event for node: {node_id}, status: error (invalid headers)")
                        socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                        return {"data": f"Error: Invalid headers JSON: {str(e)}", "api_key": state.get('api_key', ''), "context": state.get('context', '')}
                    try:
                        json.loads(body)
                    except json.JSONDecodeError as e:
                        print(f"Emitting node_processing event for node: {node_id}, status: error (invalid body)")
                        socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                        return {"data": f"Error: Invalid body JSON: {str(e)}", "api_key": state.get('api_key', ''), "context": state.get('context', '')}
                    input_data = {"url": url, "method": parameters.get('method', 'GET'), "headers": headers, "body": body}
                    print(f"Invoking fetch_from_rest_api_tool with input: {input_data}")
                    result = tool.invoke(input_data)
                    state['context'] = result
                elif tool_name == "filter_context_tool":
                    filter_key = parameters.get('filter_key', '')
                    if not filter_key:
                        print(f"Emitting node_processing event for node: {node_id}, status: error (filter key missing)")
                        socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                        return {"data": "Error: Filter key required", "api_key": state.get('api_key', ''), "context": state.get('context', '')}
                    input_data = {"filter_key": filter_key, "context": state.get('context', '')}
                    print(f"Invoking filter_context_tool with input: {input_data}")
                    result = tool.invoke(input_data)
                    state['context'] = result
                else:
                    input_data = parameters.get(list(parameters.keys())[0], state['data']) if parameters else state['data']
                    print(f"Invoking {tool_name} with input: {input_data}")
                    result = tool.invoke(input_data)

                # Emit a "completed" event for this node
                print(f"Emitting node_processing event for node: {node_id}, status: completed")
                socketio.emit('node_processing', {'nodeId': node_id, 'status': 'completed'})
                return {"data": result, "api_key": state.get('api_key', ''), "context": state.get('context', '')}

            except Exception as e:
                print(f"Emitting node_processing event for node: {node_id}, status: error (exception: {str(e)})")
                socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                return {"data": f"Error in {tool_name}: {str(e)}", "api_key": state.get('api_key', ''), "context": state.get('context', '')}

        try:
            print(f"Adding node function for node: {node_id}")
            graph.add_node(node_id, node_function)
            print(f"Successfully added node: {node_id}")
        except Exception as e:
            return jsonify({"error": f"Failed to add node {node_id} with tool {tool_name}: {str(e)}"}), 500

    # Add edges to the graph
    for edge in edges:
        try:
            print(f"Adding edge from {edge['source']} to {edge['target']}")
            graph.add_edge(edge['source'], edge['target'])
        except Exception as e:
            return jsonify({"error": f"Failed to add edge from {edge['source']} to {edge['target']}: {str(e)}"}), 500

    # Find the start node (node with no incoming edges)
    incoming_edges = {edge['target'] for edge in edges}
    start_node = next((node_id for node_id in nodes if node_id not in incoming_edges), None)
    if not start_node:
        return jsonify({"error": "No start node found"}), 400

    # Set the entry point and end point
    print(f"Setting entry point to node: {start_node}")
    graph.set_entry_point(start_node)

    # Find the end node (node with no outgoing edges)
    outgoing_edges = {edge['source'] for edge in edges}
    end_node = next((node_id for node_id in nodes if node_id not in outgoing_edges), None)
    if end_node:
        print(f"Adding edge from end node {end_node} to END")
        graph.add_edge(end_node, END)

    # Compile and run the graph
    try:
        print("Compiling graph")
        app = graph.compile()
        print("Invoking graph")
        result = app.invoke({"data": user_input, "api_key": "", "context": ""})
    except Exception as e:
        return jsonify({"error": f"Workflow execution failed: {str(e)}"}), 500

    # Emit a final "execution complete" event
    socketio.emit('execution_complete', {'result': result["data"]})

    return jsonify({"result": result["data"]})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)