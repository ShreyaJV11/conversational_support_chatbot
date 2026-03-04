import { Link, useParams, Outlet } from "react-router-dom";

export default function Layout() {
  const { botId } = useParams<{ botId: string }>();

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-md px-8 py-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">KB Admin Panel</h1>

        {botId && (
          <div className="space-x-6">
            <Link to={`/${botId}`} className="text-blue-600 hover:underline">
              Dashboard
            </Link>

            <Link
              to={`/${botId}/kb-upload`}
              className="text-blue-600 hover:underline"
            >
              Upload KB
            </Link>
          </div>
        )}
      </nav>

      <main className="p-10">
        <Outlet />
      </main>
    </div>
  );
}