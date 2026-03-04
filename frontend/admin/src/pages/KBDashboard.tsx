import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

type KBFile = {
  name?: string;
  uploaded?: string;
  status?: string;
};

const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export default function KBDashboard() {
  const { botId } = useParams<{ botId: string }>();

  const [files, setFiles] = useState<KBFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!botId) return;

    fetch(`${API_BASE}/admin/kb-files/${botId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to fetch KB files");
        }
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data)) {
          setFiles(data);
        } else {
          setFiles([]);
        }
      })
      .catch((err) => {
        console.error("Fetch error:", err);
        setError("Unable to load KB files");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [botId]);

  if (!botId) {
    return <p className="text-red-600">Bot ID missing in URL</p>;
  }

  return (
    <div className="bg-white p-6 rounded shadow-md">
      <h2 className="text-2xl font-semibold mb-6">
        Knowledge Base Files (Bot ID: {botId})
      </h2>

      {loading && <p className="text-gray-500">Loading files...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && (
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-200">
              <th className="p-3 text-left">File Name</th>
              <th className="p-3 text-left">Uploaded</th>
              <th className="p-3 text-left">Status</th>
            </tr>
          </thead>

          <tbody>
            {files.length > 0 ? (
              files.map((file, index) => (
                <tr key={index} className="border-t">
                  <td className="p-3">{file.name}</td>
                  <td className="p-3">
                    {file.uploaded
                      ? new Date(file.uploaded).toLocaleDateString()
                      : "N/A"}
                  </td>
                  <td className="p-3 text-green-600 font-medium">
                    {file.status}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="p-3 text-center text-gray-500">
                  No files found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}