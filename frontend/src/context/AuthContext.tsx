import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, errorMessage } from "../services/api";
import {
  clearToken,
  getToken,
  saveToken,
  SESSION_CHANGED,
  SESSION_KEY,
  tokenExpiry,
} from "../services/auth";
import type { Usuario } from "../types";

interface AuthState {
  user: Usuario | null;
  isLoading: boolean;
  sessionError: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}
const AuthContext = createContext<AuthState | undefined>(undefined);

function validateUser(user: Usuario): Usuario {
  if (!["solicitante", "coordinador"].includes(user.rol))
    throw new Error("Tu cuenta no tiene un rol habilitado para este portal.");
  return user;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const changed = () => {
      generation.current += 1;
      setUser(null);
      setIsLoading(Boolean(getToken()));
      setRevision((value) => value + 1);
    };
    const storage = (event: StorageEvent) => {
      if (event.key === SESSION_KEY || event.key === null) changed();
    };
    window.addEventListener(SESSION_CHANGED, changed);
    window.addEventListener("storage", storage);
    return () => {
      window.removeEventListener(SESSION_CHANGED, changed);
      window.removeEventListener("storage", storage);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const version = ++generation.current;
    const token = getToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    const expiry = tokenExpiry(token);
    if (expiry !== null && expiry <= Date.now()) {
      clearToken(token);
      setSessionError("Tu sesión terminó. Vuelve a ingresar.");
      return;
    }
    setIsLoading(true);
    api
      .me(controller.signal)
      .then((result) => {
        if (generation.current === version) {
          setUser(validateUser(result));
          setSessionError("");
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted && generation.current === version) {
          clearToken(token);
          setUser(null);
          setSessionError(errorMessage(error));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted && generation.current === version)
          setIsLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    const token = getToken();
    const expiry = token ? tokenExpiry(token) : null;
    if (!user || !token || expiry === null) return;
    const timer = window.setTimeout(
      () => {
        clearToken(token);
        setSessionError("Tu sesión terminó. Vuelve a ingresar.");
      },
      Math.max(0, Math.min(expiry - Date.now(), 2_147_483_647)),
    );
    return () => window.clearTimeout(timer);
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    const version = ++generation.current;
    const response = await api.login(email, password);
    if (version !== generation.current)
      throw new Error("La sesión cambió. Vuelve a ingresar.");
    saveToken(response.access_token);
    try {
      const current = validateUser(await api.me());
      if (version !== generation.current)
        throw new Error("La sesión cambió. Vuelve a ingresar.");
      setUser(current);
      setSessionError("");
      setIsLoading(false);
    } catch (error) {
      clearToken(response.access_token);
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setSessionError("");
  }, []);
  const value = useMemo(
    () => ({ user, isLoading, sessionError, login, logout }),
    [user, isLoading, sessionError, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider.");
  return context;
}
