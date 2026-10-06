import { AuthSessionProvider } from "@/auth-session";
import { AdminPage } from "@/components/AdminPage";
import { AuthPage } from "@/components/AuthPage";
import { BillingPage } from "@/components/BillingPage";
import { ConnectPage } from "@/components/ConnectPage";
import { DashboardPage } from "@/components/DashboardPage";
import { LandingPage } from "@/components/landing/LandingPage";
import { OnboardingPage } from "@/components/OnboardingPage";
import { ProfilePage } from "@/components/ProfilePage";
import { ProjectsPage } from "@/components/ProjectsPage";
import { SchedulePage } from "@/components/SchedulePage";

import "./index.css";

/**
 * Tiny URL → component router.
 *
 * The Bun dev server (src/index.ts) is configured to serve index.html for every
 * page route below, so reading `window.location.pathname` is enough on first
 * paint. Subsequent in-app navigations are full page loads via <a href>, which
 * is fine for an MVP — there is no client-side history to keep in sync.
 *
 * Routes match the build prompt's "FRONTEND PAGES" section: public marketing
 * pages, auth pages, the authenticated app surface (/dashboard, /projects,
 * /schedule, /connect, /billing, /profile, /onboarding) and /admin/*.
 */
function route(pathname: string) {
  if (pathname === "/auth/callback") return <AuthPage callback />;
  if (pathname === "/auth") return <AuthPage />;
  if (pathname === "/dashboard") return <DashboardPage />;
  if (pathname === "/projects") return <ProjectsPage />;
  if (pathname === "/schedule") return <SchedulePage />;
  if (pathname === "/connect") return <ConnectPage />;
  if (pathname === "/billing") return <BillingPage />;
  if (pathname === "/profile") return <ProfilePage />;
  if (pathname === "/onboarding") return <OnboardingPage />;
  if (pathname === "/admin") return <AdminPage />;
  return <LandingPage />;
}

export function App() {
  return <AuthSessionProvider>{route(window.location.pathname)}</AuthSessionProvider>;
}

export default App;
