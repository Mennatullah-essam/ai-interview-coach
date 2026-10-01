import { useId } from 'react';
import Modal from './Modal';
import Button from './Button';

export default function ConfirmModal({ title, text, confirmLabel, onConfirm, onCancel }) {
  const titleId = useId();
  return (
    <Modal onClose={onCancel} labelledBy={titleId} size="sm">
      <h3 id={titleId}>{title}</h3>
      <p className="mut" style={{ margin: '8px 0 20px' }}>{text}</p>
      <div className="row end">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="primary" onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}
