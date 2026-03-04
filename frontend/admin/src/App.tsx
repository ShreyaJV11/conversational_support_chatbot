import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import KBDashboard from "./pages/KBDashboard";
import KBUpload from "./pages/KBUpload";

function App() {
  return (
    <Routes>
      <Route path="/:botId" element={<Layout />}>
        <Route index element={<KBDashboard />} />
        <Route path="kb-upload" element={<KBUpload />} />
      </Route>
    </Routes>
  );
}

export default App;