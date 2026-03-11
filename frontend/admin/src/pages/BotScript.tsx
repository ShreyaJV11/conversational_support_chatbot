import { useParams } from "react-router-dom";
import { useState } from "react";


const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const FRONTEND_BASE = import.meta.env.VITE_FRONTEND_BASE || "http://localhost:5174";

export default function BotScript() {
  const { botId } = useParams<{ botId: string }>();
  const [copied, setCopied] = useState(false);

  if (!botId) {
    return <p className="text-red-600">Bot ID missing in URL</p>;
  }

  
  const script = `<script src="${API_BASE}/static/widget.js" data-bot-id="${botId}" data-app-url="${FRONTEND_BASE}"></script>`;

  const copyScript = () => {
    navigator.clipboard.writeText(script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl">
      <h2 className="text-2xl font-semibold mb-4">
        Chatbot Script (Bot ID: {botId})
      </h2>

      <p className="text-gray-600 mb-4">
        Copy this script and paste it into your website before the closing
        &lt;/body&gt; tag.
      </p>

      <div className="bg-gray-100 p-4 rounded font-mono text-sm break-all">
        {script}
      </div>

      <button
        onClick={copyScript}
        className="mt-4 px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
      >
        {copied ? "Copied ✅" : "Copy Script"}
      </button>
    </div>
  );
}