import { useEffect } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { Navbar } from "./components/common/Navbar";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { SolicitudesPage } from "./pages/SolicitudesPage";
import { NuevaSolicitudPage } from "./pages/NuevaSolicitudPage";
import { DetalleSolicitudPage } from "./pages/DetalleSolicitudPage";
import { DashboardPage } from "./pages/DashboardPage";

function Workspace() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <>
      <a href="#main-content" className="skip-link">
        Ir al contenido
      </a>
      <Navbar />
      <main id="main-content" className="workspace-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <span>Portal de Solicitudes Internas</span>
        <span>Un lugar para reportar. Un flujo para avanzar.</span>
      </footer>
    </>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Workspace />}>
              <Route element={<ProtectedRoute roles={["coordinador"]} />}>
                <Route path="/dashboard" element={<DashboardPage />} />
              </Route>
              <Route path="/solicitudes" element={<SolicitudesPage />} />
              <Route
                path="/solicitudes/nueva"
                element={<NuevaSolicitudPage />}
              />
              <Route
                path="/solicitudes/:id"
                element={<DetalleSolicitudPage />}
              />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/solicitudes" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
