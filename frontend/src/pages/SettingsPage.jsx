import React, { useEffect, useState } from 'react';
import {
  Activity,
  Dna,
  RefreshCw,
  Server,
} from 'lucide-react';
import { healthApi } from '../services/api';

export default function SettingsPage() {
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const res = await healthApi.check();
      setHealthData(res);
    } catch (err) {
      setHealthData({ status: 'unreachable', error: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-2 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System Environment & Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Backend server configuration, bioinformatics endpoints, and genome assembly capabilities.
        </p>
      </div>

      {/* Backend Engine Diagnostics */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Server className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-semibold text-slate-900">FastAPI Backend Engine Status</h2>
          </div>
          <button
            onClick={checkHealth}
            disabled={loading}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {healthData ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[11px]">System Status:</span>
              <span
                className={`font-bold capitalize text-sm ${
                  healthData.status === 'healthy' ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {healthData.status}
              </span>
            </div>

            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[11px]">Environment:</span>
              <span className="font-bold text-slate-800 text-sm capitalize">
                {healthData.environment || 'development'}
              </span>
            </div>

            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[11px]">Default Assembly:</span>
              <span className="font-bold text-blue-700 text-sm">
                {healthData.default_assembly || 'GRCh38'}
              </span>
            </div>

            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-slate-400 block text-[11px]">Database Layer:</span>
              <span className="font-bold text-emerald-700 text-sm">
                {healthData.database_configured ? 'Configured & Active' : 'Offline'}
              </span>
            </div>
          </div>
        ) : (
          <div className="p-4 text-center text-xs text-slate-400">Loading diagnostic checks...</div>
        )}
      </div>

      {/* External Bioinformatics Services Config */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Ensembl VEP */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-3 text-xs">
          <div className="flex items-center gap-2">
            <Dna className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-slate-900 text-sm">Ensembl VEP REST API</h3>
          </div>
          <p className="text-slate-500 leading-relaxed">
            The platform queries the official Ensembl VEP REST API with automated batching (up to 200 variants per batch) and exponential backoff retry on HTTP 429 rate limits.
          </p>
          <div className="p-3 bg-slate-50 rounded-xl font-mono space-y-1 text-slate-700">
            <div>
              <span className="text-slate-400">GRCh38 Base URL:</span>
              <p className="font-semibold text-blue-700 truncate">https://rest.ensembl.org</p>
            </div>
            <div>
              <span className="text-slate-400">GRCh37 Base URL:</span>
              <p className="font-semibold text-slate-600 truncate">https://grch37.rest.ensembl.org</p>
            </div>
          </div>
        </div>

        {/* NCBI ClinVar */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-3 text-xs">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-600" />
            <h3 className="font-semibold text-slate-900 text-sm">NCBI ClinVar Entrez E-Utilities</h3>
          </div>
          <p className="text-slate-500 leading-relaxed">
            Public pathogenicity interpretations, expert review stars, and conflict detection are retrieved from NCBI ClinVar via <code>esearch.fcgi</code> and <code>esummary.fcgi</code>.
          </p>
          <div className="p-3 bg-slate-50 rounded-xl font-mono space-y-1 text-slate-700">
            <div>
              <span className="text-slate-400">Entrez Base URL:</span>
              <p className="font-semibold text-teal-700 truncate">https://eutils.ncbi.nlm.nih.gov/entrez/eutils/</p>
            </div>
            <div>
              <span className="text-slate-400">Review Star Schema:</span>
              <p className="font-semibold text-slate-600">0 to 4 Stars (Practice Guideline $\to$ No Criteria)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
