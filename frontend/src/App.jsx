import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import DatasetUpload from './pages/DatasetUpload';
import AnalysesList from './pages/AnalysesList';
import AnalysisDetails from './pages/AnalysisDetails';
import VariantExplorer from './pages/VariantExplorer';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900 selection:bg-blue-100 selection:text-blue-900">
        <Navbar />

        <div className="flex-1 flex flex-col md:flex-row">
          <Sidebar />

          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto overflow-y-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<DatasetUpload />} />
              <Route path="/analyses" element={<AnalysesList />} />
              <Route path="/analyses/:id" element={<AnalysisDetails />} />
              <Route path="/explorer" element={<VariantExplorer />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
