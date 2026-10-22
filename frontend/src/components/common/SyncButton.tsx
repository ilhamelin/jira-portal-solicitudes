import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage, jiraIssueUrl } from "../../services/api";

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
  const busy = useRef(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  async function sync() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    try {
      if (solicitudId) {
        const result = await api.syncSolicitud(solicitudId);
        toast.info(
          `Sincronización completada: ${result.hubo_cambios ? 1 : 0} tickets actualizados`,
          {
            action: {
              label: "Abrir en Jira ↗",
              onClick: () => {
                window.open(
                  jiraIssueUrl(result.jira_issue_key),
                  "_blank",
                  "noopener,noreferrer",
                );
              },
            },
          },
        );
      } else {
        const result = await api.syncAllJira();
        const failed = result.total_revisadas - result.detalles.length;
        if (failed > 0) {
          toast.warning(
            `Sincronización parcial: ${result.total_actualizadas} tickets actualizados`,
            {
              description: `${failed} no se pudieron consultar. Revisa la trazabilidad.`,
            },
          );
        } else {
          toast.info(
            `Sincronización completada: ${result.total_actualizadas} tickets actualizados`,
          );
        }
      }
      if (active.current) onSynced();
    } catch (error) {
      toast.error("No se pudo sincronizar con Jira", {
        description: errorMessage(error),
      });
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
    </>
  );
}
