import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  LoaderCircle,
  MessageSquare,
  RefreshCw,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import { ApiError, api, errorMessage } from "../../services/api";
import type { Comentario } from "../../types";

function chronological(items: Comentario[]) {
  return [...items].sort(
    (left, right) =>
      Date.parse(left.created_at) - Date.parse(right.created_at) ||
      left.id.localeCompare(right.id),
  );
}

export function ComentariosSection({
  solicitudId,
  revision = 0,
  hasJiraTicket,
}: {
  solicitudId: string;
  revision?: number;
  hasJiraTicket: boolean;
}) {
  const titleId = useId();
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  const [items, setItems] = useState<Comentario[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [syncFailed, setSyncFailed] = useState(false);
  const [content, setContent] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [retry, setRetry] = useState(0);
  const busy = useRef(false);
  const active = useRef(true);
  const generation = useRef(0);
  const fetchController = useRef<AbortController | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetchController.current = controller;
    const current = ++generation.current;
    setLoading(true);
    setError("");
    api
      .getComentarios(solicitudId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted && current === generation.current) {
          setItems(chronological(result.items));
          setSyncFailed(result.syncFailed);
        }
      })
      .catch((failure) => {
        if (!controller.signal.aborted && current === generation.current)
          setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted && current === generation.current)
          setLoading(false);
      });
    return () => controller.abort();
  }, [solicitudId, revision, retry]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const text = content.trim();
    if (text.length < 2 || text.length > 2000) {
      setFieldError("Escribe un comentario de entre 2 y 2000 caracteres.");
      input.current?.focus();
      return;
    }
    busy.current = true;
    setPending(true);
    setFieldError("");
    try {
      const created = await api.crearComentario(solicitudId, {
        contenido: text,
      });
      if (!active.current) return;
      // Una consulta iniciada antes de confirmar el POST no debe borrar el comentario nuevo.
      fetchController.current?.abort();
      ++generation.current;
      setLoading(false);
      setItems((current) =>
        chronological([
          ...current.filter((item) => item.id !== created.id),
          created,
        ]),
      );
      setContent("");
      setError("");
      if (created.jira_comment_id)
        toast.success("Comentario publicado en el portal y en Jira");
      else
        toast.warning("Guardado solo en el portal", {
          description: hasJiraTicket
            ? "El envío a Jira no está confirmado. Actualiza los comentarios antes de volver a publicarlo."
            : "La solicitud todavía no tiene un ticket Jira vinculado.",
        });
    } catch (failure) {
      if (!active.current) return;
      setFieldError(
        failure instanceof ApiError &&
          (failure.status === 0 || failure.status >= 500)
          ? "No pudimos confirmar el resultado. Actualiza los comentarios antes de volver a enviarlo."
          : errorMessage(failure),
      );
    } finally {
      busy.current = false;
      if (active.current) setPending(false);
    }
  }

  return (
    <section className="panel comments-panel" aria-labelledby={titleId}>
      <div className="comments-heading">
        <div>
          <p className="eyebrow">CONVERSACIÓN DEL EQUIPO</p>
          <h2 id={titleId}>
            <MessageSquare size={19} aria-hidden="true" />
            Comentarios
          </h2>
        </div>
        <button
          type="button"
          className="button button-quiet"
          disabled={loading || pending}
          onClick={() => setRetry((value) => value + 1)}
        >
          <RefreshCw
            size={15}
            className={loading ? "animate-spin" : ""}
            aria-hidden="true"
          />
          Actualizar comentarios
        </button>
      </div>
      <p className="helper-text">
        Comparte información y consulta las respuestas del equipo técnico.
      </p>
      {syncFailed ? (
        <div className="notice notice-warning" role="status">
          <AlertTriangle size={18} aria-hidden="true" />
          <p>
            No pudimos actualizar desde Jira. Mostramos los comentarios
            guardados en el portal.
          </p>
        </div>
      ) : null}
      {error ? (
        <div className="notice notice-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="text-button"
            disabled={loading || pending}
            onClick={() => setRetry((value) => value + 1)}
          >
            Reintentar comentarios
          </button>
        </div>
      ) : null}
      {loading && !items.length ? (
        <div
          className="comments-skeleton"
          role="status"
          aria-label="Cargando comentarios"
        >
          <span className="sr-only">Cargando comentarios…</span>
          {[0, 1, 2].map((index) => (
            <div
              className="skeleton-block animate-pulse bg-slate-200 dark:bg-slate-800"
              key={index}
              aria-hidden="true"
            />
          ))}
        </div>
      ) : items.length ? (
        <ol
          className="comments-timeline"
          aria-label="Historial de comentarios"
          aria-busy={loading}
        >
          {items.map((item) => (
            <li key={item.id}>
              <span
                className={`comment-avatar ${item.origen === "jira" ? "comment-avatar-jira" : ""}`}
                aria-hidden="true"
              >
                {item.autor_nombre.trim().charAt(0).toUpperCase()}
              </span>
              <article className="comment-body">
                <header>
                  <strong>{item.autor_nombre}</strong>
                  <span
                    className={`badge ${item.origen === "jira" ? "badge-blue" : "badge-green"}`}
                  >
                    {item.origen === "jira" ? "Jira" : "Portal"}
                  </span>
                  <time dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString("es-CL", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </time>
                </header>
                <p className="comment-content">
                  {item.contenido || "[Comentario sin texto]"}
                </p>
                {item.origen === "portal" && !item.jira_comment_id ? (
                  <small className="comment-local-status">
                    Guardado solo en el portal
                  </small>
                ) : null}
              </article>
            </li>
          ))}
        </ol>
      ) : !error ? (
        <p className="comments-empty">
          Aún no hay comentarios. Puedes iniciar la conversación.
        </p>
      ) : null}
      <form className="comment-form" onSubmit={submit}>
        <label htmlFor={inputId}>Escribe un comentario</label>
        <textarea
          ref={input}
          id={inputId}
          name="comentario"
          rows={3}
          minLength={2}
          maxLength={2000}
          required
          disabled={pending}
          value={content}
          onChange={(event) => {
            setContent(event.target.value);
            setFieldError("");
          }}
          aria-invalid={Boolean(fieldError)}
          aria-describedby={`${hintId}${fieldError ? ` ${errorId}` : ""}`}
          placeholder="Añade contexto, responde una pregunta o comparte un avance…"
        />
        <div className="comment-form-footer">
          <p className="helper-text" id={hintId}>
            {content.length}/2000 caracteres
            {!hasJiraTicket ? " · Se guardará solo en el portal" : ""}
          </p>
          <button
            type="submit"
            className="button button-primary"
            disabled={pending || loading || content.trim().length < 2}
            aria-busy={pending}
          >
            {pending ? (
              <LoaderCircle
                size={16}
                className="animate-spin"
                aria-hidden="true"
              />
            ) : (
              <Send size={16} aria-hidden="true" />
            )}
            {pending ? "Enviando…" : "Enviar comentario"}
          </button>
        </div>
        {fieldError ? (
          <p className="field-error" id={errorId} role="alert">
            {fieldError}
          </p>
        ) : null}
      </form>
    </section>
  );
}
