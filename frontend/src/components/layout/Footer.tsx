export default function Footer() {
  return (
    <footer className="bg-bg border-t border-border py-10 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <span className="font-serif italic text-2xl text-accent">TickrAI</span>
          <p className="text-sm text-muted">&copy; 2026 TickrAI. All rights reserved.</p>
        </div>
        <p className="text-xs text-muted max-w-2xl">
          TickrAI is not a registered investment adviser, broker-dealer, or research
          analyst. All content is for informational purposes only and should not be
          considered investment advice.
        </p>
      </div>
    </footer>
  );
}
