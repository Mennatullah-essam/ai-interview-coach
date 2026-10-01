import { useState } from 'react';
import { motion } from 'framer-motion';
import Button from './Button';
import { CV_MAX_SIZE_MB } from '../data/constants';

/** Drag-and-drop target for the CV. It scales and glows while a file is dragged over it. */
export default function DropZone({ onFile, onBrowse }) {
  const [over, setOver] = useState(false);

  return (
    <motion.div
      className={`drop${over ? ' over' : ''}`}
      role="group"
      aria-label="CV drop zone"
      animate={{ scale: over ? 1.02 : 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      onDragEnter={(e) => { e.preventDefault(); setOver(true); }}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(false); }}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files[0]); }}
    >
      <motion.div className="drop-icon" aria-hidden="true" animate={over ? { y: -10, scale: 1.15 } : { y: [0, -6, 0], scale: 1 }} transition={over ? { duration: 0.2 } : { duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}>☁️</motion.div>
      <h3 style={{ margin: '8px 0' }}>{over ? 'Drop to upload' : 'Drag & drop your CV here'}</h3>
      <p className="mut">Supported formats: PDF, DOCX · Max {CV_MAX_SIZE_MB} MB</p>
      <Button variant="primary" className="mt-md" onClick={onBrowse}>Browse files</Button>
    </motion.div>
  );
}
