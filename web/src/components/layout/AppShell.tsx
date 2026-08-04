import { Activity, BarChart3, Menu, Radar, ShieldCheck, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ResearchViewState } from "../../lib/contracts";
import type { AppRoute } from "../../lib/navigation";
import { SystemStatusBar } from "../status/SystemStatusBar";

interface Props {
  children: ReactNode;
  state: ResearchViewState;
  onRetry: () => void;
  route: AppRoute;
}

const navigation = [
  { route: "/" as const, href: "#/", label: "Command Center", icon: Activity },
  { route: "/scanner" as const, href: "#/scanner", label: "Live Scanner", icon: Radar },
];

export function AppShell({ children, state, onRetry, route }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className={`app-shell ${state.source === "preview" ? "app-shell--preview" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to research content</a>

      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`} aria-label="Primary navigation">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">T</div>
          <div>
            <strong>TRAIDR</strong>
            <span>Research intelligence</span>
          </div>
          <button className="sidebar__close" type="button" onClick={() => setMenuOpen(false)} aria-label="Close navigation">
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <nav className="nav-list">
          <p className="nav-label">Do now</p>
          {navigation.map(({ route: targetRoute, href, label, icon: Icon }) => (
            <a
              key={targetRoute}
              href={href}
              onClick={() => setMenuOpen(false)}
              className={`nav-item ${route === targetRoute ? "nav-item--active" : ""}`}
              aria-current={route === targetRoute ? "page" : undefined}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </a>
          ))}
        </nav>

        <div className="sidebar__roadmap" aria-label="Build progress">
          <p className="nav-label">Platform progress</p>
          <div className="progress-row"><span>Data + API</span><strong>Done</strong></div>
          <div className="progress-row"><span>Visual shell</span><strong>V2</strong></div>
          <div className="progress-track" aria-hidden="true"><span /></div>
          <p>Market workspace and research chat unlock in later verified phases.</p>
        </div>

        <div className="safety-card">
          <ShieldCheck size={18} aria-hidden="true" />
          <div><strong>Safety boundary active</strong><span>No order or wallet actions</span></div>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-backdrop" type="button" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <div className="app-shell__content">
        <div className="mobile-header">
          <button className="icon-button" type="button" onClick={() => setMenuOpen(true)} aria-label="Open navigation">
            <Menu size={20} aria-hidden="true" />
          </button>
          <span><BarChart3 size={17} aria-hidden="true" /> TRAIDR</span>
        </div>
        <SystemStatusBar state={state} onRetry={onRetry} />
        {state.source === "preview" && (
          <div className="preview-ribbon" role="status">
            PREVIEW DATA · NOT LIVE · NO DIRECTIONAL SIGNALS
          </div>
        )}
        <main id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
