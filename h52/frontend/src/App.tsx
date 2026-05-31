import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Navbar } from '@/components/ui/Navbar';
import { HomePage } from '@/pages/HomePage';
import { RecordPage } from '@/pages/RecordPage';
import { ResultPage } from '@/pages/ResultPage';
import { RealtimePage } from '@/pages/RealtimePage';
import { HistoryPage } from '@/pages/HistoryPage';

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <Navbar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/record" element={<RecordPage />} />
          <Route path="/result/:id" element={<ResultPage />} />
          <Route path="/realtime" element={<RealtimePage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </div>
    </Router>
  );
}
