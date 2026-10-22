import {
  ArrowUpRight,
  ChartNoAxesCombined,
  Layers3,
  ListTodo,
  LogOut,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

import { ThemeToggle } from "./ThemeToggle";

export function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="site-header">
      <div className="nav-inner">
        <Link
          to="/solicitudes"
          className="brand"
          aria-label="Portal de Solicitudes, inicio"
        >
          <span className="brand-mark">
            <Layers3 size={23} aria-hidden="true" />
          </span>
          <span>
            Portal<span className="brand-subtitle">DE SOLICITUDES</span>
          </span>
        </Link>
        <nav aria-label="Navegación principal" className="primary-nav">
          <NavLink to="/solicitudes" end>
            <ListTodo size={17} aria-hidden="true" />
            Solicitudes
          </NavLink>
          {user?.rol === "coordinador" ? (
            <NavLink to="/dashboard">
              <ChartNoAxesCombined size={17} aria-hidden="true" />
              Dashboard
            </NavLink>
          ) : null}
        </nav>
        <div className="user-menu">
          <ThemeToggle />
          <span className="avatar" aria-hidden="true">
            {user?.nombre.trim().charAt(0).toUpperCase()}
          </span>
          <div className="user-info">
            <span>{user?.nombre}</span>
            <span className="role-label">
              {user?.rol === "coordinador" ? "Coordinador" : "Solicitante"}
            </span>
          </div>
          <button
            className="icon-button"
            onClick={logout}
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
      <div className="workspace-strip">
        <div>
          <span className="workspace-dot" />
          Espacio de trabajo interno
          <span className="workspace-provider">
            Integrado con Jira Cloud{" "}
            <ArrowUpRight size={13} aria-hidden="true" />
          </span>
        </div>
      </div>
    </header>
  );
}
