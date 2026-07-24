import { AppHeader } from "./components/AppHeader";
import { ToastProvider } from "./components/ToastProvider";
import { AppRoutes } from "./routes/AppRoutes";

export function App() {
  return (
    <ToastProvider>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="app-shell">
        <AppHeader />
        <main id="main-content" className="app-main" tabIndex={-1}>
          <AppRoutes />
        </main>
      </div>
    </ToastProvider>
  );
}
