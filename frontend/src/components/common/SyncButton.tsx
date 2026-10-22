import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, X } from "lucide-react";
import { api, errorMessage } from "../../services/api";

export function SyncButton({
  solicitudId,
  onSynced,
  disabled = false,
  label = "Sincronizar con Jira",
}: {
  solicitudId?: string;
  onSynced: () => void;
  disabled?: boolean;
  label?: string;
}) {
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<{
    message: string;
    warning: boolean;
  } | null>(null);
  const busy = useRef(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 9000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function sync() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setNotice(null);
    try {
      if (solicitudId) {
        const result = await api.syncSolicitud(solicitudId);
        if (active.current)
          setNotice({
            message: `Sincronización completada: ${result.hubo_cambios ? 1 : 0} tickets actualizados`,
            warning: false,
          });
      } else {
        const result = await api.syncAllJira();
        const failed = result.total_revisadas - result.detalles.length;
        if (active.current)
          setNotice({
            message:
              failed > 0
                ? `Sincronización parcial: ${result.total_actualizadas} tickets actualizados; ${failed} no se pudieron consultar. Revisa la trazabilidad.`
                : `Sincronización completada: ${result.total_actualizadas} tickets actualizados`,
            warning: failed > 0,
          });
      }
      if (active.current) onSynced();
    } catch (error) {
      if (active.current)
        setNotice({ message: errorMessage(error), warning: true });
    } finally {
      busy.current = false;
      if (active.current) setPending(false);
    }
  }
  return (
    <>
      <button
        type="button"
        className="button button-secondary sync-button"
        onClick={sync}
        disabled={pending || disabled}
        aria-busy={pending}
      >
        <RefreshCw
          size={16}
          aria-hidden="true"
          className={pending ? "animate-spin" : ""}
        />
        {pending ? "Sincronizando…" : label}
      </button>
      {notice ? (
        <div
          className={`sync-toast ${notice.warning ? "sync-toast-warning" : ""}`}
          role={notice.warning ? "alert" : "status"}
        >
          {notice.warning ? (
            <AlertTriangle size={19} aria-hidden="true" />
          ) : (
            <CheckCircle2 size={19} aria-hidden="true" />
          )}
          <p>{notice.message}</p>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Cerrar notificación"
          >
            <X size={17} />
          </button>
        </div>
      ) : null}
    </>
  );
}
