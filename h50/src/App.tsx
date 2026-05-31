import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Home from "@/pages/Home";
import UploadPage from "@/pages/UploadPage";
import EditorPage from "@/pages/EditorPage";
import ResultPage from "@/pages/ResultPage";
import AudioPage from "@/pages/AudioPage";
import LibraryPage from "@/pages/LibraryPage";
import ScoreDetailPage from "@/pages/ScoreDetailPage";
import StylesPage from "@/pages/StylesPage";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/editor" element={<EditorPage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/audio" element={<AudioPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/score/:scoreId" element={<ScoreDetailPage />} />
        <Route path="/styles" element={<StylesPage />} />
        <Route path="*" element={<Navigate to="/upload" replace />} />
      </Routes>
    </Router>
  );
}
