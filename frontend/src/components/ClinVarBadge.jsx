import React from 'react';
import { AlertTriangle, ExternalLink, Star } from 'lucide-react';

function getStarCount(reviewStatus) {
  if (!reviewStatus) return 0;
  const lower = reviewStatus.toLowerCase();
  if (lower.includes('practice guideline')) return 4;
  if (lower.includes('expert panel')) return 3;
  if (lower.includes('multiple submitters') && !lower.includes('conflict')) return 2;
  if (lower.includes('criteria provided') || lower.includes('single submitter')) return 1;
  return 0;
}

export default function ClinVarBadge({
  interpretation,
  reviewStatus,
  accession,
  hasConflicts = false,
  showStars = true,
  showLink = true,
}) {
  if (!interpretation) {
    return (
      <span className="text-xs text-slate-400 italic">
        No ClinVar record
      </span>
    );
  }

  const norm = interpretation.toLowerCase();
  let styles = 'bg-slate-50 text-slate-700 border-slate-200';

  if (norm.includes('pathogenic') && !norm.includes('likely')) {
    styles = 'bg-rose-50 text-rose-800 border-rose-300 font-medium';
  } else if (norm.includes('likely pathogenic')) {
    styles = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
  } else if (norm.includes('uncertain') || norm.includes('vus')) {
    styles = 'bg-yellow-50 text-yellow-800 border-yellow-300';
  } else if (norm.includes('benign')) {
    styles = 'bg-emerald-50 text-emerald-800 border-emerald-300';
  }

  const stars = getStarCount(reviewStatus);

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <div className="inline-flex items-center gap-1.5 flex-wrap">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${styles}`}
          title={`Review Status: ${reviewStatus || 'Unknown'}`}
        >
          <span>{interpretation}</span>
          {showStars && (
            <span className="inline-flex items-center text-amber-500 ml-0.5" title={`${stars} Star(s) - ${reviewStatus || ''}`}>
              {Array.from({ length: 4 }).map((_, i) => (
                <Star
                  key={i}
                  className={`w-3 h-3 ${i < stars ? 'fill-amber-400 text-amber-500' : 'text-slate-300'}`}
                />
              ))}
            </span>
          )}
        </span>

        {hasConflicts && (
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-800 border border-rose-200"
            title="Laboratories report conflicting clinical interpretations for this variant."
          >
            <AlertTriangle className="w-3 h-3 text-rose-600 shrink-0" />
            <span>Conflicting Submissions</span>
          </span>
        )}

        {showLink && accession && (
          <a
            href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${accession.replace(/[^0-9]/g, '')}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] font-mono text-cyan-700 hover:text-cyan-900 inline-flex items-center gap-0.5 underline decoration-cyan-400"
            title={`View ${accession} on NCBI ClinVar`}
          >
            <span>{accession}</span>
            <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
      </div>
    </div>
  );
}

