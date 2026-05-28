import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      <h1 className="text-6xl font-bold text-accent">404</h1>
      <p className="text-xl text-muted mt-4">Page not found</p>
      <Link
        to="/"
        className="mt-8 inline-block bg-accent text-white px-6 py-2.5 rounded-[8px] font-medium hover:bg-accent-hover transition-colors"
      >
        Back to Home
      </Link>
    </div>
  );
}
