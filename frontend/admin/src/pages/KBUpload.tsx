import { useState } from "react";
import { useParams } from "react-router-dom";

const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export default function KBUpload() {
  const { botId } = useParams<{ botId: string }>();

  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] =
    useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  if (!botId) {
    return <p className="text-red-600">Bot ID missing in URL</p>;
  }

  const handleUpload = async () => {
    if (!file) {
      setMessage("Please select a file");
      setStatus("error");
      return;
    }

    if (!file.name.endsWith(".txt")) {
      setMessage("Only .txt files are allowed");
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

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl">
      <h2 className="text-2xl font-semibold mb-6">
        Upload Knowledge Base (Bot ID: {botId})
      </h2>

      <input
        type="file"
        accept=".txt"
        className="mb-4"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        disabled={status === "uploading"}
      />

      <button
        onClick={handleUpload}
        disabled={status === "uploading"}
        className={`px-6 py-2 rounded text-white transition ${
          status === "uploading"
            ? "bg-gray-400 cursor-not-allowed"
            : "bg-blue-600 hover:bg-blue-700"
        }`}
      >
        {status === "uploading" ? "Processing..." : "Upload"}
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