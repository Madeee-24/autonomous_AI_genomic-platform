import React from 'react';
import {
  X,
  Dna,
  AlertTriangle,
  CheckCircle,
  FileText,
  Activity,
  Layers,
  Info,
} from 'lucide-react';
import TierBadge from './TierBadge';
import ImpactBadge from './ImpactBadge';
import ClinVarBadge from './ClinVarBadge';

export default function VariantDetailsModal({ variant, onClose }) {
  if (!variant) return null;

  const prio = variant.prioritization;
  const reasons = prio?.reasons || {};
  const limitations = prio?.limitations || {};

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="variant-details-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 sm:p-6"
    >
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/30 rounded-lg text-blue-400 border border-blue-500/30">
              <Dna className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 id="variant-details-title" className="text-lg font-bold font-mono tracking-tight text-white">
                  {variant.chromosome}:{variant.position} {variant.reference_allele} &gt; {variant.alternate_allele}
                </h3>
                {variant.primary_gene && (
                  <span className="px-2 py-0.5 text-xs font-bold bg-cyan-900 text-cyan-200 border border-cyan-700 rounded">
                    {variant.primary_gene}
                  </span>
                )}
                <span className="text-xs text-slate-400 font-mono">({variant.variant_type})</span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                dbSNP / ID: {variant.variant_identifier || 'None declared'} • Filter: {variant.filter_status} • Quality: {variant.quality ?? 'N/A'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close dialog"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-slate-800 text-sm">
          {/* Prioritization Matrix Banner */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Candidate Prioritization</p>
              <div className="mt-1 flex items-center gap-2">
                <TierBadge category={variant.priority_category} score={variant.priority_score} />
                <span className="text-xs text-slate-500 font-mono">Matrix {prio?.rule_version || 'v1.0'}</span>
              </div>
            </div>

            {reasons.scoring_breakdown && (
              <div className="flex items-center gap-4 text-xs font-mono bg-white px-3 py-2 rounded-lg border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[10px]">VEP Impact:</span>
                  <span className="font-semibold text-slate-700">+{reasons.scoring_breakdown.consequence_impact_score || 0}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">ClinVar Sig:</span>
                  <span className="font-semibold text-slate-700">+{reasons.scoring_breakdown.clinvar_significance_score || 0}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Stars Mod:</span>
                  <span className="font-semibold text-slate-700">+{reasons.scoring_breakdown.review_status_score || 0}</span>
                </div>
                {reasons.scoring_breakdown.conflict_penalty && (
                  <div>
                    <span className="text-rose-400 block text-[10px]">Conflict Pen:</span>
                    <span className="font-semibold text-rose-600">-{reasons.scoring_breakdown.conflict_penalty}</span>
                  </div>
                )}
                <div className="pl-2 border-l border-slate-200">
                  <span className="text-slate-400 block text-[10px]">Total Score:</span>
                  <span className="font-bold text-blue-700 text-sm">{reasons.scoring_breakdown.total_score || variant.priority_score || 0}</span>
                </div>
              </div>
            )}
          </div>

          {/* Section 1: Ensembl VEP Consequence Annotations */}
          <div>
            <div className="flex items-center gap-2 pb-2 mb-3 border-b border-slate-200">
              <Activity className="w-4 h-4 text-blue-600" />
              <h4 className="font-semibold text-slate-900">Ensembl VEP Consequence Annotations</h4>
            </div>

            {variant.annotations && variant.annotations.length > 0 ? (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-600 uppercase font-semibold">
                    <tr>
                      <th className="py-2 px-3">Gene Symbol</th>
                      <th className="py-2 px-3">Gene ID</th>
                      <th className="py-2 px-3">Transcript</th>
                      <th className="py-2 px-3">Consequence Term</th>
                      <th className="py-2 px-3">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {variant.annotations.map((ann, idx) => (
                      <tr key={ann.id || idx} className="hover:bg-slate-50 font-mono">
                        <td className="py-2 px-3 font-semibold text-slate-900">{ann.gene_symbol || '—'}</td>
                        <td className="py-2 px-3 text-slate-600">{ann.gene_id || '—'}</td>
                        <td className="py-2 px-3 text-slate-600">{ann.transcript_id || '—'}</td>
                        <td className="py-2 px-3 text-blue-700">{ann.consequence}</td>
                        <td className="py-2 px-3">
                          <ImpactBadge impact={ann.impact} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded-lg">
                No Ensembl VEP consequence records retrieved for this genomic variant.
              </p>
            )}
          </div>

          {/* Section 2: NCBI ClinVar Evidence */}
          <div>
            <div className="flex items-center gap-2 pb-2 mb-3 border-b border-slate-200">
              <FileText className="w-4 h-4 text-teal-600" />
              <h4 className="font-semibold text-slate-900">NCBI ClinVar Public Evidence</h4>
            </div>

            {variant.evidence_records && variant.evidence_records.length > 0 ? (
              <div className="space-y-3">
                {variant.evidence_records.map((ev, idx) => (
                  <div key={ev.id || idx} className="p-4 rounded-xl border border-slate-200 bg-white space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <ClinVarBadge
                          interpretation={ev.interpretation}
                          reviewStatus={ev.review_status}
                          accession={ev.source_accession}
                          hasConflicts={ev.has_conflicts}
                        />
                      </div>
                      <span className="text-xs text-slate-400 font-mono">
                        Source: {ev.source_name} • Retrieved {ev.retrieved_at ? new Date(ev.retrieved_at).toLocaleDateString() : 'Active Cache'}
                      </span>
                    </div>

                    {ev.has_conflicts && (
                      <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold">Conflicting Submitter Classifications:</span>
                          <p className="mt-0.5 text-rose-700">
                            Different reporting clinical laboratories disagree on this variant's clinical significance. Professional review of each individual submitter assertion is required.
                          </p>
                        </div>
                      </div>
                    )}

                    {ev.evidence_summary && (
                      <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                        <span className="font-semibold text-slate-700 block mb-0.5">Reported Conditions & Evidence:</span>
                        <span>{ev.evidence_summary}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded-lg">
                No matching assertions found in NCBI ClinVar for this coordinate and allele.
              </p>
            )}
          </div>

          {/* Section 3: Prioritization Reasons & Limitations */}
          <div>
            <div className="flex items-center gap-2 pb-2 mb-3 border-b border-slate-200">
              <Layers className="w-4 h-4 text-indigo-600" />
              <h4 className="font-semibold text-slate-900">Scoring Matrix Rationale & Provenance</h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Positive Scoring Rationale */}
              <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200/80">
                <span className="text-xs font-semibold text-emerald-900 flex items-center gap-1.5 mb-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  Prioritization Factors
                </span>
                <ul className="text-xs text-emerald-950 space-y-1.5 list-disc list-inside">
                  {reasons.rationale_trail && reasons.rationale_trail.length > 0 ? (
                    reasons.rationale_trail.map((r, i) => <li key={i}>{r}</li>)
                  ) : (
                    <li className="italic text-slate-500">Heuristic baseline calculation (no dominant pathogenic markers).</li>
                  )}
                </ul>
              </div>

              {/* Explicit Limitations & Disclaimers */}
              <div className="p-4 bg-amber-50/50 rounded-xl border border-amber-200/80">
                <span className="text-xs font-semibold text-amber-900 flex items-center gap-1.5 mb-2">
                  <Info className="w-4 h-4 text-amber-600" />
                  Methodological Limitations
                </span>
                <ul className="text-xs text-amber-950 space-y-1.5 list-disc list-inside">
                  {limitations.caveats && limitations.caveats.length > 0 ? (
                    limitations.caveats.map((c, i) => <li key={i}>{c}</li>)
                  ) : (
                    <li className="italic text-slate-500">Subject to general academic research-use disclaimers.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Variant ID: <code className="font-mono">{variant.id}</code></span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors font-medium"
          >
            Close Details
          </button>
        </div>
      </div>
    </div>
  );
}
