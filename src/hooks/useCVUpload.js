import { useCallback, useState } from 'react';
import api, { errorMessage } from '../services/api';
import { CV_ACCEPTED_EXTENSIONS, CV_MAX_SIZE_MB } from '../data/constants';

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
    const previous = file;
    setFile(null);
    setProgress(1);
    try {
      const stored = await api.uploadCV(picked, setProgress);
      setFile(stored);
      onSuccess?.();
      // Replacing: remove the previous CV from the server (interviews that used it are kept).
      if (previous?.id) api.deleteCV(previous.id).catch((e) => console.error(e));
    } catch (e) {
      setError(errorMessage(e, 'Upload failed. Try again.'));
      setProgress(0);
      setFile(previous);
    }
  }, [file, setFile, onSuccess]);

  const remove = useCallback(async () => {
    if (!file) return;
    setError('');
    try {
      await api.deleteCV(file.id);
      setFile(null);
      setProgress(0);
    } catch (e) {
      setError(errorMessage(e, 'Could not remove the CV. Please try again.'));
    }
  }, [file, setFile]);

  const status = file ? 'done' : progress > 0 ? 'uploading' : 'idle';
  return { status, progress, error, upload, remove };
}
