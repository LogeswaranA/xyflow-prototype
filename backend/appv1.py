# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from langgraph.graph import StateGraph, END
from typing import Dict, Any, TypedDict
import json
from toolsv1 import available_tools

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000")

# Define the state for LangGraph
class GraphState(TypedDict):
    data: str  # The data being passed between nodes

# Load/save workflows from/to JSON file
WORKFLOW_FILE = "workflows.json"

def load_workflows():
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_workflows(workflows):
    with open(WORKFLOW_FILE, 'w') as f:
        json.dump(workflows, f, indent=2)

# API to get available tools
@app.route('/tools', methods=['GET'])
def get_tools():
    tools = [
        {"name": "input_query_tool", "description": "Capture the user's input query.", "parameters": [{"name": "query", "label": "Input Query", "type": "text"}]},
        {"name": "llm_tool", "description": "Generate text using an LLM based on a prompt.", "parameters": [{"name": "prompt", "label": "Prompt", "type": "text"}]},
        {"name": "output_report_tool", "description": "Format the final output as a report.", "parameters": [{"name": "data", "label": "Data", "type": "textarea"}]}
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

    # Add nodes to the graph
    for node_id, node in nodes.items():
        tool_name = node['data']['label']
        parameters = node['data'].get('parameters', {})

        def create_node_function(node_id, tool_name, params):
            def node_function(state: GraphState) -> GraphState:
                # Emit a "processing" event for this node
                socketio.emit('node_processing', {'nodeId': node_id, 'status': 'processing'})
                socketio.sleep(1)  # Simulate processing time for visibility

                tool = available_tools.get(tool_name)
                if not tool:
                    socketio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                    return {"data": f"Error: Tool {tool_name} not found"}

                # Use the parameter if provided, otherwise use the state data
                input_data = params.get(list(params.keys())[0], state['data']) if params else state['data']
                result = tool(input_data)

                # Emit a "completed" event for this node
                socketio.emit('node_processing', {'nodeId': node_id, 'status': 'completed'})
                return {"data": result}

            return node_function

        graph.add_node(node_id, create_node_function(node_id, tool_name, parameters))

    # Add edges to the graph
    for edge in edges:
        graph.add_edge(edge['source'], edge['target'])

    # Find the start node (node with no incoming edges)
    incoming_edges = {edge['target'] for edge in edges}
    start_node = next((node_id for node_id in nodes if node_id not in incoming_edges), None)
    if not start_node:
        return jsonify({"error": "No start node found"}), 400

    # Set the entry point and end point
    graph.set_entry_point(start_node)

    # Find the end node (node with no outgoing edges)
    outgoing_edges = {edge['source'] for edge in edges}
    end_node = next((node_id for node_id in nodes if node_id not in outgoing_edges), None)
    if end_node:
        graph.add_edge(end_node, END)

    # Compile and run the graph
    app = graph.compile()
    result = app.invoke({"data": user_input})

    # Emit a final "execution complete" event
    socketio.emit('execution_complete', {'result': result["data"]})

    return jsonify({"result": result["data"]})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)