import React from 'react';
import { AlertCircle, ShieldAlert } from 'lucide-react';

export default function ResearchDisclaimer({ compact = false }) {
  if (compact) {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded-md">
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
        <span>Academic Research-Support Tool • Not for Clinical Diagnostics</span>
      </div>
    );
  }

  return (
    <aside aria-label="Research Disclaimer" className="bg-amber-50/90 border-b border-amber-200/80 px-4 py-2 text-xs text-amber-900 transition-colors">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0" />
          <span className="font-semibold text-amber-950">ACADEMIC RESEARCH-SUPPORT NOTICE:</span>
          <span>
            This platform facilitates bioinformatics exploration and heuristic variant prioritization. It does not establish clinical medical diagnoses. Professional geneticist validation is mandatory before any clinical translation.
          </span>
        </div>
        <span className="text-amber-700 font-mono text-[11px] hidden sm:inline">
          Evidence Sources: Ensembl VEP (REST) & NCBI ClinVar (Entrez)
        </span>
      </div>
    </aside>
  );
}

