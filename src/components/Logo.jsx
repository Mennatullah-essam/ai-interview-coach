import { Link } from 'react-router-dom';

/** Brand mark; a link to the landing page unless `to` is omitted. */
export default function Logo({ to }) {
  const content = (<><i aria-hidden="true">AI</i>Interview Coach</>);
  return to ? <Link to={to} className="logo" aria-label="AI Interview Coach home">{content}</Link> : <div className="logo">{content}</div>;
}
