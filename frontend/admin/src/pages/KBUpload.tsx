import { useState } from "react";
import { useParams } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export default function KBUpload() {
  const { botId } = useParams<{ botId: string }>();

  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  if (!botId) return <p className="text-red-600">Bot ID missing in URL</p>;

  const reset = () => { setStatus("idle"); setMessage(""); };

  const handleUpload = async () => {
    if (!file) { setMessage("Please select a file"); setStatus("error"); return; }

    const allowed = [".txt", ".md", ".html", ".pdf", ".png", ".jpg", ".jpeg", ".pptx"];
    if (!allowed.some(ext => file.name.toLowerCase().endsWith(ext))) {
      setMessage("Unsupported file type");
      setStatus("error");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setMessage("File too large (max 5MB)");
      setStatus("error");
      return;
    }

    try {
      setStatus("uploading");
      setMessage("Uploading and indexing...");

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/admin/upload-kb?bot_id=${botId}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await response.json();
      setStatus("success");
      setMessage(`Indexed ✅ ${data.chunks_inserted} chunks (${data.chunks_skipped} skipped)`);
      setFile(null);
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "Upload failed");
    }
  };

  const handleUrlIngest = async () => {
    if (!url.startsWith("http")) {
      setMessage("Enter a valid URL starting with http:// or https://");
      setStatus("error");
      return;
    }

    try {
      setStatus("uploading");
      setMessage("Fetching and indexing page...");

      const response = await fetch(`${API_BASE}/admin/ingest-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, bot_id: parseInt(botId) }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "URL ingestion failed");
      }

      const data = await response.json();
      setStatus("success");
      setMessage(`Indexed ✅ ${data.chunks_inserted} chunks from ${data.source}`);
      setUrl("");
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "URL ingestion failed");
    }
  };

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl space-y-8">
      <h2 className="text-2xl font-semibold">Upload Knowledge Base (Bot ID: {botId})</h2>

      {/* File Upload */}
      <div>
        <h3 className="text-lg font-medium mb-2">Upload File</h3>
        <p className="text-sm text-gray-500 mb-3">Supported: .txt, .md, .html, .pdf, .pptx, .png, .jpg, .jpeg</p>
        <input
          type="file"
          accept=".txt,.md,.html,.pdf,.pptx,.png,.jpg,.jpeg"
          className="mb-4 block"
          onChange={(e) => { setFile(e.target.files?.[0] || null); reset(); }}
          disabled={status === "uploading"}
        />
        <button
          onClick={handleUpload}
          disabled={status === "uploading"}
          className={`px-6 py-2 rounded text-white transition ${
            status === "uploading" ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {status === "uploading" ? "Processing..." : "Upload"}
        </button>
      </div>

      {/* Divider */}
      <div className="border-t pt-6">
        <h3 className="text-lg font-medium mb-2">Ingest from URL</h3>
        <p className="text-sm text-gray-500 mb-3">
          Paste any webpage URL (Confluence, internal wiki, docs site). The system will scrape and index all text, headings, lists, and image content.
        </p>
        <input
          type="url"
          placeholder="https://your-confluence-page.com/..."
          value={url}
          onChange={(e) => { setUrl(e.target.value); reset(); }}
          disabled={status === "uploading"}
          className="w-full border rounded px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          onClick={handleUrlIngest}
          disabled={status === "uploading"}
          className={`px-6 py-2 rounded text-white transition ${
            status === "uploading" ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
          }`}
        >
          {status === "uploading" ? "Fetching..." : "Ingest URL"}
        </button>
      </div>

      {/* Status message */}
      {status !== "idle" && (
        <p className={`font-medium ${
          status === "success" ? "text-green-600" : status === "error" ? "text-red-600" : "text-gray-600"
        }`}>
          {message}
        </p>
      )}
    </div>
  );
}
