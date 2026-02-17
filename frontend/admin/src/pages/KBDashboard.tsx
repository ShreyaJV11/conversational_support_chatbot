export default function KBDashboard() {
  const mockFiles = [
    {
      name: "questions_answer.txt",
      category: "General",
      uploaded: "2026-02-17",
      status: "Indexed",
    },
  ];

  return (
    <div className="bg-white p-6 rounded shadow-md">
      <h2 className="text-2xl font-semibold mb-6">Knowledge Base Files</h2>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-200">
            <th className="p-3 text-left">File Name</th>
            <th className="p-3 text-left">Category</th>
            <th className="p-3 text-left">Uploaded</th>
            <th className="p-3 text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {mockFiles.map((file, index) => (
            <tr key={index} className="border-t">
              <td className="p-3">{file.name}</td>
              <td className="p-3">{file.category}</td>
              <td className="p-3">{file.uploaded}</td>
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
