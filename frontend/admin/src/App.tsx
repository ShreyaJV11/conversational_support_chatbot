import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import KBDashboard from "./pages/KBDashboard";
import KBUpload from "./pages/KBUpload";

function App() {
  return (
    <Routes>
      {/* Redirect root to bot_id=1 */}
      <Route path="/" element={<Navigate to="/1" replace />} />
      
      <Route path="/:botId" element={<Layout />}>
        <Route index element={<KBDashboard />} />
        <Route path="kb-upload" element={<KBUpload />} />
      </Route>
    </Routes>
  );
}

export default App;