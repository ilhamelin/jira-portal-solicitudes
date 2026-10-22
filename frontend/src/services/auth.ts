export const SESSION_KEY = "portal.session.v1";
export const SESSION_CHANGED = "portal:session-changed";

export function getToken(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string): void {
  try {
    localStorage.setItem(SESSION_KEY, token);
  } catch {
    throw new Error(
      "Habilita el almacenamiento del navegador para iniciar sesión.",
    );
  }
}

export function clearToken(expected?: string): void {
  if (expected !== undefined && getToken() !== expected) return;
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* La sesión en memoria también se elimina. */
  }
  window.dispatchEvent(new Event(SESSION_CHANGED));
}

export function tokenExpiry(token: string): number | null {
  try {
    const payload: unknown = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    if (
      typeof payload === "object" &&
      payload !== null &&
      "exp" in payload &&
      typeof payload.exp === "number"
    ) {
      return payload.exp * 1000;
    }
  } catch {
    /* El servidor valida la firma; aquí solo se gestiona la expiración visual. */
  }
  return null;
}
