import React from 'react';

export default function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  colorScheme = 'blue',
}) {
  const colorMap = {
    blue: {
      bg: 'bg-white',
      border: 'border-slate-200',
      iconBg: 'bg-blue-50 text-blue-600',
      valueColor: 'text-slate-900',
    },
    teal: {
      bg: 'bg-white',
      border: 'border-slate-200',
      iconBg: 'bg-teal-50 text-teal-600',
      valueColor: 'text-slate-900',
    },
    rose: {
      bg: 'bg-white',
      border: 'border-rose-200',
      iconBg: 'bg-rose-50 text-rose-600',
      valueColor: 'text-rose-900',
    },
    amber: {
      bg: 'bg-white',
      border: 'border-amber-200',
      iconBg: 'bg-amber-50 text-amber-600',
      valueColor: 'text-amber-900',
    },
    emerald: {
      bg: 'bg-white',
      border: 'border-emerald-200',
      iconBg: 'bg-emerald-50 text-emerald-600',
      valueColor: 'text-emerald-900',
    },
  };

  const scheme = colorMap[colorScheme] || colorMap.blue;

  return (
    <div className={`p-5 rounded-xl border ${scheme.border} ${scheme.bg} shadow-xs hover:shadow-sm transition-shadow`}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
        {Icon && (
          <div className={`p-2 rounded-lg ${scheme.iconBg}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className={`text-2xl font-bold font-mono tracking-tight ${scheme.valueColor}`}>
          {value !== undefined && value !== null ? value : '—'}
        </span>
        {trend && <span className="text-xs text-slate-500 font-medium">{trend}</span>}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
    </div>
  );
}
