import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui/StateBox";

export function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState icon="🧭" title="Page not found">
        <p>The page you're looking for doesn't exist.</p>
        <Link className="btn" to="/dashboard">Back to dashboard</Link>
      </EmptyState>
    </div>
  );
}
