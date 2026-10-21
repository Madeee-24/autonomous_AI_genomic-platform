import React, { useEffect, useState } from 'react';
import {
  FileCheck,
  Download,
  FileText,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  Clock,
  Sparkles,
} from 'lucide-react';
import { analysesApi, reportsApi } from '../services/api';

export default function ReportsPage() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generatingJobId, setGeneratingJobId] = useState(null);

  const fetchAnalyses = async () => {
    setLoading(true);
    try {
      const res = await analysesApi.list(0, 50);
      setAnalyses(
        (res.items || []).filter(
          (j) => j.status === 'COMPLETED' || j.status === 'COMPLETED_WITH_WARNINGS'
        )
      );
    } catch (err) {
      console.error('Failed to load reports history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyses();
  }, []);

  const handleDownload = (jobId) => {
    const downloadUrl = reportsApi.getLatestDownloadUrl(jobId);
    window.open(downloadUrl, '_blank');
  };

  const handleGenerateFresh = async (jobId) => {
    setGeneratingJobId(jobId);
    try {
      await reportsApi.generate(jobId);
      handleDownload(jobId);
    } catch (err) {
      alert(`Could not generate fresh report: ${err.message}`);
    } finally {
      setGeneratingJobId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-2 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Structured Genomic Reports</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Audit-ready academic research summaries, heuristic candidate breakdowns, public evidence provenance, and AI scientific rationales.
        </p>
      </div>

      {/* Reports Catalog */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Analysis Summary Reports</h2>
            <p className="text-xs text-slate-500">Completed jobs available for publication-ready PDF export and archival</p>
          </div>
          <button
            onClick={fetchAnalyses}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          {analyses.length > 0 ? (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Report Document</th>
                  <th className="py-3 px-4">Associated Analysis</th>
                  <th className="py-3 px-4 text-right">Variants Evaluated</th>
                  <th className="py-3 px-4">Completed Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {analyses.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 flex items-center gap-2.5 font-sans">
                      <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="font-semibold text-slate-900 block">
                          Genomic_Report_{job.id.slice(0, 8)}.pdf
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          Format: ReportLab Audit PDF • Version: v1.0
                        </span>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-slate-700">
                      <span>{job.id.slice(0, 13)}...</span>
                      <span className="block text-[11px] text-slate-400">Dataset: {job.dataset_id.slice(0, 8)}...</span>
                    </td>

                    <td className="py-3 px-4 text-right font-bold text-blue-700">
                      {job.variants_count}
                    </td>

                    <td className="py-3 px-4 font-sans text-slate-500 text-[11px]">
                      {job.finished_at ? new Date(job.finished_at).toLocaleString() : 'Recent'}
                    </td>

                    <td className="py-3 px-4 text-right font-sans">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleGenerateFresh(job.id)}
                          disabled={generatingJobId === job.id}
                          className="px-2.5 py-1.5 border border-slate-200 hover:bg-slate-100 text-slate-700 rounded-xl text-xs font-medium transition-colors inline-flex items-center gap-1"
                          title="Generate fresh PDF with latest database records"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${generatingJobId === job.id ? 'animate-spin' : ''}`} />
                          <span>{generatingJobId === job.id ? 'Rendering...' : 'Regenerate'}</span>
                        </button>
                        <button
                          onClick={() => handleDownload(job.id)}
                          className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition-colors inline-flex items-center gap-1.5 shadow-2xs shadow-blue-500/20"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download PDF</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-12 flex flex-col items-center justify-center text-center text-slate-400">
              <FileCheck className="w-10 h-10 stroke-1 mb-2 text-slate-300" />
              <p className="text-sm font-semibold text-slate-600">No completed analysis reports yet</p>
              <p className="text-xs text-slate-400 mt-1">
                Completed analyses will automatically appear here with one-click audit-ready PDF export.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
