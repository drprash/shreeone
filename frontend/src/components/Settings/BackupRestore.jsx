import React, { useState, useRef } from 'react';
import api from '../../services/api';

const MODULE_LABELS = {
  core: 'Core (family, users, accounts, transactions, categories, permissions, currencies)',
  automation: 'Automation (recurring payments, budget settings)',
  exchange_rates: 'Exchange Rates (historical rates — re-fetched automatically daily)',
  audit_logs: 'Audit Logs (full activity history — can be large)',
};

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const SectionCard = ({ title, description, children }) => (
  <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-6 space-y-4">
    <div>
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>
    </div>
    {children}
  </div>
);

const Alert = ({ type, children }) => {
  const styles = {
    error: 'bg-red-50 border-red-200 text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400',
    success: 'bg-green-50 border-green-200 text-green-700 dark:bg-green-900/20 dark:border-green-800 dark:text-green-400',
    warning: 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-400',
    info: 'bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400',
  };
  return (
    <div className={`p-3 border rounded-lg text-sm ${styles[type]}`}>{children}</div>
  );
};

const RowCountBadge = ({ label, counts }) => (
  <div className="bg-slate-50 dark:bg-slate-700 rounded-lg p-3">
    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
      {label}
    </p>
    <div className="flex flex-wrap gap-2">
      {Object.entries(counts).map(([key, count]) => (
        <span
          key={key}
          className="inline-flex items-center gap-1 px-2 py-0.5 bg-white dark:bg-slate-600 border border-slate-200 dark:border-slate-500 rounded text-xs text-slate-600 dark:text-slate-300"
        >
          <span className="font-medium">{count.toLocaleString()}</span>
          <span className="text-slate-400 dark:text-slate-400">{key.replace(/_/g, ' ')}</span>
        </span>
      ))}
    </div>
  </div>
);

