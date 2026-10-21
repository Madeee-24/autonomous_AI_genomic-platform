import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Layers,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Dna,
  RefreshCw,
  FileText,
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { analysesApi } from '../services/api';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';

const TIER_COLORS = {
  TIER_1_CRITICAL: '#e11d48', // rose-600
  TIER_2_HIGH: '#ea580c',     // orange-600
  TIER_3_MODERATE: '#0284c7', // sky-600
  TIER_4_LOW: '#10b981',      // emerald-500
  UNCERTAIN: '#64748b',       // slate-500
};

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [recentAnalyses, setRecentAnalyses] = useState([]);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, listRes] = await Promise.all([
        analysesApi.getDashboardSummary().catch(() => null),
        analysesApi.list(0, 5).catch(() => ({ items: [] })),
      ]);
      setSummary(sumRes);
      setRecentAnalyses(listRes.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const pieData = summary?.tier_distribution
    ? Object.entries(summary.tier_distribution).map(([tier, count]) => ({
        name: tier.replace(/_/g, ' '),
        value: count,
        key: tier,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Genomic Analysis Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time pipeline overview, variant candidate tiers, and recent automated workflows.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <Link
            to="/upload"
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-xs shadow-blue-500/20"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload New VCF</span>
          </Link>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadDashboardData}
            className="text-xs font-semibold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Uploaded Datasets"
          value={summary?.total_datasets ?? 0}
          subtitle="VCF files registered & validated"
          icon={FileText}
          colorScheme="blue"
        />
        <MetricCard
          title="Completed Analyses"
          value={summary?.completed_analyses ?? 0}
          subtitle={`${summary?.running_analyses || 0} active job(s) processing`}
          icon={CheckCircle2}
          colorScheme="emerald"
        />
        <MetricCard
          title="Total Variants Processed"
          value={summary?.total_variants_processed ?? 0}
          subtitle="Individual genomic mutations parsed"
          icon={Dna}
          colorScheme="teal"
        />
        <MetricCard
          title="Critical Candidate Variants"
          value={summary?.tier_distribution?.TIER_1_CRITICAL ?? 0}
          subtitle="Tier 1 High-Impact Pathogenic"
          icon={AlertTriangle}
          colorScheme="rose"
        />
      </div>

      {/* Two Column Layout: Chart & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tier Distribution Chart */}
        <div className="lg:col-span-1 bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs flex flex-col">
          <h2 className="text-sm font-semibold text-slate-900 mb-1">Variant Prioritization Breakdown</h2>
          <p className="text-xs text-slate-500 mb-4">Distribution across heuristic scoring tiers</p>

          {pieData.length > 0 ? (
            <div className="h-64 w-full flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.key} fill={TIER_COLORS[entry.key] || '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400">
              <Layers className="w-10 h-10 stroke-1 mb-2 text-slate-300" />
              <p className="text-xs">No prioritized variants yet.</p>
              <p className="text-[11px] text-slate-400 mt-1">
                Upload a VCF and run an analysis with prioritization enabled.
              </p>
            </div>
          )}
        </div>

        {/* Recent Analysis Jobs Table */}
        <div className="lg:col-span-2 bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Recent Analysis Jobs</h2>
              <p className="text-xs text-slate-500">Latest pipeline executions and live statuses</p>
            </div>
            <Link
              to="/analyses"
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto flex-1">
            {recentAnalyses.length > 0 ? (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-semibold border-y border-slate-100">
                  <tr>
                    <th className="py-2.5 px-3">Job ID</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Stage</th>
                    <th className="py-2.5 px-3 text-right">Variants</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentAnalyses.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3 font-mono font-medium text-slate-800">
                        {job.id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={job.status} size="xs" />
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-600">
                        {job.current_stage}
                      </td>
                      <td className="py-3 px-3 font-mono text-right text-slate-700 font-semibold">
                        {job.variants_count}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          to={`/analyses/${job.id}`}
                          className="px-2.5 py-1 rounded bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-600 font-medium transition-colors inline-block"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="h-48 flex flex-col items-center justify-center text-center text-slate-400">
                <Activity className="w-8 h-8 stroke-1 mb-2 text-slate-300" />
                <p className="text-xs">No analysis jobs executed yet.</p>
                <Link
                  to="/upload"
                  className="mt-2 text-xs font-semibold text-blue-600 hover:underline"
                >
                  Start your first analysis &rarr;
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
