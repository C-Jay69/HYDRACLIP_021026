import { AuthSessionProvider } from "@/auth-session";
import { AuthPage } from "@/components/AuthPage";
import { DashboardPage } from "@/components/DashboardPage";
import { LandingPage } from "@/components/landing/LandingPage";

import "./index.css";

export function App() {
  return (
    <AuthSessionProvider>
      {window.location.pathname === "/auth/callback" ? (
        <AuthPage callback />
      ) : window.location.pathname === "/auth" ? (
        <AuthPage />
      ) : window.location.pathname === "/dashboard" ? (
        <DashboardPage />
      ) : (
        <LandingPage />
      )}
    </AuthSessionProvider>
  );
}

export default App;
