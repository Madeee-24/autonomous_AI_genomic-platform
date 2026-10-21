import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  Layers,
  Search,
  FileCheck,
  Settings,
  ExternalLink,
} from 'lucide-react';

export default function Sidebar() {
  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/upload', label: 'Dataset Upload', icon: UploadCloud },
    { to: '/analyses', label: 'Analysis Jobs', icon: Layers },
    { to: '/explorer', label: 'Variant Explorer', icon: Search },
    { to: '/reports', label: 'Reports & History', icon: FileCheck },
    { to: '/settings', label: 'System & Health', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 min-h-[calc(100vh-4rem)] border-r border-slate-800">
      {/* Navigation Links */}
      <div className="p-4 flex-1 space-y-1">
        <p className="px-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Platform Workspace
        </p>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>

      {/* External References & Provenance */}
      <div className="p-4 border-t border-slate-800 space-y-3 text-xs">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          External Services
        </p>
        <div className="space-y-1.5 font-mono text-[11px]">
          <a
            href="https://www.ensembl.org/info/docs/tools/vep/index.html"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between text-slate-400 hover:text-cyan-400 transition-colors"
          >
            <span>Ensembl VEP REST</span>
            <ExternalLink className="w-3 h-3" />
          </a>
          <a
            href="https://www.ncbi.nlm.nih.gov/clinvar/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between text-slate-400 hover:text-cyan-400 transition-colors"
          >
            <span>NCBI ClinVar Entrez</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Academic Project Badge */}
        <div className="pt-2 border-t border-slate-800/80">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Final-Year CSE Major Engineering Project • Designed for reproducible genomic research.
          </p>
        </div>
      </div>
    </aside>
  );
}
