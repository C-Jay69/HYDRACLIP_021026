"use client";

import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/components/Toast";
import { AuthGate } from "@/components/AuthGate";

export function Providers({ children }) {
  return (
    <ToastProvider>
      <AuthProvider>
        <AuthGate>{children}</AuthGate>
      </AuthProvider>
    </ToastProvider>
  );
}
