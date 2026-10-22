import { SkeletonTable } from "../components/common/SkeletonTable";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDown,
  Inbox,
  ListFilter,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../services/api";
import { SolicitudCard } from "../components/solicitudes/SolicitudCard";
import { SyncButton } from "../components/common/SyncButton";
import type { EstadoNegocio, Solicitud, TipoSolicitud } from "../types";

const STATES: EstadoNegocio[] = [
  "Recibido",
  "En análisis",
  "En desarrollo",
  "En pruebas",
  "Cerrado",
  "Rechazado",
];
const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

export function SolicitudesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Solicitud[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [type, setType] = useState<TipoSolicitud | "">("");
  const [state, setState] = useState<EstadoNegocio | "">("");
  const [revision, setRevision] = useState(0);
  const moreController = useRef<AbortController | null>(null);
  const moreBusy = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setItems([]);
    api
      .solicitudes(0, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setItems(data);
          setHasMore(data.length === 50);
        }
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      moreController.current?.abort();
    };
  }, [revision]);

  async function loadMore() {
    if (moreBusy.current) return;
    moreBusy.current = true;
    setLoadingMore(true);
    setError("");
    const controller = new AbortController();
    moreController.current = controller;
    try {
      const next = await api.solicitudes(items.length, controller.signal);
      if (!controller.signal.aborted) {
        setItems((current) => {
          const existing = new Set(current.map((item) => item.id));
          return [...current, ...next.filter((item) => !existing.has(item.id))];
        });
        setHasMore(next.length === 50);
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure));
    } finally {
      moreBusy.current = false;
      setLoadingMore(false);
    }
  }

  const visible = useMemo(() => {
    const query = normalize(search.trim());
    return items.filter(
      (item) =>
        (!type || item.tipo === type) &&
        (!state || item.estado_negocio === state) &&
        (!query ||
          normalize(
            `${item.titulo} ${item.area} ${item.jira_integracion?.jira_issue_key ?? ""}`,
          ).includes(query)),
    );
  }, [items, search, type, state]);
  const filtered = Boolean(search || type || state);

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CENTRO DE SOLICITUDES</p>
          <h1>
            {user?.rol === "coordinador"
              ? "Solicitudes del equipo"
              : "Mis solicitudes"}
          </h1>
          <p className="page-description">
            {user?.rol === "coordinador"
              ? "Una vista compartida de los incidentes y mejoras de tu equipo."
              : "Todo lo que reportaste y el estado de cada avance, en un solo lugar."}
          </p>
        </div>
        <Link to="/solicitudes/nueva" className="button button-primary">
          <Plus size={18} aria-hidden="true" />
          Nueva Solicitud
        </Link>
      </div>
      <section
        className="panel requests-panel"
        aria-label="Listado de solicitudes"
      >
        <div className="list-toolbar">
          <div className="type-tabs" role="group" aria-label="Filtrar por tipo">
            {(
              [
                ["", "Todas"],
                ["incidente", "Incidentes"],
                ["mejora", "Mejoras"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={type === value}
                className={type === value ? "selected" : ""}
                onClick={() => setType(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="list-toolbar-actions">
            {user?.rol === "coordinador" ? (
              <SyncButton
                onSynced={() => setRevision((value) => value + 1)}
                disabled={isLoading || loadingMore}
              />
            ) : null}
            <button
              type="button"
              className="button button-quiet"
              onClick={() => setRevision((value) => value + 1)}
              disabled={isLoading || loadingMore}
            >
              <RefreshCw
                size={15}
                aria-hidden="true"
                className={isLoading ? "animate-spin" : ""}
              />
              Actualizar
            </button>
          </div>
        </div>
        <div className="filters">
          <div className="search-field">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              aria-label="Buscar entre las solicitudes cargadas"
              placeholder="Buscar por título, área o clave Jira…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="state-filter">
            <ListFilter size={16} aria-hidden="true" />
            <label htmlFor="filter-state" className="sr-only">
              Estado de negocio
            </label>
            <select
              id="filter-state"
              value={state}
              onChange={(event) =>
                setState(event.target.value as EstadoNegocio | "")
              }
            >
              <option value="">Todos los estados</option>
              {STATES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>
        {error ? (
          <div className="notice notice-error list-notice" role="alert">
            <AlertCircle size={19} aria-hidden="true" />
            <div>
              {error}
              <button
                className="text-button block"
                onClick={() => setRevision((value) => value + 1)}
              >
                Volver a cargar
              </button>
            </div>
          </div>
        ) : null}
        {isLoading ? (
          <SkeletonTable />
        ) : items.length === 0 && !error ? (
          <div className="empty-state">
            <span className="empty-icon">
              <Inbox size={29} aria-hidden="true" />
            </span>
            <h2>Tu próxima solución empieza aquí</h2>
            <p>
              Aún no hay solicitudes para mostrar. Registra un incidente o
              propone una mejora.
            </p>
            <Link className="button button-primary" to="/solicitudes/nueva">
              <Plus size={17} aria-hidden="true" />
              Crear una solicitud
            </Link>
          </div>
        ) : (
          <>
            <div className="list-meta" role="status" aria-live="polite">
              <span>
                {visible.length}{" "}
                {visible.length === 1 ? "solicitud" : "solicitudes"}
                {filtered ? " coincidentes" : " cargadas"}
              </span>
              {filtered ? (
                <button
                  className="text-button"
                  onClick={() => {
                    setSearch("");
                    setType("");
                    setState("");
                  }}
                >
                  <X size={13} aria-hidden="true" />
                  Limpiar filtros
                </button>
              ) : (
                <span>Más recientes primero</span>
              )}
            </div>
            {visible.length ? (
              <>
                <div className="table-head" aria-hidden="true">
                  <span>Solicitud</span>
                  <span>Tipo</span>
                  <span>Área</span>
                  <span>Prioridad</span>
                  <span>Estado</span>
                  <span>Jira Cloud</span>
                  <span />
                </div>
                <ul className="request-list">
                  {visible.map((item) => (
                    <li key={item.id}>
                      <SolicitudCard solicitud={item} />
                    </li>
                  ))}
                </ul>
              </>
            ) : !error ? (
              <div className="empty-state">
                <Search size={27} aria-hidden="true" />
                <h2>No encontramos coincidencias</h2>
                <p>Prueba con otro título, estado o tipo de solicitud.</p>
              </div>
            ) : null}
            {hasMore ? (
              <div className="load-more">
                <p className="helper-text">
                  Los filtros se aplican a las solicitudes cargadas.
                </p>
                <button
                  className="button button-secondary"
                  onClick={loadMore}
                  disabled={loadingMore || isLoading}
                >
                  {loadingMore ? (
                    <LoaderCircle
                      size={16}
                      className="animate-spin"
                      aria-hidden="true"
                    />
                  ) : (
                    <ArrowDown size={16} aria-hidden="true" />
                  )}
                  {loadingMore ? "Cargando…" : "Cargar más solicitudes"}
                </button>
              </div>
            ) : null}
          </>
        )}
      </section>
      <p className="page-footnote">
        <span className="workspace-dot" />
        Los estados de negocio y de integración se muestran por separado.
      </p>
    </>
  );
}
