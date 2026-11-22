"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  api,
  clearTokens,
  hasTokens,
  setTokens,
} from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!hasTokens()) {
      setUser(null);
      return null;
    }
    try {
      const profile = await api.profile();
      setUser(profile);
      return profile;
    } catch {
      clearTokens();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let active = true;

    (async () => {
      await loadUser();
      if (active) setLoading(false);
    })();

    const onUnauthorized = () => {
      clearTokens();
      setUser(null);
    };
    window.addEventListener("hydraclip:unauthorized", onUnauthorized);

    return () => {
      active = false;
      window.removeEventListener("hydraclip:unauthorized", onUnauthorized);
    };
  }, [loadUser]);

  const login = useCallback(
    async (email, password) => {
      const data = await api.login(email, password);
      setTokens(data.access_token, data.refresh_token);
      const profile = await loadUser();
      return profile || data.user;
    },
    [loadUser],
  );

  const register = useCallback(
    async (name, email, password) => {
      const data = await api.register(name, email, password);
      setTokens(data.access_token, data.refresh_token);
      const profile = await loadUser();
      return profile || data.user;
    },
    [loadUser],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // The access token may already be expired; clearing local state is enough.
    }
    clearTokens();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => loadUser(), [loadUser]);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refreshUser, setUser }),
    [user, loading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
