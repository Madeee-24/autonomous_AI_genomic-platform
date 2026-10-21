import React from 'react';
import { ShieldCheck, AlertCircle, HelpCircle, ShieldAlert, Info } from 'lucide-react';

export default function TierBadge({ category, score, showScore = true }) {
  const norm = (category || 'UNCERTAIN').toUpperCase();

  let styles = 'bg-slate-100 text-slate-700 border-slate-300';
  let Icon = HelpCircle;
  let label = 'Uncertain';

  switch (norm) {
    case 'TIER_1_CRITICAL':
      styles = 'bg-rose-100 text-rose-800 border-rose-300 font-semibold';
      Icon = ShieldAlert;
      label = 'Tier 1 • Critical';
      break;
    case 'TIER_2_HIGH':
      styles = 'bg-amber-100 text-amber-800 border-amber-300 font-semibold';
      Icon = AlertCircle;
      label = 'Tier 2 • High';
      break;
    case 'TIER_3_MODERATE':
      styles = 'bg-sky-100 text-sky-800 border-sky-300';
      Icon = Info;
      label = 'Tier 3 • Moderate';
      break;
    case 'TIER_4_LOW':
      styles = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      Icon = ShieldCheck;
      label = 'Tier 4 • Low';
      break;
    case 'UNCERTAIN':
    default:
      styles = 'bg-slate-100 text-slate-700 border-slate-300';
      Icon = HelpCircle;
      label = 'Uncertain';
      break;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs border ${styles}`}
      title={category}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{label}</span>
      {showScore && score !== undefined && score !== null && (
        <span className="ml-1 pl-1 border-l border-current opacity-75 font-mono text-[11px]">
          {Number(score).toFixed(1)}
        </span>
      )}
    </span>
  );
}

