import { useState } from "react";
import { useParams } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

// Match this list with your backend allowed extensions
const ALLOWED_EXTENSIONS = [
  // Text formats
  ".txt", ".md", ".json", ".yaml", ".yml",
  // Document formats
  ".pdf", ".docx", ".pptx",
  // Spreadsheet formats
  ".xlsx", ".xls", ".csv",
  // Web formats
  ".html", ".htm",
  // Image formats (with OCR)
  ".png", ".jpg", ".jpeg"
];

export default function KBUpload() {
  const { botId } = useParams<{ botId: string }>();

  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [uploadMode, setUploadMode] = useState<"file" | "url">("file");
  const [status, setStatus] =
    useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  if (!botId) {
    return <p className="text-red-600">Bot ID missing in URL</p>;
  }

  const handleFileUpload = async () => {
    if (!file) {
      setMessage("Please select a file");
      setStatus("error");
      return;
    }

    // 1️⃣ Dynamic file extension validation
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
      setMessage(`Unsupported format. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
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

      const response = await fetch(
        `${API_BASE}/admin/upload-kb?bot_id=${botId}`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await response.json();

      setStatus("success");
      setMessage(
        `Indexed ✅ ${data.chunks_inserted} chunks (${data.chunks_skipped} skipped)`
      );

      setFile(null);
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "Upload failed");
    }
  };

  const handleUrlFetch = async () => {
    if (!url.trim()) {
      setMessage("Please enter a URL");
      setStatus("error");
      return;
    }

    // Basic URL validation
    try {
      new URL(url);
    } catch {
      setMessage("Please enter a valid URL");
      setStatus("error");
      return;
    }

    try {
      setStatus("uploading");
      setMessage("Fetching and indexing content from URL...");

      const response = await fetch(
        `${API_BASE}/admin/fetch-url`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            url: url,
            bot_id: parseInt(botId),
          }),
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "URL fetch failed");
      }

      const data = await response.json();

      setStatus("success");
      setMessage(
        `Indexed ✅ ${data.chunks_inserted} chunks from ${data.url}`
      );

      setUrl("");
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "URL fetch failed");
    }
  };

  const handleUpload = () => {
    if (uploadMode === "file") {
      handleFileUpload();
    } else {
      handleUrlFetch();
    }
  };

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl">
      <h2 className="text-2xl font-semibold mb-6">
        Upload Knowledge Base (Bot ID: {botId})
      </h2>

      {/* Mode Selector */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setUploadMode("file")}
          className={`px-4 py-2 rounded transition ${
            uploadMode === "file"
              ? "bg-blue-600 text-white"
              : "bg-gray-200 text-gray-700 hover:bg-gray-300"
          }`}
        >
          📁 Upload File
        </button>
        <button
          onClick={() => setUploadMode("url")}
          className={`px-4 py-2 rounded transition ${
            uploadMode === "url"
              ? "bg-blue-600 text-white"
              : "bg-gray-200 text-gray-700 hover:bg-gray-300"
          }`}
        >
          🌐 Fetch from URL
        </button>
      </div>

      {/* File Upload Mode */}
      {uploadMode === "file" && (
        <>
          <input
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="mb-4 block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-md file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            disabled={status === "uploading"}
          />
          
          <p className="text-xs text-gray-500 mb-4">
            Supported formats: {ALLOWED_EXTENSIONS.join(", ")} (Max: 5MB)
          </p>
        </>
      )}

      {/* URL Fetch Mode */}
      {uploadMode === "url" && (
        <>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/documentation"
            className="mb-4 block w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={status === "uploading"}
          />
          
          <p className="text-xs text-gray-500 mb-4">
            Enter a URL to fetch content from (HTML pages, documentation, articles, etc.)
          </p>
        </>
      )}

      <button
        onClick={handleUpload}
        disabled={status === "uploading"}
        className={`px-6 py-2 rounded text-white transition ${
          status === "uploading"
            ? "bg-gray-400 cursor-not-allowed"
            : "bg-blue-600 hover:bg-blue-700"
        }`}
      >
        {status === "uploading" ? "Processing..." : uploadMode === "file" ? "Upload" : "Fetch & Index"}
      </button>

      {status !== "idle" && (
        <p
          className={`mt-4 font-medium ${
            status === "success"
              ? "text-green-600"
              : status === "error"
              ? "text-red-600"
              : "text-gray-600"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}