import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Layers,
  Search,
  RefreshCw,
  Dna,
} from 'lucide-react';
import { analysesApi } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function AnalysesList() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const fetchAnalyses = async () => {
    setLoading(true);
    try {
      const res = await analysesApi.list(0, 100);
      setAnalyses(res.items || []);
    } catch (err) {
      console.error('Failed to fetch analyses:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyses();
  }, []);

  const filteredAnalyses = analyses.filter((job) => {
    if (filter !== 'ALL' && job.status !== filter) return false;
    if (search.trim()) {
      const term = search.toLowerCase();
      return (
        job.id.toLowerCase().includes(term) ||
        job.dataset_id.toLowerCase().includes(term) ||
        (job.current_stage && job.current_stage.toLowerCase().includes(term))
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Genomic Analysis Jobs</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Monitor pipeline executions, track stage transitions, and explore variant results.
          </p>
        </div>

        <button
          onClick={fetchAnalyses}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Jobs</span>
        </button>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status filter tabs */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl w-full sm:w-auto">
          {['ALL', 'RUNNING', 'COMPLETED', 'FAILED'].map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                filter === tab
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search Box */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by Job ID or stage..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-blue-500 text-slate-800"
          />
        </div>
      </div>

      {/* Analyses Table Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          {filteredAnalyses.length > 0 ? (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4">Analysis Job ID</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Execution Stage</th>
                  <th className="py-3 px-4 text-right">Variants</th>
                  <th className="py-3 px-4">Created Timestamp</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {filteredAnalyses.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-blue-500 shrink-0" />
                      <span>{job.id.slice(0, 13)}...</span>
                    </td>
                    <td className="py-3 px-4 font-sans">
                      <StatusBadge status={job.status} size="xs" />
                    </td>
                    <td className="py-3 px-4 font-sans">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px] font-mono">
                        {job.current_stage}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-blue-700">
                      {job.variants_count}
                    </td>
                    <td className="py-3 px-4 font-sans text-slate-500 text-[11px]">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right font-sans space-x-2">
                      <Link
                        to={`/analyses/${job.id}`}
                        className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition-colors inline-block"
                      >
                        Pipeline Details
                      </Link>
                      {job.variants_count > 0 && (
                        <Link
                          to={`/explorer?analysisId=${job.id}`}
                          className="px-2.5 py-1 rounded bg-blue-50 hover:bg-blue-600 text-blue-700 hover:text-white font-medium text-xs transition-colors inline-flex items-center gap-1"
                        >
                          <Dna className="w-3 h-3" />
                          <span>Explore</span>
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-12 flex flex-col items-center justify-center text-center text-slate-400">
              <Layers className="w-10 h-10 stroke-1 mb-2 text-slate-300" />
              <p className="text-sm font-semibold text-slate-600">No analysis jobs found</p>
              <p className="text-xs text-slate-400 mt-1">
                {analyses.length === 0
                  ? 'Upload a VCF dataset to trigger an automated analysis.'
                  : 'No jobs match your selected filter criteria.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
