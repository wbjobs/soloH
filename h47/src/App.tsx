import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "@/components/Navbar";
import RealtimeRecognition from "@/pages/RealtimeRecognition";
import PlaybackComparison from "@/pages/PlaybackComparison";
import Statistics from "@/pages/Statistics";

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-950">
        <Navbar />
        <Routes>
          <Route path="/" element={<RealtimeRecognition />} />
          <Route path="/playback" element={<PlaybackComparison />} />
          <Route path="/statistics" element={<Statistics />} />
        </Routes>
      </div>
    </Router>
  );
}
