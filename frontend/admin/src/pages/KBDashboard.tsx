import { useEffect, useState } from "react";

export default function KBDashboard() {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/admin/kb-files")
      .then((res) => res.json())
      .then((data) => setFiles(data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="bg-white p-6 rounded shadow-md">
      <h2 className="text-2xl font-semibold mb-6">
        Knowledge Base Files
      </h2>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-200">
            <th className="p-3 text-left">File Name</th>
            <th className="p-3 text-left">Uploaded</th>
            <th className="p-3 text-left">Status</th>
          </tr>
        </thead>

        <tbody>
          {files.map((file: any, index: number) => (
            <tr key={index} className="border-t">
              <td className="p-3">{file.name}</td>
              <td className="p-3">
                {new Date(file.uploaded).toLocaleDateString()}
              </td>
              <td className="p-3 text-green-600 font-medium">
                {file.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}