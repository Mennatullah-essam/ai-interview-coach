import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import AnimatedCheck from '../components/AnimatedCheck';
import Button from '../components/Button';
import Card from '../components/Card';
import Chip from '../components/Chip';
import DropZone from '../components/DropZone';
import InlineMessage from '../components/InlineMessage';
import ProgressBar from '../components/ProgressBar';
import { Reveal } from '../components/Reveal';
import { CV_ACCEPTED_EXTENSIONS } from '../data/constants';
import { swap } from '../animations/variants';
import { useApp } from '../hooks/useApp';
import { useCVUpload } from '../hooks/useCVUpload';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useToast } from '../hooks/useToast';

export default function CVUpload() {
  useDocumentTitle('Upload your CV');
  const navigate = useNavigate();
  const { cvFile, setCvFile } = useApp();
  const { say } = useToast();
  const input = useRef(null);
  const { status, progress, error, upload, remove } = useCVUpload({
    file: cvFile,
    setFile: setCvFile,
    onSuccess: () => say('CV uploaded successfully'),
  });

  const onPick = (e) => {
    upload(e.target.files[0]);
    e.target.value = ''; // allow picking the same file again
  };

  return (
    <div className="wrap narrow">
      <Reveal>
        <h2>Upload your CV</h2>
        <p className="mut lead">Your CV personalizes the interview — questions are built around your skills, projects and experience.</p>
      </Reveal>
      <input ref={input} type="file" accept={CV_ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',')} hidden aria-label="Choose CV file" onChange={onPick} />

      <AnimatePresence mode="wait" initial={false}>
        {status === 'idle' && (
          <motion.div key="idle" {...swap}>
            <DropZone onFile={upload} onBrowse={() => input.current.click()} />
          </motion.div>
        )}
        {status === 'uploading' && (
          <motion.div key="uploading" {...swap}>
            <Card role="status">
              <b>Uploading &amp; analyzing…</b>
              <ProgressBar className="mt-md" ariaLabel="Upload progress" value={progress} fast />
              <span className="mut">{progress}%</span>
            </Card>
          </motion.div>
        )}
        {status === 'done' && (
          <motion.div key="done" {...swap}>
            <Card>
              <div className="row sp">
                <div className="row">
                  <motion.div className="ico flat file-ico" initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 400, damping: 14 }} aria-hidden="true">
                    📄
                    <motion.span className="pulse-ring" initial={{ opacity: 0.7, scale: 1 }} animate={{ opacity: 0, scale: 1.7 }} transition={{ duration: 1, delay: 0.15 }} />
                  </motion.div>
                  <div>
                    <b>{cvFile.name}</b>
                    <div className="mut">{cvFile.ext} · {cvFile.size}</div>
                  </div>
                </div>
                <Chip tone="ok"><AnimatedCheck />Uploaded</Chip>
              </div>
              <div className="row mt-md">
                <Button onClick={() => input.current.click()}>Replace</Button>
                <Button onClick={remove}>Remove</Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <InlineMessage variant="box" message={error} />

      <div className="mt-lg" style={{ textAlign: 'right' }}>
        <Button variant="primary" disabled={!cvFile} onClick={() => navigate('/interview/setup')}>Continue to Job Role →</Button>
      </div>
    </div>
  );
}
