export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const formatDate = (date = new Date()) =>
  date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

export const formatFileSize = (bytes) => `${(bytes / 1024).toFixed(0)} KB`;

export const getFirstName = (name) => name.trim().split(/\s+/)[0] ?? '';

export const getInitials = (name) =>
  name.split(/\s+/).filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
