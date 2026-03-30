import { Route, Routes } from "react-router-dom";

import Sidebar from "./components/Sidebar";
import EngineStudioPage from "./pages/EngineStudioPage";
import GeneratorPage from "./pages/GeneratorPage";
import LibraryPage from "./pages/LibraryPage";
import SettingsPage from "./pages/SettingsPage";
import SummaryPage from "./pages/SummaryPage";
import TopicsPage from "./pages/TopicsPage";

export default function App() {
  return (
    <div className="layout">
      <Sidebar />
      <main className="main">
        <Routes>
          <Route path="/" element={<SummaryPage />} />
          <Route path="/topics" element={<TopicsPage />} />
          <Route path="/generator" element={<GeneratorPage />} />
          <Route path="/engine-studio" element={<EngineStudioPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
