// frontend/src/App.js
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import FlowCanvas from './FlowCanvas';

const App = () => {
  const [tools, setTools] = useState([]);

  useEffect(() => {
    const fetchTools = async () => {
      try {
        const response = await axios.get('http://localhost:5000/tools');
        console.log('Fetched tools:', response.data);
        setTools(response.data);
      } catch (error) {
        console.error('Error fetching tools:', error);
      }
    };
    fetchTools();
  }, []);

  return (
    <div>
      <h1>Agentic AI Workflow Builder</h1>
      {tools.length === 0 ? (
        <p>Loading tools...</p>
      ) : (
        <FlowCanvas tools={tools} />
      )}
    </div>
  );
};

export default App;