import { useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Layers3,
  LoaderCircle,
  ShieldCheck,
  UserRound,
  UsersRound,
} from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../services/api";

export function LoginPage() {
  const { user, isLoading, sessionError, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const passwordInput = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const target: unknown = location.state?.from;
  const destination =
    typeof target === "string" &&
    (target.startsWith("/solicitudes") || target === "/dashboard")
      ? target
      : "/solicitudes";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError("");
    try {
      await login(email.trim(), password);
      navigate(destination, { replace: true });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  function fillDemo(role: "solicitante" | "coordinador") {
    setEmail(`${role}@empresa.com`);
    setPassword(role === "solicitante" ? "Solicitante123!" : "Coordinador123!");
    setError("");
    passwordInput.current?.focus();
  }

  if (isLoading)
    return (
      <div className="full-loader" role="status">
        <LoaderCircle className="animate-spin" aria-hidden="true" />
        Verificando tu sesión…
      </div>
    );
  if (user) return <Navigate to={destination} replace />;

  return (
    <main className="login-layout">
      <section className="login-story" aria-labelledby="welcome-title">
        <div className="brand brand-light">
          <span className="brand-mark">
            <Layers3 size={25} aria-hidden="true" />
          </span>
          <span>
            Portal<span className="brand-subtitle">DE SOLICITUDES</span>
          </span>
        </div>
        <div className="login-story-content">
          <span className="story-kicker">
            <span />
            CONECTAMOS EQUIPOS Y SOLUCIONES
          </span>
          <h1 id="welcome-title">
            Las buenas soluciones
            <br /> empiezan con
            <br /> <em>una solicitud.</em>
          </h1>
          <p>
            Reporta un incidente, propone una mejora y sigue cada avance. Tu
            equipo y Jira, en el mismo flujo.
          </p>
          <div
            className="story-workflow"
            aria-label="Registra, conecta y sigue"
          >
            <span>
              <span>01</span>Registra
            </span>
            <ArrowRight size={17} aria-hidden="true" />
            <span>
              <span>02</span>Conecta
            </span>
            <ArrowRight size={17} aria-hidden="true" />
            <span>
              <span>03</span>Sigue
            </span>
          </div>
        </div>
        <div className="story-footer">
          <ShieldCheck size={17} aria-hidden="true" />
          Acceso interno · Seguimiento con Jira Cloud
        </div>
      </section>
      <section className="login-form-section" aria-labelledby="login-title">
        <div className="login-form-wrap">
          <p className="eyebrow">BIENVENIDO A TU ESPACIO DE TRABAJO</p>
          <h2 id="login-title">Inicia sesión</h2>
          <p className="page-description">
            Ingresa con tu cuenta para continuar.
          </p>
          {error || sessionError ? (
            <div className="notice notice-error" role="alert">
              {error || sessionError}
            </div>
          ) : null}
          <form onSubmit={submit} className="login-form" aria-busy={pending}>
            <div className="field">
              <label htmlFor="email">Correo electrónico</label>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="username"
                placeholder="nombre@empresa.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={pending}
              />
            </div>
            <div className="field">
              <label htmlFor="password">Contraseña</label>
              <div className="password-field">
                <input
                  id="password"
                  ref={passwordInput}
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  placeholder="Tu contraseña"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={pending}
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={
                    showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
                  }
                  aria-pressed={showPassword}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button
              className="button button-primary login-submit"
              disabled={pending}
            >
              {pending ? (
                <>
                  <LoaderCircle
                    size={18}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                  Ingresando…
                </>
              ) : (
                <>
                  Ingresar al portal
                  <ArrowRight size={18} aria-hidden="true" />
                </>
              )}
            </button>
          </form>
          <div className="demo-divider">
            <span>¿Estás explorando la demo?</span>
          </div>
          <p className="helper-text mb-4">
            Selecciona una cuenta para completar el formulario.
          </p>
          <div className="demo-buttons">
            <button
              type="button"
              onClick={() => fillDemo("solicitante")}
              disabled={pending}
            >
              <UserRound size={19} aria-hidden="true" />
              <span>
                Ingresar como Solicitante Demo
                <small>Crea y consulta tus solicitudes</small>
              </span>
              <ArrowRight size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => fillDemo("coordinador")}
              disabled={pending}
            >
              <UsersRound size={19} aria-hidden="true" />
              <span>
                Ingresar como Coordinador Demo
                <small>Consulta las solicitudes del equipo</small>
              </span>
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
          <p className="login-note">
            <Check size={14} aria-hidden="true" />
            Cada perfil tiene acceso según su rol.
          </p>
        </div>
      </section>
    </main>
  );
}
