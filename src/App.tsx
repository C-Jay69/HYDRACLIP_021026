import { AuthPage } from "@/components/AuthPage";
import { LandingPage } from "@/components/landing/LandingPage";

import "./index.css";

export function App() {
  if (window.location.pathname === "/auth/callback") {
    return <AuthPage callback />;
  }
  if (window.location.pathname === "/auth") {
    return <AuthPage />;
  }
  return <LandingPage />;
}

export default App;
