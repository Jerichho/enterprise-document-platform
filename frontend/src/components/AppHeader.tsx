import { NavLink } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export function AppHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="brand-row">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <p className="brand-eyebrow">Enterprise Knowledge Platform</p>
            <h1>Internal Document Intelligence</h1>
          </div>
        </div>
        {user && (
          <div className="user-chip">
            <span>
              {user.full_name} · {user.role}
            </span>
            <button type="button" className="btn ghost" onClick={logout}>
              Sign out
            </button>
          </div>
        )}
      </div>
      {user && (
        <nav className="app-nav" aria-label="Primary">
          <NavLink to="/documents">Documents</NavLink>
          <NavLink to="/assistant">Assistant</NavLink>
          {user.role === "admin" && <NavLink to="/admin">Admin</NavLink>}
          <NavLink to="/status">Status</NavLink>
        </nav>
      )}
    </header>
  );
}
