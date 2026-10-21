import React from 'react';

export default function ImpactBadge({ impact }) {
  const norm = (impact || 'MODIFIER').toUpperCase();

  let styles = 'bg-slate-100 text-slate-700 border-slate-200';

  switch (norm) {
    case 'HIGH':
      styles = 'bg-purple-100 text-purple-800 border-purple-300 font-semibold';
      break;
    case 'MODERATE':
      styles = 'bg-blue-100 text-blue-800 border-blue-200';
      break;
    case 'LOW':
      styles = 'bg-teal-50 text-teal-700 border-teal-200';
      break;
    case 'MODIFIER':
    default:
      styles = 'bg-slate-100 text-slate-600 border-slate-200';
      break;
  }

  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] uppercase tracking-wider font-mono border ${styles}`}
    >
      {norm}
    </span>
  );
}
