import { useState } from "react";

export default function KBUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("idle");

  const handleUpload = () => {
    if (!file) return alert("Please select a file");

    setStatus("Uploading...");

    setTimeout(() => {
      setStatus("Processing...");
      setTimeout(() => {
        setStatus("Indexed ✅");
      }, 1500);
    }, 1500);
  };

  return (
    <div className="bg-white p-6 rounded shadow-md max-w-2xl">
      <h2 className="text-2xl font-semibold mb-6">Upload Knowledge Base</h2>

      <input
        type="file"
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
    </div>
  );
}
