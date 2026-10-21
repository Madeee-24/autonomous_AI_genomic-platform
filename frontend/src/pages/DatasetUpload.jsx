import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileCheck,
  AlertCircle,
  CheckCircle2,
  Play,
  RefreshCw,
  HardDrive,
  FileText,
} from 'lucide-react';
import { datasetsApi, analysesApi } from '../services/api';

export default function DatasetUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [assembly, setAssembly] = useState('GRCh38');
  const [dragActive, setDragActive] = useState(false);

  // Pre-flight validation state
  const [validating, setValidating] = useState(false);
  const [preflightResult, setPreflightResult] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Uploading state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadSuccess, setUploadSuccess] = useState(null);

  // Launch Analysis Modal
  const [activeDatasetForJob, setActiveDatasetForJob] = useState(null);
  const [jobOptions, setJobOptions] = useState({
    annotate_with_vep: true,
    retrieve_clinvar_evidence: true,
    generate_ai_explanations: false,
  });
  const [launching, setLaunching] = useState(false);

  // Existing datasets table
  const [datasets, setDatasets] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  const fetchDatasets = async () => {
    setLoadingDatasets(true);
    try {
      const res = await datasetsApi.list();
      setDatasets(res.items || []);
    } catch (err) {
      console.error('Failed to list datasets:', err);
    } finally {
      setLoadingDatasets(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (file) => {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.vcf') && !name.endsWith('.vcf.gz')) {
      setValidationError("Invalid file extension. Please select a '.vcf' or '.vcf.gz' genomic file.");
      setSelectedFile(null);
      return;
    }
    setValidationError(null);
    setPreflightResult(null);
    setUploadSuccess(null);
    setSelectedFile(file);
  };

  const handlePreflightValidate = async () => {
    if (!selectedFile) return;
    setValidating(true);
    setValidationError(null);
    setPreflightResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('assembly', assembly);

    try {
      const res = await datasetsApi.validateOnly(formData);
      setPreflightResult(res);
    } catch (err) {
      setValidationError(err.message || 'Validation inspection failed.');
    } finally {
      setValidating(false);
    }
  };

  const handleUploadAndSave = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadProgress(0);
    setValidationError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('assembly', assembly);

    try {
      const res = await datasetsApi.upload(formData, (percent) => {
        setUploadProgress(percent);
      });
      setUploadSuccess(res);
      setSelectedFile(null);
      setPreflightResult(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchDatasets();
      // Prompt user to immediately launch analysis
      setActiveDatasetForJob({
        id: res.dataset_id,
        filename: res.original_filename,
        assembly: res.assembly,
      });
    } catch (err) {
      setValidationError(err.message || 'Failed to upload dataset.');
    } finally {
      setUploading(false);
    }
  };

  const handleLaunchAnalysis = async () => {
    if (!activeDatasetForJob) return;
    setLaunching(true);
    try {
      const job = await analysesApi.create({
        dataset_id: activeDatasetForJob.id,
        genome_assembly: activeDatasetForJob.assembly,
        options: jobOptions,
      });
      setActiveDatasetForJob(null);
      navigate(`/analyses/${job.id}`);
    } catch (err) {
      alert(`Could not start analysis: ${err.message}`);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="pb-2 border-b border-slate-200">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Dataset Ingestion & Validation</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Upload and validate genomic Variant Call Format (VCFv4.2) files. Ensure accurate genome assembly alignment before initiating analysis.
        </p>
      </div>

      {/* Upload & Preflight Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Zone Card */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-5">
          <h2 className="text-base font-semibold text-slate-900">1. Select Reference Assembly & VCF File</h2>

          {/* Assembly selector */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-3 bg-slate-50 rounded-xl border border-slate-200">
            <label htmlFor="assembly-select" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Genome Assembly:
            </label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                <input
                  id="assembly-select"
                  type="radio"
                  name="assembly"
                  value="GRCh38"
                  checked={assembly === 'GRCh38'}
                  onChange={(e) => setAssembly(e.target.value)}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span>GRCh38 / hg38 (Recommended Modern)</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  name="assembly"
                  value="GRCh37"
                  checked={assembly === 'GRCh37'}
                  onChange={(e) => setAssembly(e.target.value)}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span>GRCh37 / hg19 (Legacy)</span>
              </label>
            </div>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              dragActive
                ? 'border-blue-500 bg-blue-50/50'
                : 'border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".vcf,.gz"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
              <UploadCloud className="w-6 h-6" />
            </div>
            <p className="text-sm font-semibold text-slate-800">
              {selectedFile ? selectedFile.name : 'Click to browse or drag and drop VCF file'}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports standard VCF v4.2 or bgzipped .vcf.gz (Up to 100 MB)
            </p>
            {selectedFile && (
              <span className="mt-3 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-mono font-medium">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for inspection
              </span>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handlePreflightValidate}
              disabled={!selectedFile || validating || uploading}
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <FileCheck className={`w-4 h-4 ${validating ? 'animate-spin' : ''}`} />
              <span>{validating ? 'Inspecting VCF...' : 'Pre-Flight Inspect'}</span>
            </button>

            <button
              onClick={handleUploadAndSave}
              disabled={!selectedFile || uploading || validating}
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-2 transition-colors shadow-xs shadow-blue-500/20 disabled:opacity-50"
            >
              <UploadCloud className={`w-4 h-4 ${uploading ? 'animate-bounce' : ''}`} />
              <span>{uploading ? `Uploading (${uploadProgress}%)...` : 'Upload & Store Dataset'}</span>
            </button>
          </div>

          {/* Progress bar */}
          {uploading && (
            <div className="space-y-1">
              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500 text-right font-mono">{uploadProgress}% complete</p>
            </div>
          )}

          {/* Error Banner */}
          {validationError && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Validation Rejected</p>
                <p className="mt-0.5 leading-relaxed">{validationError}</p>
              </div>
            </div>
          )}

          {/* Upload Success Banner */}
          {uploadSuccess && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold">Dataset Stored Successfully</p>
                <p className="mt-0.5 font-mono text-[11px] text-emerald-800">
                  ID: {uploadSuccess.dataset_id} • Verified Assembly: {uploadSuccess.assembly} • SHA-256: {uploadSuccess.file_checksum.slice(0, 16)}...
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Pre-Flight Inspection Details Panel */}
        <div className="lg:col-span-1 bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs flex flex-col">
          <h2 className="text-base font-semibold text-slate-900 mb-1">Pre-Flight Metrics</h2>
          <p className="text-xs text-slate-500 mb-4">Integrity checks prior to analysis</p>

          {preflightResult ? (
            <div className="space-y-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">Structure:</span>
                  <span className={`font-semibold ${preflightResult.validation_summary.is_valid ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {preflightResult.validation_summary.is_valid ? 'Valid VCFv4.2' : 'Invalid'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Header Assembly:</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {preflightResult.validation_summary.detected_assembly || 'Undeclared'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sample Count:</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {preflightResult.validation_summary.sample_count}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Accepted Records:</span>
                  <span className="font-mono font-bold text-blue-700">
                    {preflightResult.validation_summary.accepted_variants_count}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Contigs Declared:</span>
                  <span className="font-mono text-slate-700">
                    {preflightResult.validation_summary.contigs_declared.length} contig(s)
                  </span>
                </div>
              </div>

              {preflightResult.can_proceed_to_analysis ? (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Ready to upload & analyze. File passes all syntax rules.</span>
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>File contains structural warnings or zero accepted variants.</span>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-400">
              <FileCheck className="w-10 h-10 stroke-1 mb-2 text-slate-300" />
              <p className="text-xs">No inspection run yet.</p>
              <p className="text-[11px] text-slate-400 mt-1">
                Select a VCF file and click "Pre-Flight Inspect" to inspect header contigs and format specifications.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Existing Uploaded Datasets Table */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Stored Genomic Datasets</h2>
            <p className="text-xs text-slate-500">Catalog of securely registered VCF files available for analysis</p>
          </div>
          <button
            onClick={fetchDatasets}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
            title="Refresh datasets"
          >
            <RefreshCw className={`w-4 h-4 ${loadingDatasets ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          {datasets.length > 0 ? (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-y border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Filename</th>
                  <th className="py-2.5 px-3">Assembly</th>
                  <th className="py-2.5 px-3">Size</th>
                  <th className="py-2.5 px-3 text-right">Variants</th>
                  <th className="py-2.5 px-3">Uploaded</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {datasets.map((d) => (
                  <tr key={d.dataset_id} className="hover:bg-slate-50 font-mono">
                    <td className="py-3 px-3 font-medium text-slate-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-blue-500 shrink-0" />
                      <span>{d.original_filename}</span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px] font-semibold">
                        {d.assembly}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      {(d.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-blue-700">
                      {d.variant_count}
                    </td>
                    <td className="py-3 px-3 text-slate-500 font-sans text-[11px]">
                      {new Date(d.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() =>
                          setActiveDatasetForJob({
                            id: d.dataset_id,
                            filename: d.original_filename,
                            assembly: d.assembly,
                          })
                        }
                        className="px-3 py-1 bg-blue-50 hover:bg-blue-600 text-blue-700 hover:text-white rounded-lg text-xs font-semibold font-sans transition-colors inline-flex items-center gap-1.5"
                      >
                        <Play className="w-3 h-3" />
                        <span>Run Analysis</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="h-32 flex flex-col items-center justify-center text-center text-slate-400">
              <HardDrive className="w-8 h-8 stroke-1 mb-2 text-slate-300" />
              <p className="text-xs">No genomic datasets uploaded yet.</p>
            </div>
          )}
        </div>
      </div>

      {/* Launch Analysis Modal */}
      {activeDatasetForJob && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="launch-analysis-title"
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
                <Play className="w-5 h-5" />
              </div>
              <div>
                <h3 id="launch-analysis-title" className="text-base font-bold text-slate-900">Configure & Launch Analysis</h3>
                <p className="text-xs text-slate-500 font-mono">{activeDatasetForJob.filename}</p>
              </div>
            </div>

            <div className="space-y-3 py-2 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-slate-500 block mb-1 font-medium">Target Genome Assembly:</span>
                <span className="font-mono font-bold text-slate-800">{activeDatasetForJob.assembly}</span>
              </div>

              <div className="space-y-2 pt-2">
                <span className="font-semibold text-slate-800 block text-xs">Pipeline Workflow Stages:</span>

                <label className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={jobOptions.annotate_with_vep}
                    onChange={(e) =>
                      setJobOptions({ ...jobOptions, annotate_with_vep: e.target.checked })
                    }
                    className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="font-semibold text-slate-900 block">Ensembl VEP Consequence Annotation</span>
                    <span className="text-[11px] text-slate-500">
                      Queries Ensembl REST API for gene transcripts, consequences, and impacts.
                    </span>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={jobOptions.retrieve_clinvar_evidence}
                    onChange={(e) =>
                      setJobOptions({ ...jobOptions, retrieve_clinvar_evidence: e.target.checked })
                    }
                    className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="font-semibold text-slate-900 block">NCBI ClinVar Evidence Retrieval</span>
                    <span className="text-[11px] text-slate-500">
                      Fetches clinical significance, review status stars, and conflicts.
                    </span>
                  </div>
                </label>

                <div className="p-2.5 bg-blue-50/50 rounded-lg border border-blue-100 text-[11px] text-blue-900">
                  <span className="font-semibold block">Transparent Heuristic Prioritization (Active)</span>
                  <span>Automatically calculates candidate scores (0-100) and categorizes into Tiers 1-4.</span>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                onClick={() => setActiveDatasetForJob(null)}
                className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleLaunchAnalysis}
                disabled={launching}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs shadow-blue-500/20 disabled:opacity-50"
              >
                <Play className={`w-3.5 h-3.5 ${launching ? 'animate-spin' : ''}`} />
                <span>{launching ? 'Starting Pipeline...' : 'Start Analysis Job'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
