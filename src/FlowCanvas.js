// frontend/src/FlowCanvas.js
import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  addEdge,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import axios from 'axios';
import { io } from 'socket.io-client';

// Connect to the SocketIO server
const socket = io('http://localhost:5000');

const FlowCanvas = ({ tools }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [input, setInput] = useState('');
  const [result, setResult] = useState('');
  const reactFlowWrapper = useRef(null);
  const { screenToFlowPosition } = useReactFlow();

  // State for parameter modal
  const [showModal, setShowModal] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeParams, setNodeParams] = useState({});

  // Map tools to their parameters for easy lookup
  const toolParameters = tools.reduce((acc, tool) => {
    acc[tool.name] = tool.parameters || [];
    return acc;
  }, {});

  // Listen for SocketIO events
  useEffect(() => {
    socket.on('node_processing', ({ nodeId, status }) => {
      console.log(`Node ${nodeId} status: ${status}`);
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              style: {
                ...node.style,
                backgroundColor: status === 'processing' ? 'yellow' : status === 'completed' ? 'lightgreen' : 'red',
              },
            };
          }
          return node;
        })
      );
    });

    socket.on('execution_complete', ({ result }) => {
      console.log('Execution complete:', result);
      setResult(result);
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          style: { ...node.style, backgroundColor: undefined },
        }))
      );
    });

    // Cleanup on unmount
    return () => {
      socket.off('node_processing');
      socket.off('execution_complete');
    };
  }, [setNodes]);

  // Handle drag start
  const onDragStart = (event, tool) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(tool));
    event.dataTransfer.effectAllowed = 'move';
  };

  // Allow dropping on the canvas
  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Handle drop event
  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const toolData = event.dataTransfer.getData('application/reactflow');
      if (!toolData) return;

      const tool = JSON.parse(toolData);
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const uniqueId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const newNode = {
        id: uniqueId,
        type: 'default',
        data: { label: tool.name, parameters: {} },
        position,
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [screenToFlowPosition, setNodes]
  );

  // Connect nodes
  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Handle node click to show parameter modal
  const onNodeClick = (event, node) => {
    setSelectedNode(node);
    setNodeParams(node.data.parameters || {});
    setShowModal(true);
  };

  // Handle parameter form submission
  const handleParamSubmit = () => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === selectedNode.id
          ? { ...node, data: { ...node.data, parameters: nodeParams } }
          : node
      )
    );
    setShowModal(false);
    setSelectedNode(null);
    setNodeParams({});
  };

  // Handle parameter input change
  const handleParamChange = (paramName, value) => {
    setNodeParams((prev) => ({ ...prev, [paramName]: value }));
  };

  // Save workflow to backend
  const saveWorkflow = async () => {
    try {
      const response = await axios.post('http://localhost:5000/save-workflow', {
        id: 'workflow1',
        nodes,
        edges,
      });
      alert(response.data.message);
    } catch (error) {
      console.error('Error saving workflow:', error);
      alert('Failed to save workflow');
    }
  };

  // Execute workflow via backend
  const executeWorkflow = async () => {
    try {
      setResult(''); // Clear previous result
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          style: { ...node.style, backgroundColor: undefined },
        }))
      );
      await axios.post('http://localhost:5000/execute-workflow', {
        workflowId: 'workflow1',
        input,
      });
    } catch (error) {
      console.error('Error executing workflow:', error);
      setResult('Error executing workflow');
    }
  };

  // Generate a unique key for ReactFlow to force re-render on node style changes
  const reactFlowKey = nodes.map((n) => `${n.id}-${n.style?.backgroundColor || 'default'}`).join('-');

  return (
    <div style={{ flex: 1, display: 'flex' }}>
      {/* Sidebar with tools and controls */}
      <div style={{ width: '250px', padding: '20px', background: '#f0f0f0', overflowY: 'auto' }}>
        <h3>Available Tools</h3>
        {tools.length === 0 ? (
          <p>No tools available</p>
        ) : (
          tools.map((tool) => (
            <div
              key={tool.name}
              draggable
              onDragStart={(event) => onDragStart(event, tool)}
              style={{
                marginBottom: '10px',
                padding: '10px',
                background: '#007bff',
                color: 'white',
                borderRadius: '4px',
                cursor: 'grab',
                userSelect: 'none',
              }}
            >
              <strong>{tool.name}</strong>
              <p style={{ fontSize: '12px', margin: '5px 0 0', color: '#e0e0e0' }}>
                {tool.description}
              </p>
            </div>
          ))
        )}
        <button
          onClick={saveWorkflow}
          style={{
            width: '100%',
            padding: '10px',
            background: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            marginTop: '20px',
            cursor: 'pointer',
          }}
        >
          Save Workflow
        </button>
        <div style={{ marginTop: '20px' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the agent..."
            style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
          />
          <button
            onClick={executeWorkflow}
            style={{
              width: '100%',
              padding: '10px',
              background: '#17a2b8',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Execute
          </button>
          {result && (
            <p style={{ marginTop: '10px', wordWrap: 'break-word' }}>
              <strong>Result:</strong> {result}
            </p>
          )}
        </div>
      </div>

      {/* React Flow canvas */}
      <div style={{ flex: 1 }} ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDragOver={onDragOver}
          onDrop={onDrop}
          onNodeClick={onNodeClick}
          fitView
          key={reactFlowKey}
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>

      {/* Parameter configuration modal */}
      {showModal && selectedNode && (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'white',
            padding: '20px',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
            zIndex: 1000,
            width: '400px',
          }}
        >
          <h3>Configure {selectedNode.data.label}</h3>
          {toolParameters[selectedNode.data.label]?.map((param) => (
            <div key={param.name} style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                {param.label}
              </label>
              {param.type === 'textarea' ? (
                <textarea
                  value={nodeParams[param.name] || ''}
                  onChange={(e) => handleParamChange(param.name, e.target.value)}
                  style={{ width: '100%', padding: '5px', resize: 'vertical' }}
                  rows="3"
                />
              ) : (
                <input
                  type={param.type}
                  value={nodeParams[param.name] || ''}
                  onChange={(e) => handleParamChange(param.name, e.target.value)}
                  style={{ width: '100%', padding: '5px' }}
                  placeholder={`Enter ${param.label}`}
                />
              )}
            </div>
          ))}
          <div style={{ textAlign: 'right' }}>
            <button
              onClick={() => setShowModal(false)}
              style={{
                padding: '8px 16px',
                background: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                marginRight: '10px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleParamSubmit}
              style={{
                padding: '8px 16px',
                background: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Wrap FlowCanvas in ReactFlowProvider
const FlowCanvasWithProvider = (props) => (
  <ReactFlowProvider>
    <FlowCanvas {...props} />
  </ReactFlowProvider>
);

export default FlowCanvasWithProvider;