import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  Dna,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';
import { analysesApi } from '../services/api';
import TierBadge from '../components/TierBadge';
import ImpactBadge from '../components/ImpactBadge';
import ClinVarBadge from '../components/ClinVarBadge';
import VariantDetailsModal from '../components/VariantDetailsModal';

const CHROMOSOMES = [
  'ALL',
  ...Array.from({ length: 22 }, (_, i) => `chr${i + 1}`),
  'chrX',
  'chrY',
  'chrM',
];

const TIERS = [
  { value: 'ALL', label: 'All Prioritization Tiers' },
  { value: 'TIER_1_CRITICAL', label: 'Tier 1 • Critical (Pathogenic High-Impact)' },
  { value: 'TIER_2_HIGH', label: 'Tier 2 • High (Likely Pathogenic / Moderate)' },
  { value: 'TIER_3_MODERATE', label: 'Tier 3 • Moderate (VUS / Functional Risk)' },
  { value: 'TIER_4_LOW', label: 'Tier 4 • Low (Benign / Modifiers)' },
  { value: 'UNCERTAIN', label: 'Uncertain / Unannotated' },
];

export default function VariantExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialAnalysisId = searchParams.get('analysisId') || '';

  // Analysis selector state
  const [analyses, setAnalyses] = useState([]);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState(initialAnalysisId);

  // Variant filtering & pagination
  const [variants, setVariants] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);

  // Active filters
  const [chromosome, setChromosome] = useState('ALL');
  const [gene, setGene] = useState('');
  const [tier, setTier] = useState('ALL');
  const [hasConflictsOnly, setHasConflictsOnly] = useState(false);

  // Modal inspection state
  const [selectedVariant, setSelectedVariant] = useState(null);

  // Fetch list of available completed analyses
  useEffect(() => {
    const loadAnalyses = async () => {
      try {
        const res = await analysesApi.list(0, 50);
        const list = res.items || [];
        setAnalyses(list);
        if (!selectedAnalysisId && list.length > 0) {
          const firstValid = list.find((j) => j.variants_count > 0) || list[0];
          setSelectedAnalysisId(firstValid.id);
          setSearchParams({ analysisId: firstValid.id });
        }
      } catch (err) {
        console.error('Failed to load analyses list:', err);
      }
    };
    loadAnalyses();
  }, []);

  // Fetch variants for selected analysis and filters
  const fetchVariants = async () => {
    if (!selectedAnalysisId) return;
    setLoading(true);
    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (chromosome !== 'ALL') params.chromosome = chromosome;
      if (gene.trim()) params.gene = gene.trim();
      if (tier !== 'ALL') params.priority_category = tier;
      if (hasConflictsOnly) params.has_conflicts = true;

      const res = await analysesApi.getVariants(selectedAnalysisId, params);
      setVariants(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err) {
      console.error('Failed to fetch variants:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedAnalysisId) {
      fetchVariants();
    }
  }, [selectedAnalysisId, page, pageSize, chromosome, tier, hasConflictsOnly]);

  const handleAnalysisChange = (newId) => {
    setSelectedAnalysisId(newId);
    setSearchParams({ analysisId: newId });
    setPage(1);
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchVariants();
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Genomic Variant Explorer</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Interactive multi-parametric exploration of parsed mutations, VEP transcripts, ClinVar assertions, and priority tiers.
          </p>
        </div>

        {/* Analysis Job Selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="analysis-select" className="text-xs font-semibold text-slate-500 uppercase tracking-wider shrink-0">
            Target Job:
          </label>
          <select
            id="analysis-select"
            value={selectedAnalysisId}
            onChange={(e) => handleAnalysisChange(e.target.value)}
            className="text-xs font-mono bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500 shadow-2xs"
          >
            {analyses.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id.slice(0, 8)}... ({a.variants_count} variants • {a.status})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Gene search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Filter by Gene Symbol (e.g. TP53, CFTR)..."
              value={gene}
              onChange={(e) => setGene(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500 text-slate-800"
            />
          </div>

          {/* Chromosome selector */}
          <select
            value={chromosome}
            onChange={(e) => {
              setChromosome(e.target.value);
              setPage(1);
            }}
            className="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          >
            {CHROMOSOMES.map((chr) => (
              <option key={chr} value={chr}>
                {chr === 'ALL' ? 'All Chromosomes' : chr}
              </option>
            ))}
          </select>

          {/* Prioritization Tier selector */}
          <select
            value={tier}
            onChange={(e) => {
              setTier(e.target.value);
              setPage(1);
            }}
            className="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-slate-800 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          >
            {TIERS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>

          {/* Search Trigger */}
          <button
            type="submit"
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
          >
            <Filter className="w-3.5 h-3.5" />
            <span>Apply Filters</span>
          </button>
        </form>

        {/* Second row toggles */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-100 text-xs">
          <label className="flex items-center gap-2 text-slate-700 cursor-pointer font-medium">
            <input
              type="checkbox"
              checked={hasConflictsOnly}
              onChange={(e) => {
                setHasConflictsOnly(e.target.checked);
                setPage(1);
              }}
              className="rounded text-blue-600 focus:ring-blue-500"
            />
            <span className="flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
              <span>Show Only Variants with Conflicting ClinVar Interpretations</span>
            </span>
          </label>

          <span className="text-slate-500 font-mono text-[11px]">
            Showing {variants.length} of {total} matching variant records
          </span>
        </div>
      </div>

      {/* Main Variant Data Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden flex flex-col">
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">Genomic Coordinates</th>
                <th className="py-3 px-3">Ref &gt; Alt</th>
                <th className="py-3 px-3">Gene</th>
                <th className="py-3 px-3">Primary Consequence</th>
                <th className="py-3 px-3">ClinVar Evidence</th>
                <th className="py-3 px-3">Candidate Prioritization</th>
                <th className="py-3 px-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 font-sans">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
                    <span>Loading variant data...</span>
                  </td>
                </tr>
              ) : variants.length > 0 ? (
                variants.map((v) => (
                  <tr
                    key={v.id}
                    onClick={() => setSelectedVariant(v)}
                    className="hover:bg-blue-50/40 transition-colors cursor-pointer group"
                  >
                    {/* Coordinates */}
                    <td className="py-3 px-3 font-semibold text-slate-900">
                      <span>{v.chromosome}:{v.position}</span>
                      {v.variant_identifier && (
                        <span className="block text-[11px] font-normal text-slate-400">
                          {v.variant_identifier}
                        </span>
                      )}
                    </td>

                    {/* Alleles */}
                    <td className="py-3 px-3 text-slate-700">
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 font-bold text-slate-800">
                        {v.reference_allele} &gt; {v.alternate_allele}
                      </span>
                    </td>

                    {/* Gene */}
                    <td className="py-3 px-3">
                      {v.primary_gene ? (
                        <span className="font-bold text-slate-900 bg-cyan-50 text-cyan-900 px-2 py-0.5 rounded border border-cyan-200">
                          {v.primary_gene}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic font-sans">—</span>
                      )}
                    </td>

                    {/* Consequence & Impact */}
                    <td className="py-3 px-3 font-sans space-y-1">
                      {v.primary_consequence ? (
                        <div>
                          <span className="font-mono text-xs text-blue-700 block">
                            {v.primary_consequence}
                          </span>
                          <ImpactBadge impact={v.primary_impact} />
                        </div>
                      ) : (
                        <span className="text-slate-400 italic text-xs">Unannotated</span>
                      )}
                    </td>

                    {/* ClinVar Evidence */}
                    <td className="py-3 px-3 font-sans">
                      <ClinVarBadge
                        interpretation={v.clinvar_interpretation}
                        reviewStatus={v.clinvar_review_status}
                        accession={v.clinvar_accession}
                        hasConflicts={v.has_conflicts}
                      />
                    </td>

                    {/* Prioritization Tier */}
                    <td className="py-3 px-3 font-sans">
                      <TierBadge category={v.priority_category} score={v.priority_score} />
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-3 text-right font-sans">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedVariant(v);
                        }}
                        className="px-2.5 py-1 bg-slate-100 group-hover:bg-blue-600 group-hover:text-white rounded-lg text-xs font-semibold text-slate-700 transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 font-sans">
                    <Dna className="w-8 h-8 stroke-1 mx-auto mb-2 text-slate-300" />
                    <p className="font-semibold text-slate-600">No matching variants found</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Try clearing or loosening your chromosome, gene, or tier filters.
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-700 focus:outline-hidden"
            >
              {[10, 25, 50, 100].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-mono">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 transition-colors"
                title="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 transition-colors"
                title="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Deep-Dive Inspection Modal */}
      {selectedVariant && (
        <VariantDetailsModal
          variant={selectedVariant}
          onClose={() => setSelectedVariant(null)}
        />
      )}
    </div>
  );
}
