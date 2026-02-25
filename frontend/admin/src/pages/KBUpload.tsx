import { useState } from "react";

export default function KBUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const handleUpload = async () => {
    if (!file) return alert("Please select a file");

    try {
      setStatus("Uploading...");
      setError("");

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://localhost:8000/api/admin/upload-kb",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();

      setStatus(`Indexed ✅ (${data.chunks_created} chunks)`);

    } catch (err: any) {
      setError(err.message);
      setStatus("Failed ❌");
    }
  };

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl">
      <h2 className="text-2xl font-semibold mb-6">
        Upload Knowledge Base
      </h2>

      <input
        type="file"
        accept=".txt"
        className="mb-4"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />

      <button
        onClick={handleUpload}
        className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
      >
        Upload
      </button>

      {status !== "idle" && (
        <p className="mt-4 text-lg font-medium">{status}</p>
      )}

      {error && (
        <p className="mt-2 text-red-600">{error}</p>
      )}
    </div>
  );
}