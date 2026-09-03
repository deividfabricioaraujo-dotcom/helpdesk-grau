import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import { api, formatApiError } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // null = checking, false = anon, object = admin
  const [ready, setReady] = useState(false);

  const check = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const login = useCallback(async (username, password) => {
    try {
      const { data } = await api.post("/auth/login", { username, password });
      setUser(data.user);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: formatApiError(e.response?.data?.detail) };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore network error on logout */
    }
    setUser(false);
  }, []);

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
