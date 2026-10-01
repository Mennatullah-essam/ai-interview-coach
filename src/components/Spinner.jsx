export default function Spinner({ label, className = '' }) {
  return (
    <div role="status" className={className}>
      <div className="spin" aria-hidden="true" />
      {label && <p className="mut mt-md" style={{ textAlign: 'center' }}>{label}</p>}
    </div>
  );
}
