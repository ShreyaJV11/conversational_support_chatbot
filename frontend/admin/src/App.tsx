import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import KBDashboard from "./pages/KBDashboard";
import KBUpload from "./pages/KBUpload";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<KBDashboard />} />
        <Route path="/kb-upload" element={<KBUpload />} />
      </Routes>
    </Layout>
  );
}

export default App;

