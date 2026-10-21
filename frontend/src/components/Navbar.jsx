import React, { useEffect, useState } from 'react';
import { Dna } from 'lucide-react';
import { healthApi } from '../services/api';
import ResearchDisclaimer from './ResearchDisclaimer';

export default function Navbar() {
  const [health, setHealth] = useState({ status: 'connecting', assembly: 'GRCh38' });

  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        const res = await healthApi.check();
        if (mounted) {
          setHealth({
            status: res.status === 'healthy' ? 'online' : 'degraded',
            assembly: res.default_assembly || 'GRCh38',
            supported: res.supported_assemblies || ['GRCh38', 'GRCh37'],
          });
        }
      } catch (err) {
        if (mounted) {
          setHealth({ status: 'offline', assembly: 'GRCh38' });
        }
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <ResearchDisclaimer compact={false} />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center text-cyan-400 shadow-sm shadow-slate-900/20">
            <Dna className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900 text-base sm:text-lg tracking-tight">
                Genomic<span className="text-cyan-600">AI</span> Platform
              </span>
              <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-semibold border border-slate-200">
                v1.0-research
              </span>
            </div>
            <p className="text-[11px] text-slate-500 hidden sm:block">
              Autonomous Genomic Variant Validation, VEP Annotation & Prioritization
            </p>
          </div>
        </div>

        {/* Right side status indicators */}
        <div className="flex items-center gap-3">
          {/* Assembly indicator */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-mono border border-slate-200">
            <span className="text-slate-400">Assembly:</span>
            <span className="font-semibold text-slate-800">GRCh38 / GRCh37</span>
          </div>

          {/* Backend Status indicator */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              health.status === 'online'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : health.status === 'connecting'
                ? 'bg-slate-100 text-slate-600 border-slate-200'
                : 'bg-rose-50 text-rose-700 border-rose-200'
            }`}
            title={`Backend Service: ${health.status.toUpperCase()}`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                health.status === 'online'
                  ? 'bg-emerald-500 animate-ping'
                  : health.status === 'connecting'
                  ? 'bg-slate-400'
                  : 'bg-rose-500'
              }`}
            />
            <span className="capitalize">{health.status === 'online' ? 'Engine Online' : health.status}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
