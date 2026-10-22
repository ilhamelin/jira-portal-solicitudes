import { Navigate, Outlet, useLocation } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import type { RolUsuario } from "../../types";

export function ProtectedRoute({
  roles = ["solicitante", "coordinador"],
}: {
  roles?: RolUsuario[];
}) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading)
    return (
      <div className="full-loader" role="status">
        <LoaderCircle className="animate-spin" aria-hidden="true" />
        Verificando tu sesión…
      </div>
    );
  if (!user)
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!roles.includes(user.rol)) return <Navigate to="/solicitudes" replace />;
  return <Outlet />;
}
