import { useCallback, useState } from 'react';
import api from '../services/api';
import { CV_ACCEPTED_EXTENSIONS, CV_MAX_SIZE_MB } from '../data/constants';
import { formatFileSize } from '../utils/format';

/** Validation + upload progress for the CV step. `file` / `setFile` live in AppContext. */
export function useCVUpload({ file, setFile, onSuccess }) {
  const [progress, setProgress] = useState(file ? 100 : 0);
  const [error, setError] = useState('');

  const upload = useCallback(async (picked) => {
    if (!picked) return;
    const ext = picked.name.split('.').pop().toLowerCase();
    if (!CV_ACCEPTED_EXTENSIONS.includes(ext)) return setError('Unsupported format. Please upload a PDF or DOCX file.');
    if (picked.size > CV_MAX_SIZE_MB * 1024 * 1024) return setError(`File is too large. Maximum size is ${CV_MAX_SIZE_MB} MB.`);
    setError('');
    setFile(null);
    setProgress(1);
    try {
      const res = await api.uploadCV(picked, setProgress);
      setFile({ name: picked.name, ext: ext.toUpperCase(), size: formatFileSize(picked.size), id: res.id });
      onSuccess?.();
    } catch {
      setError('Upload failed. Try again.');
      setProgress(0);
    }
  }, [setFile, onSuccess]);

  const remove = useCallback(() => { setFile(null); setProgress(0); }, [setFile]);

  const status = file ? 'done' : progress > 0 ? 'uploading' : 'idle';
  return { status, progress, error, upload, remove };
}
