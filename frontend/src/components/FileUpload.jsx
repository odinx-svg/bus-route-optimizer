import React, { useCallback, useState, useRef } from 'react';
import { Upload, AlertCircle, X, Loader2, FileSpreadsheet } from 'lucide-react';

export default function FileUpload({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const inputRef = useRef(null);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const validateFiles = (files) => {
    const validFiles = Array.from(files).filter(f =>
      f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
    );
    if (validFiles.length === 0) {
      setError('Selecciona archivos Excel válidos (.xlsx o .xls)');
      return null;
    }
    if (validFiles.length !== files.length) {
      setError(`${files.length - validFiles.length} archivo(s) ignorado(s)`);
    }
    return validFiles;
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const validFiles = validateFiles(e.dataTransfer.files);
    if (validFiles) {
      setSelectedFiles(prev => [...prev, ...validFiles]);
      setError(null);
    }
  }, []);

  const handleChange = (e) => {
    const validFiles = validateFiles(e.target.files);
    if (validFiles) {
      setSelectedFiles(prev => [...prev, ...validFiles]);
      setError(null);
    }
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setError(null);
  };

  const clearFiles = () => {
    setSelectedFiles([]);
    setError(null);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach(file => formData.append('files', file));

      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

      const response = await fetch(`${apiUrl}/upload/analyze`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (!response.ok) {
        let errorMsg = 'Error al subir';
        try {
          const errData = await response.json();
          if (typeof errData?.detail === 'string') {
            errorMsg = errData.detail;
          } else if (typeof errData?.detail?.message === 'string') {
            errorMsg = errData.detail.message;
          } else {
            errorMsg = `Error del servidor: ${response.status}`;
          }
        } catch {
          errorMsg = `Error del servidor: ${response.status}`;
        }
        throw new Error(errorMsg);
      }

      const data = await response.json();
      const routes = Array.isArray(data) ? data : data?.routes;

      if (!routes || (Array.isArray(routes) && routes.length === 0)) {
        throw new Error('No se encontraron rutas en los archivos');
      }

      onUploadSuccess({
        routes,
        parse_report: data?.parse_report || null,
      });
      setSelectedFiles([]);
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message || 'Error al subir');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative border border-dashed rounded-[14px] p-6 text-center
          transition-all duration-200 cursor-pointer
          ${dragActive
            ? 'border-indigo-500/50 bg-indigo-500/[0.06]'
            : 'border-white/[0.1] hover:border-white/[0.2] hover:bg-white/[0.02]'
          }
          ${uploading ? 'pointer-events-none opacity-50' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".xlsx,.xls"
          onChange={handleChange}
          disabled={uploading}
          className="hidden"
        />
        <div className="space-y-3">
          <div className={`
            w-12 h-12 mx-auto rounded-[12px] flex items-center justify-center transition-colors
            ${dragActive ? 'bg-indigo-500/[0.1]' : 'bg-white/[0.04]'}
          `}>
            <Upload className={`w-5 h-5 ${dragActive ? 'text-indigo-400' : 'text-zinc-500'}`} />
          </div>
          <div>
            <p className="text-[13px] font-medium text-zinc-300">
              {dragActive ? 'Suelta los archivos aquí' : 'Arrastra archivos Excel o examinar'}
            </p>
            <p className="text-[11px] text-zinc-600 mt-1">
              Formatos .xlsx y .xls
            </p>
          </div>
        </div>
      </div>

      {/* Selected Files */}
      {selectedFiles.length > 0 && (
        <div className="bg-white/[0.03] border border-white/[0.06] rounded-[14px] p-3 animate-fadeIn">
          <div className="flex items-center justify-between mb-2.5">
            <span className="text-[11px] font-medium text-zinc-400">
              {selectedFiles.length} archivo{selectedFiles.length > 1 ? 's' : ''}
            </span>
            {!uploading && (
              <button
                onClick={clearFiles}
                className="p-1 hover:bg-white/[0.06] rounded-md transition-colors"
              >
                <X className="w-3.5 h-3.5 text-zinc-500 hover:text-red-400" />
              </button>
            )}
          </div>

          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {selectedFiles.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2.5 p-2 bg-white/[0.03] rounded-[10px] group hover:bg-white/[0.05] transition-colors"
              >
                <FileSpreadsheet className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] text-zinc-300 truncate">{file.name}</p>
                  <p className="text-[10px] text-zinc-600">{formatFileSize(file.size)}</p>
                </div>
                {!uploading && (
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                    className="p-1 hover:bg-red-500/[0.1] rounded-md transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <X className="w-3 h-3 text-zinc-500 hover:text-red-400" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2.5 p-3 bg-red-500/[0.06] border border-red-500/[0.12] rounded-[12px] animate-shake">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-[12px] text-red-400">{error}</p>
        </div>
      )}

      {/* Upload Button */}
      {selectedFiles.length > 0 && (
        <button
          onClick={uploading ? undefined : handleUpload}
          disabled={uploading}
          className={`
            w-full py-3 font-medium rounded-[12px] transition-colors text-[13px]
            flex items-center justify-center gap-2
            ${uploading
              ? 'bg-indigo-600/50 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-500'
            }
            text-white
          `}
        >
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Subiendo...</span>
              <span className="text-[11px] opacity-70">{uploadProgress}%</span>
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              Subir {selectedFiles.length} archivo{selectedFiles.length > 1 ? 's' : ''}
            </>
          )}
        </button>
      )}

      {/* Progress bar */}
      {uploading && (
        <div className="h-[3px] bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 transition-all duration-300 ease-out rounded-full"
            style={{ width: `${uploadProgress}%` }}
          />
        </div>
      )}
    </div>
  );
}
