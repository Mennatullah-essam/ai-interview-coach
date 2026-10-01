export default function Skeleton({ n = 3 }) {
  return (
    <div className="g" role="status" aria-label="Loading">
      {Array.from({ length: n }, (_, i) => <div key={i} className="sk" />)}
    </div>
  );
}
