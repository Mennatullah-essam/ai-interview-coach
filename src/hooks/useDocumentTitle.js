import { useEffect } from 'react';

export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · AI Interview Coach` : 'AI Interview Coach';
  }, [title]);
}