const BackupRestore = () => {
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [options, setOptions] = useState({
    include_automation: true,
    include_exchange_rates: false,
    include_audit_logs: false,
  });
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupError, setBackupError] = useState(null);
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [parsedManifest, setParsedManifest] = useState(null);
  const [fileParseError, setFileParseError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreError, setRestoreError] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);

  const handleLoadPreview = async () => {
    setPreviewLoading(true);
    setBackupError(null);
    try {
      const res = await api.get('/admin/backup/preview');
      setPreview(res.data);
    } catch (err) {
      setBackupError(err.response?.data?.detail || 'Failed to load preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownload = async () => {
    setBackupLoading(true);
    setBackupError(null);
    try {
      const res = await api.post('/admin/backup', null, {
        params: options,
        responseType: 'blob',
      });

      // Extract filename from Content-Disposition or generate one
      const disposition = res.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `shreeone_backup_${Date.now()}.json`;

      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setBackupError(err.response?.data?.detail || 'Backup download failed');
    } finally {
      setBackupLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setParsedManifest(null);
    setFileParseError(null);
    setRestoreResult(null);
    setRestoreError(null);

    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target.result);
        const manifest = json.backup_manifest;
        if (!manifest) throw new Error('Missing backup_manifest');
        setParsedManifest(manifest);
      } catch {
        setFileParseError('This file is not a valid ShreeOne backup.');
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.readAsText(file);
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setParsedManifest(null);
    setFileParseError(null);
    setRestoreResult(null);
    setRestoreError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRestore = async () => {
    setRestoreLoading(true);
    setRestoreError(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const res = await api.post('/admin/backup/restore', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setRestoreResult(res.data);
      setShowConfirmModal(false);
      setSelectedFile(null);
      setParsedManifest(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setRestoreError(err.response?.data?.detail || 'Restore failed');
      setShowConfirmModal(false);
    } finally {
      setRestoreLoading(false);
      setConfirmInput('');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Backup & Restore</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Download a full export of your family data, or restore from a previous backup.
          Only the Family Admin can perform these operations.
        </p>
      </div>

      {/* ── Create Backup ─────────────────────────────────────────────────── */}
      <SectionCard
        title="Create Backup"
        description="Download your family data as a signed JSON file."
      >
        {backupError && <Alert type="error">{backupError}</Alert>}

        {/* Preview row counts */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Data preview (row counts per module)
            </p>
            <button
              onClick={handleLoadPreview}
              disabled={previewLoading}
              className="text-xs px-3 py-1.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors disabled:opacity-50"
            >
              {previewLoading ? 'Loading…' : preview ? 'Refresh' : 'Load preview'}
            </button>
          </div>

          {preview && (
            <div className="space-y-2">
              <RowCountBadge label="Core (always included)" counts={preview.core} />
              <RowCountBadge label="Automation" counts={preview.automation} />
              <RowCountBadge label="Exchange Rates" counts={preview.exchange_rates} />
              <RowCountBadge label="Audit Logs" counts={preview.audit_logs} />
            </div>
          )}
        </div>

        {/* Module options */}
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
            Optional modules to include
          </p>

          {/* Core always-on chip */}
          <div className="flex items-center gap-3 mb-2 opacity-60 cursor-not-allowed select-none">
            <div className="w-4 h-4 rounded bg-indigo-600 flex items-center justify-center flex-shrink-0">
              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </div>
            <span className="text-sm text-slate-600 dark:text-slate-400">
              {MODULE_LABELS.core}
            </span>
          </div>

          {[
            { key: 'include_automation', moduleKey: 'automation' },
            { key: 'include_exchange_rates', moduleKey: 'exchange_rates' },
            { key: 'include_audit_logs', moduleKey: 'audit_logs' },
          ].map(({ key, moduleKey }) => (
            <label key={key} className="flex items-center gap-3 mb-2 cursor-pointer">
              <input
                type="checkbox"
                checked={options[key]}
                onChange={(e) => setOptions({ ...options, [key]: e.target.checked })}
                className="w-4 h-4 rounded accent-indigo-600"
              />
              <span className="text-sm text-slate-600 dark:text-slate-400">
                {MODULE_LABELS[moduleKey]}
              </span>
            </label>
          ))}
        </div>

        <button
          onClick={handleDownload}
          disabled={backupLoading}
          className="w-full px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {backupLoading ? 'Preparing backup…' : 'Download Backup'}
        </button>

        <Alert type="info">
          The backup file is cryptographically signed. Do not edit the file — the signature
          will fail on restore. Store it in a secure location as it contains sensitive financial data.
        </Alert>
      </SectionCard>

      {/* ── Restore Backup ────────────────────────────────────────────────── */}
      <SectionCard
        title="Restore from Backup"
        description="Upload a previously downloaded backup file to overwrite the current family data."
      >
        {restoreError && <Alert type="error">{restoreError}</Alert>}

        {restoreResult && (
          <div className="space-y-3">
            <Alert type="success">
              <p className="font-semibold mb-1">Restore completed successfully</p>
              <p className="text-xs">
                Backup generated: {formatDate(restoreResult.backup_generated_at)}
                {' · '}
                Modules restored: {restoreResult.modules_restored.join(', ')}
              </p>
            </Alert>
            {restoreResult.warnings?.length > 0 && (
              <div className="space-y-1">
                {restoreResult.warnings.map((w, i) => (
                  <Alert key={i} type="warning">{w}</Alert>
                ))}
              </div>
            )}
          </div>
        )}

        <Alert type="warning">
          <strong>Destructive operation.</strong> Restoring a backup will permanently overwrite all
          current family data. This action cannot be undone. All family members will be logged out.
          Password hashes and passkey credentials are not restored — all users will need to
          reset their passwords.
        </Alert>

        {/* File input */}
        {!selectedFile ? (
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Select backup file
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={handleFileChange}
              className="block w-full text-sm text-slate-600 dark:text-slate-400
                file:mr-3 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-medium
                file:bg-indigo-50 file:text-indigo-700
                dark:file:bg-indigo-900/30 dark:file:text-indigo-300
                hover:file:bg-indigo-100 dark:hover:file:bg-indigo-900/50
                file:cursor-pointer"
            />
            {fileParseError && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{fileParseError}</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Manifest preview */}
            {parsedManifest && (
              <div className="bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg p-4 space-y-2">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Backup details
                </p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <span className="text-slate-500 dark:text-slate-400">File</span>
                  <span className="text-slate-700 dark:text-slate-200 truncate">{selectedFile.name}</span>
                  <span className="text-slate-500 dark:text-slate-400">Generated</span>
                  <span className="text-slate-700 dark:text-slate-200">
                    {formatDate(parsedManifest.generated_at)}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">Type</span>
                  <span className="text-slate-700 dark:text-slate-200 capitalize">
                    {parsedManifest.backup_type}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">Modules</span>
                  <span className="text-slate-700 dark:text-slate-200">
                    {parsedManifest.included_modules?.join(', ')}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">Schema</span>
                  <span className="text-slate-700 dark:text-slate-200">
                    v{parsedManifest.schema_version}
                  </span>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setShowConfirmModal(true)}
                disabled={restoreLoading || !parsedManifest}
                className="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {restoreLoading ? 'Restoring…' : 'Restore this backup'}
              </button>
              <button
                onClick={handleClearFile}
                disabled={restoreLoading}
                className="px-4 py-2.5 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-500 transition-colors font-medium disabled:opacity-50"
              >
                Clear
              </button>
            </div>
          </div>
        )}
      </SectionCard>

      {/* ── Confirmation Modal ─────────────────────────────────────────────── */}
      {showConfirmModal && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50 p-4">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-md w-full p-6 slide-in space-y-4">
            <h3 className="text-xl font-bold text-red-600 dark:text-red-400">
              Confirm Restore
            </h3>

            <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
              <p>
                You are about to <strong>permanently overwrite</strong> all current family data
                with the backup from:
              </p>
              <p className="font-mono text-xs bg-slate-100 dark:bg-slate-700 rounded px-3 py-2">
                {formatDate(parsedManifest?.generated_at)}
              </p>
              <ul className="list-disc list-inside space-y-1 mt-2">
                <li>All active sessions will be invalidated</li>
                <li>All users must reset their passwords</li>
                <li>Passkey credentials will be lost</li>
                <li>This cannot be undone</li>
              </ul>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Type <strong>RESTORE</strong> to confirm
              </label>
              <input
                type="text"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                placeholder="RESTORE"
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:border-red-500"
                autoFocus
              />
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleRestore}
                disabled={confirmInput !== 'RESTORE' || restoreLoading}
                className="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {restoreLoading ? 'Restoring…' : 'Yes, Restore'}
              </button>
              <button
                onClick={() => {
                  setShowConfirmModal(false);
                  setConfirmInput('');
                }}
                disabled={restoreLoading}
                className="flex-1 px-4 py-2.5 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-500 transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BackupRestore;
