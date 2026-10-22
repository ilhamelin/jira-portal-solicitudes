import { useEffect, useRef, useState } from "react";
import {
  Download,
  FileImage,
  FileText,
  LoaderCircle,
  Paperclip,
} from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "../../services/api";
import type { Adjunto } from "../../types";
import { formatFileSize, saveFile } from "./FileUploadZone";

export function AdjuntosList({
  solicitudId,
  revision = 0,
}: {
  solicitudId: string;
  revision?: number;
}) {
  const [items, setItems] = useState<Adjunto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [downloading, setDownloading] = useState<string | null>(null);
  const busy = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setItems([]);
    api
      .getAdjuntos(solicitudId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setItems(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [solicitudId, revision, retry]);
  async function download(item: Adjunto) {
    if (busy.current) return;
    busy.current = true;
    setDownloading(item.id);
    try {
      saveFile(
        await api.downloadAdjunto(solicitudId, item.id),
        item.nombre_archivo,
      );
    } catch (failure) {
      toast.error("No se pudo descargar el adjunto", {
        description: errorMessage(failure),
      });
    } finally {
      busy.current = false;
      setDownloading(null);
    }
  }
  return (
    <section
      className="panel attachments-panel"
      aria-labelledby="attachments-title"
      aria-busy={loading}
    >
      <h2 id="attachments-title">
        <Paperclip size={18} aria-hidden="true" />
        Archivos adjuntos
      </h2>
      {loading ? (
        <p className="helper-text" role="status">
          Cargando adjuntos…
        </p>
      ) : error ? (
        <div className="notice notice-error" role="alert">
          <p>{error}</p>
          <button
            className="text-button"
            type="button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Reintentar
          </button>
        </div>
      ) : items.length ? (
        <ul className="attachment-list">
          {items.map((item) => (
            <li key={item.id}>
              {item.mime_type.startsWith("image/") ? (
                <FileImage size={24} aria-hidden="true" />
              ) : (
                <FileText size={24} aria-hidden="true" />
              )}
              <div className="attachment-info">
                <strong>{item.nombre_archivo}</strong>
                <small>
                  {formatFileSize(item.tamanio_bytes)} ·{" "}
                  {item.mime_type === "application/pdf"
                    ? "PDF"
                    : item.mime_type === "text/plain"
                      ? "TXT"
                      : "Imagen"}
                </small>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label={`Descargar ${item.nombre_archivo}`}
                disabled={downloading !== null}
                onClick={() => void download(item)}
              >
                {downloading === item.id ? (
                  <LoaderCircle
                    size={18}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Download size={18} aria-hidden="true" />
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="helper-text">
          Esta solicitud no tiene archivos adjuntos enviados desde el portal.
        </p>
      )}
    </section>
  );
}
