import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { ParamsPage } from "@/pages/ParamsPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { VisualizationPage } from "@/pages/VisualizationPage";
import { useAppStore } from "@/store";

function AppContent() {
  const { activeTab } = useAppStore();

  const renderActivePage = () => {
    switch (activeTab) {
      case 'params':
        return <ParamsPage />;
      case 'results':
        return <ResultsPage />;
      case 'visualization':
        return <VisualizationPage />;
      default:
        return <ParamsPage />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 animate-fade-in">
        {renderActivePage()}
      </main>
      <footer className="border-t border-slate-500/20 py-4 text-center text-xs text-slate-500">
        <p>量子点器件模拟器 © 2025 | 基于有效质量近似、费米黄金定则与漂移扩散模型</p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<AppContent />} />
      </Routes>
    </Router>
  );
}
