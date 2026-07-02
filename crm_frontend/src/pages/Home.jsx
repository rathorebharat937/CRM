import { Link } from "react-router-dom";

import AppIcon from "../components/AppIcon";
import { LANDING_APPS, LANDING_PLATFORM_APPS, LANDING_PORTALS } from "../config/appCatalog";

const DIFFERENTIATORS = [
  "GST quotations & invoices",
  "Payment due follow-ups",
  "Lead reminder queues",
  "WhatsApp-friendly notes",
  "Made for Indian teams",
];

const NICHES = [
  "Agencies & consultants",
  "CAs & advocates",
  "Interior designers",
  "NGOs & foundations",
  "B2B sales teams",
  "Service businesses",
];

function Home() {
  return (
    <div className="crm-landing">
      <header className="crm-landing-topbar">
        <Link to="/" className="crm-landing-brand" aria-label="BlackPapers home">
          <img src="/branding/logo.svg" alt="" className="crm-landing-logo" />
          <span>BlackPapers</span>
        </Link>
        <nav className="crm-landing-topnav">
          <a href="#apps">Apps</a>
          <a href="#sign-in">Sign in</a>
          <a href="#sign-in" className="crm-landing-cta">
            Get started
          </a>
        </nav>
      </header>

      <section className="crm-landing-hero">
        <p className="crm-landing-eyebrow">BlackPapers · business operating software</p>
        <h1>
          Your paperwork,{" "}
          <span className="crm-landing-highlight">finally in one place</span>
        </h1>
        <p className="crm-landing-lead">
          From the first lead call to the last payment receipt — manage clients,
          GST billing, dues, tasks, and team work on one dashboard. Built for
          agencies, consultants, CAs, NGOs, traders, and growing Indian teams
          who want clarity, not clutter.
        </p>
        <div className="crm-landing-pills">
          {DIFFERENTIATORS.map((item) => (
            <span key={item} className="crm-landing-pill">
              {item}
            </span>
          ))}
        </div>
        <div className="crm-landing-hero-actions">
          <a href="#sign-in" className="crm-btn crm-btn-primary">
            Choose your workspace
          </a>
          <Link to="/user-signup" className="crm-btn crm-btn-ghost">
            Create portal account
          </Link>
        </div>
      </section>

      <section id="apps" className="crm-landing-apps-wrap">
        <div className="crm-landing-apps-panel">
          <p className="crm-landing-apps-intro">
            Open only what you need — leads, quotes, GST invoices, and payment
            follow-ups on day one. Switch on HR, payroll, inventory, and
            platform apps (website, store, POS, manufacturing, AI) as you
            grow. Same login, same company profile, same BlackPapers workspace.
          </p>
          <div className="crm-app-grid crm-app-grid-landing">
            {LANDING_APPS.map((app) => (
              <div
                key={app.id}
                className="crm-app-tile crm-app-tile-static"
                style={{ "--app-accent": app.color }}
              >
                <AppIcon name={app.icon} color={app.color} />
                <span className="crm-app-tile-label">{app.label}</span>
                <span className="crm-app-tile-sub">{app.subtitle}</span>
              </div>
            ))}
          </div>

          <h3 className="crm-landing-platform-heading">Platform &amp; Growth</h3>
          <p className="crm-landing-apps-intro crm-landing-platform-intro">
            Fourteen platform modules — website, store, POS, manufacturing, quality,
            maintenance, field service, subscriptions, rental, workflows, marketing,
            AI reports, AI assistant, and API marketplace. Enable each module in its
            Settings after sign-in.
          </p>
          <div className="crm-app-grid crm-app-grid-landing">
            {LANDING_PLATFORM_APPS.map((app) => (
              <div
                key={app.id}
                className={`crm-app-tile crm-app-tile-static${app.comingSoon ? " crm-app-tile-coming-soon" : ""}`}
                style={{ "--app-accent": app.color }}
              >
                <AppIcon name={app.icon} color={app.color} />
                <span className="crm-app-tile-label">{app.label}</span>
                <span className="crm-app-tile-sub">{app.subtitle}</span>
                {app.comingSoon && (
                  <span className="crm-app-tile-badge">Soon</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="crm-landing-niches">
        <h2>Built for how Indian teams work</h2>
        <div className="crm-landing-niche-grid">
          {NICHES.map((niche) => (
            <span key={niche} className="crm-landing-niche">
              {niche}
            </span>
          ))}
        </div>
      </section>

      <section id="sign-in" className="crm-landing-signin">
        <h2>Choose your workspace</h2>
        <p className="crm-muted">
          Staff sign in by role. New company? Start with <strong>Admin</strong>.
          Demo? Try <strong>Sales</strong> or <strong>Accountant</strong>.
        </p>
        <div className="crm-app-grid crm-app-grid-portals">
          {LANDING_PORTALS.map((portal) => (
            <Link
              key={portal.path}
              to={portal.path}
              className="crm-app-tile crm-app-tile-portal"
              style={{ "--app-accent": portal.color }}
            >
              <AppIcon name={portal.icon} color={portal.color} />
              <span className="crm-app-tile-label">{portal.title}</span>
              <span className="crm-app-tile-sub">{portal.description}</span>
            </Link>
          ))}
        </div>
        <p className="crm-landing-user-link">
          External portal user?{" "}
          <Link to="/user-signup">Create account</Link>
          {" · "}
          <Link to="/user-login">Portal sign in</Link>
        </p>
      </section>

      <footer className="crm-landing-footer">
        <p>BlackPapers · Leads se payment tak, ek hi jagah</p>
      </footer>
    </div>
  );
}

export default Home;
