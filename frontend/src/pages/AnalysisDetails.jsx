import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Layers,
  Clock,
  CheckCircle2,
  AlertCircle,
  Dna,
  RefreshCw,
  Ban,
  AlertTriangle,
} from 'lucide-react';
import { analysesApi } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const PIPELINE_STAGES = [
  { key: 'QUEUED', label: 'Queued', description: 'Job scheduled for background execution' },
  { key: 'VALIDATING', label: 'Validation', description: 'VCF file integrity & contig check' },
  { key: 'PARSING', label: 'Variant Parsing', description: 'Splits multiallelics & normalizes SNVs' },
  { key: 'ANNOTATING', label: 'VEP Annotation', description: 'Ensembl REST consequence terms' },
  { key: 'RETRIEVING_EVIDENCE', label: 'ClinVar Evidence', description: 'NCBI Entrez pathogenicity search' },
  { key: 'PRIORITIZING', label: 'Heuristic Matrix', description: 'Transparent candidate rule scoring' },
  { key: 'COMPLETED', label: 'Pipeline Complete', description: 'Results stored & audit trail ready' },
];

export default function AnalysisDetails() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  const fetchJobAndEvents = async () => {
    try {
      const [jobData, eventsData] = await Promise.all([
        analysesApi.get(id),
        analysesApi.getEvents(id).catch(() => []),
      ]);
      setJob(jobData);
      setEvents(eventsData);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to retrieve analysis details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobAndEvents();

    // Auto-poll while running
    const interval = setInterval(() => {
      if (job && (job.status === 'RUNNING' || job.status === 'QUEUED')) {
        fetchJobAndEvents();
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [id, job?.status]);

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to halt this analysis?')) return;
    setCancelling(true);
    try {
      const updated = await analysesApi.cancel(id);
      setJob(updated);
      fetchJobAndEvents();
    } catch (err) {
      alert(`Could not cancel analysis: ${err.message}`);
    } finally {
      setCancelling(false);
    }
  };

  // Determine stage index
  const getStageStatus = (stageKey) => {
    if (!job) return 'upcoming';
    if (job.status === 'FAILED') return 'failed';
    if (job.status === 'CANCELLED') return 'cancelled';

    const stageKeys = PIPELINE_STAGES.map((s) => s.key);
    const currentIndex = stageKeys.indexOf(job.current_stage);
    const thisIndex = stageKeys.indexOf(stageKey);

    if (job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_WARNINGS') {
      return 'completed';
    }

    if (thisIndex < currentIndex) return 'completed';
    if (thisIndex === currentIndex) return 'current';
    return 'upcoming';
  };

  if (loading && !job) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
        <span className="text-xs font-mono">Loading analysis pipeline details...</span>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 space-y-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <h2 className="font-semibold text-sm">Analysis Job Error</h2>
        </div>
        <p className="text-xs">{error || 'Job not found'}</p>
        <Link to="/analyses" className="text-xs font-semibold underline block">
          &larr; Back to all analysis jobs
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl border border-blue-100">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold font-mono text-slate-900 tracking-tight">
                  Job {job.id.slice(0, 8)}...
                </h1>
                <StatusBadge status={job.status} stage={job.current_stage} />
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                Dataset: {job.dataset_id} • Created: {new Date(job.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchJobAndEvents}
              className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs transition-colors"
              title="Refresh status"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            {job.variants_count > 0 && (
              <Link
                to={`/explorer?analysisId=${job.id}`}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-xs shadow-blue-500/20"
              >
                <Dna className="w-4 h-4" />
                <span>Open Variant Explorer</span>
              </Link>
            )}

            {(job.status === 'RUNNING' || job.status === 'QUEUED') && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5 border border-rose-200"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>{cancelling ? 'Halting...' : 'Cancel Job'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Failure or Warning banner */}
        {job.error_summary && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Execution Warning / Error ({job.error_code || 'FAULT'}):</span>
              <p className="mt-0.5">{job.error_summary}</p>
            </div>
          </div>
        )}

        {/* Quick Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-slate-100 text-xs font-mono">
          <div>
            <span className="text-slate-400 block text-[11px]">Variants Processed:</span>
            <span className="font-bold text-slate-800 text-sm">{job.variants_count}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Current Stage:</span>
            <span className="font-semibold text-blue-700">{job.current_stage}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Started At:</span>
            <span className="text-slate-700">
              {job.started_at ? new Date(job.started_at).toLocaleTimeString() : 'Pending'}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">Finished At:</span>
            <span className="text-slate-700">
              {job.finished_at ? new Date(job.finished_at).toLocaleTimeString() : 'In Progress'}
            </span>
          </div>
        </div>
      </div>

      {/* Multi-Stage Visual Stepper */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <h2 className="text-sm font-semibold text-slate-900">Pipeline Stage Progression</h2>

        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          {PIPELINE_STAGES.map((s, idx) => {
            const status = getStageStatus(s.key);

            let borderClass = 'border-slate-200 bg-slate-50 text-slate-400';
            let iconColor = 'text-slate-300';
            let labelClass = 'text-slate-500';

            if (status === 'completed') {
              borderClass = 'border-emerald-200 bg-emerald-50/50 text-emerald-800';
              iconColor = 'text-emerald-600';
              labelClass = 'text-emerald-950 font-semibold';
            } else if (status === 'current') {
              borderClass = 'border-blue-400 bg-blue-50 text-blue-900 ring-2 ring-blue-500/20';
              iconColor = 'text-blue-600';
              labelClass = 'text-blue-950 font-bold';
            }

            return (
              <div
                key={s.key}
                className={`p-3 rounded-xl border flex flex-col justify-between transition-all ${borderClass}`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-mono font-bold uppercase opacity-75">
                      0{idx + 1}
                    </span>
                    {status === 'completed' ? (
                      <CheckCircle2 className={`w-4 h-4 ${iconColor}`} />
                    ) : status === 'current' ? (
                      <RefreshCw className={`w-4 h-4 ${iconColor} animate-spin`} />
                    ) : (
                      <Clock className={`w-4 h-4 ${iconColor}`} />
                    )}
                  </div>
                  <h3 className={`text-xs ${labelClass}`}>{s.label}</h3>
                </div>
                <p className="text-[10px] text-slate-500 mt-2 line-clamp-2">{s.description}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Workflow Audit Trail (Event Logs) */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Workflow Audit Trail & Provenance</h2>
            <p className="text-xs text-slate-500">Immutable record of pipeline transitions and external queries</p>
          </div>
          <span className="text-xs font-mono text-slate-500">{events.length} event(s) recorded</span>
        </div>

        <div className="relative border-l-2 border-slate-200 ml-4 pl-4 space-y-4 my-2">
          {events.length > 0 ? (
            events.map((ev) => (
              <div key={ev.id} className="relative group text-xs">
                {/* Dot */}
                <div className="absolute -left-[23px] top-1 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-xs" />
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 group-hover:border-slate-300 transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <span className="font-semibold text-slate-900 font-mono">
                      [{ev.stage}] {ev.event_type}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {new Date(ev.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-slate-600">{ev.message}</p>
                  {ev.details && Object.keys(ev.details).length > 0 && (
                    <pre className="mt-2 p-2 bg-slate-900 text-slate-200 rounded text-[11px] font-mono overflow-x-auto">
                      {JSON.stringify(ev.details, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-slate-400 italic">No workflow events logged yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
