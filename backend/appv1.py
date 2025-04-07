# backend/appv1.py
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, END  # Now works after installation
from typing import Dict, Any, TypedDict
import json
import os
from tools import available_tools
import socketio
import uvicorn
import asyncio
from pydantic import BaseModel
from websocket import create_connection

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SocketIO setup
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="http://localhost:3000")
app.mount("/socket.io", socketio.ASGIApp(sio))

# Define the state for LangGraph
class GraphState(TypedDict):
    data: str

# Workflow file management
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
@app.get("/tools")
async def get_tools():
    tools = [
        {"name": "input_query_tool", "description": "Capture the user's input query.", "parameters": [{"name": "query", "label": "Input Query", "type": "text"}]},
        {"name": "llm_tool", "description": "Generate text using an LLM based on a prompt.", "parameters": [{"name": "prompt", "label": "Prompt", "type": "text"}]},
        {"name": "output_report_tool", "description": "Format the final output as a report.", "parameters": [{"name": "data", "label": "Data", "type": "textarea"}]},
        {"name": "twilio_call_tool", "description": "Make a phone call using Twilio.", "parameters": [
            {"name": "phone_number", "label": "Phone Number", "type": "text"},
            {"name": "message", "label": "Message", "type": "text"}
        ]},
        {"name": "deepgram_stt_tool", "description": "Convert audio to text using Deepgram.", "parameters": [
            {"name": "audio_url", "label": "Audio URL", "type": "text"}
        ]},
        {"name": "rag_tool", "description": "Generate a response using RAG with context.", "parameters": [
            {"name": "query", "label": "Query", "type": "text"},
            {"name": "context", "label": "Context", "type": "textarea"}
        ]},
        {"name": "elevenlabs_tts_tool", "description": "Convert text to speech using ElevenLabs.", "parameters": [
            {"name": "text", "label": "Text", "type": "text"}
        ]},
        {"name": "response_summary_tool", "description": "Summarize provided data.", "parameters": [
            {"name": "data", "label": "Data", "type": "textarea"}
        ]}
    ]
    return tools

# Pydantic model for workflow execution input
class ExecuteWorkflowInput(BaseModel):
    workflowId: str = "workflow1"
    input: str = ""

# API to save a workflow
@app.post("/save-workflow")
async def save_workflow(request: Request):
    data = await request.json()
    workflow_id = data.get('id', 'workflow1')
    workflows = load_workflows()
    workflows[workflow_id] = {
        "nodes": data['nodes'],
        "edges": data['edges']
    }
    save_workflows(workflows)
    return {"message": "Workflow saved", "id": workflow_id}

# API to execute the workflow
@app.post("/execute-workflow")
async def execute_workflow(input_data: ExecuteWorkflowInput):
    workflow_id = input_data.workflowId
    user_input = input_data.input

    workflows = load_workflows()
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows[workflow_id]
    nodes = {node['id']: node for node in workflow['nodes']}
    edges = workflow['edges']

    # Build the LangGraph workflow
    graph = StateGraph(GraphState)

    # Add nodes to the graph
    for node_id, node in nodes.items():
        tool_name = node['data']['label']
        parameters = node['data'].get('parameters', {})

        async def create_node_function(node_id, tool_name, params):
            async def node_function(state: GraphState) -> GraphState:
                await sio.emit('node_processing', {'nodeId': node_id, 'status': 'processing'})
                await asyncio.sleep(1)  # Simulate processing time

                tool = available_tools.get(tool_name)
                if not tool:
                    await sio.emit('node_processing', {'nodeId': node_id, 'status': 'error'})
                    return {"data": f"Error: Tool {tool_name} not found"}

                input_data = params.get(list(params.keys())[0], state['data']) if params else state['data']
                result = tool(input_data)

                await sio.emit('node_processing', {'nodeId': node_id, 'status': 'completed'})
                return {"data": result}

            return node_function

        graph.add_node(node_id, await create_node_function(node_id, tool_name, parameters))

    # Add edges to the graph
    for edge in edges:
        graph.add_edge(edge['source'], edge['target'])

    # Find start and end nodes
    incoming_edges = {edge['target'] for edge in edges}
    start_node = next((node_id for node_id in nodes if node_id not in incoming_edges), None)
    if not start_node:
        raise HTTPException(status_code=400, detail="No start node found")

    graph.set_entry_point(start_node)
    outgoing_edges = {edge['source'] for edge in edges}
    end_node = next((node_id for node_id in nodes if node_id not in outgoing_edges), None)
    if end_node:
        graph.add_edge(end_node, END)

    # Compile and run the graph
    compiled_graph = graph.compile()
    result = await compiled_graph.ainvoke({"data": user_input})

    await sio.emit('execution_complete', {'result': result["data"]})
    return {"result": result["data"]}

# WebSocket for Twilio-ElevenLabs integration
@app.websocket("/connection")
async def websocket_connection(websocket: WebSocket):
    await websocket.accept()
    elevenlabs_ws = None
    try:
        # Connect to ElevenLabs WebSocket (placeholder; requires proper ElevenLabs WebSocket URL)
        elevenlabs_ws = create_connection(f"wss://api.elevenlabs.io/v1/websocket?api_key={os.getenv('ELEVENLABS_API_KEY')}")
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "media":
                # Forward Twilio audio to ElevenLabs
                elevenlabs_ws.send(json.dumps({"user_audio_chunk": msg["media"]["payload"]}))
                # Receive ElevenLabs response
                elevenlabs_response = json.loads(elevenlabs_ws.recv())
                if elevenlabs_response.get("type") == "audio":
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": msg.get("streamSid"),
                        "media": {"payload": elevenlabs_response["audio"]["chunk"]}
                    })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if elevenlabs_ws:
            elevenlabs_ws.close()
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)