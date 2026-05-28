export default function Footer() {
  const links = ['Compliance', 'Disclosures', 'Privacy Policy', 'Terms of Service'];

  return (
    <footer className="bg-bg border-t border-border py-12 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Top row: Logo and tagline */}
        <div className="mb-8">
          <span className="font-serif italic text-2xl text-accent">TickrAI</span>
          <p className="text-muted mt-2">
            Institutional-Grade Analysis for Every Investor
          </p>
        </div>

        {/* Middle row: Links */}
        <div className="flex flex-wrap gap-6 mb-8">
          {links.map((link) => (
            <a
              key={link}
              href="#"
              className="text-muted hover:text-accent transition-colors"
            >
              {link}
            </a>
          ))}
        </div>

        {/* Bottom row: Copyright */}
        <p className="text-sm text-muted mb-4">
          &copy; 2026 TickrAI. All rights reserved.
        </p>

        {/* Legal disclaimer */}
        <p className="text-xs text-muted max-w-2xl mx-auto text-center">
          TickrAI is not a registered investment adviser, broker-dealer, or research
          analyst. All content is for informational purposes only and should not be
          considered investment advice.
        </p>
      </div>
    </footer>
  );
}
