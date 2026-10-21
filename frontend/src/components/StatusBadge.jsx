import React from 'react';
import { CheckCircle2, Clock, Loader2, XCircle, Ban, AlertTriangle } from 'lucide-react';

export default function StatusBadge({ status, stage, size = 'sm' }) {
  const normalized = (status || stage || 'UNKNOWN').toUpperCase();

  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200';
  let Icon = Clock;
  let animate = false;
  let label = normalized.replace(/_/g, ' ');

  switch (normalized) {
    case 'COMPLETED':
      colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      Icon = CheckCircle2;
      break;
    case 'COMPLETED_WITH_WARNINGS':
      colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
      Icon = AlertTriangle;
      break;
    case 'RUNNING':
      colorClasses = 'bg-blue-50 text-blue-700 border-blue-200';
      Icon = Loader2;
      animate = true;
      break;
    case 'QUEUED':
      colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200';
      Icon = Clock;
      break;
    case 'FAILED':
      colorClasses = 'bg-rose-50 text-rose-700 border-rose-200';
      Icon = XCircle;
      break;
    case 'CANCELLED':
      colorClasses = 'bg-slate-100 text-slate-600 border-slate-200';
      Icon = Ban;
      break;
    // Stages
    case 'VALIDATING':
    case 'PARSING':
    case 'ANNOTATING':
    case 'RETRIEVING_EVIDENCE':
    case 'PRIORITIZING':
      colorClasses = 'bg-sky-50 text-sky-700 border-sky-200';
      Icon = Loader2;
      animate = true;
      break;
    default:
      break;
  }

  const sizeClasses = size === 'xs' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${colorClasses} ${sizeClasses}`}
    >
      <Icon className={`w-3.5 h-3.5 ${animate ? 'animate-spin' : ''}`} />
      <span>{label}</span>
    </span>
  );
}
