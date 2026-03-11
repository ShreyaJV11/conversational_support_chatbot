// main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import ChatWidget from './components/ChatWidget';
import './styles/index.css';

// 1. Read the URL parameters that widget.js passed in!
const urlParams = new URLSearchParams(window.location.search);
const idParam = urlParams.get('bot_id');
const botId = idParam ? Number(idParam) : undefined;

console.log("[React main.tsx] Read Bot ID from URL:", botId);

// 2. Find the root div in your index.html
const rootElement = document.getElementById('root');

if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);

  // 3. If we don't have an ID
  if (!botId) {
    console.error("❌ No bot_id found in the URL.");
    root.render(null); 
  } else {
    // 4. Render the widget perfectly
    root.render(
      <React.StrictMode>
        <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
          <ChatWidget config={{ botId: botId }} />
        </div>
      </React.StrictMode>
    );
  }
}