import {
  FileUploadZone,
  saveFile,
} from "../components/solicitudes/FileUploadZone";
import { toast } from "sonner";
import { useRef, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bug,
  Check,
  CheckCircle2,
  FileText,
  LoaderCircle,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError, api, errorMessage, jiraIssueUrl } from "../services/api";
import type {
  PrioridadTipo,
  Solicitud,
  SolicitudCreateInput,
  TipoSolicitud,
} from "../types";

const AREAS = [
  "Finanzas",
  "Operaciones",
  "Ventas",
  "TI",
  "Recursos Humanos",
  "Logística",
];
const INITIAL: SolicitudCreateInput = {
  titulo: "",
  descripcion: "",
  tipo: "incidente",
  area: "",
  prioridad_solicitada: "media",
};

export function NuevaSolicitudPage() {
  const [form, setForm] = useState<SolicitudCreateInput>(INITIAL);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadFailures, setUploadFailures] = useState<
    { file: File; error: string }[]
  >([]);
  const [uploadProgress, setUploadProgress] = useState("");
  const [result, setResult] = useState<Solicitud | null>(null);
  const busy = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);

  function update<K extends keyof SolicitudCreateInput>(
    field: K,
    value: SolicitudCreateInput[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const input = {
      ...form,
      titulo: form.titulo.trim(),
      descripcion: form.descripcion.trim(),
    };
    const validation: Record<string, string> = {};
    if (input.titulo.length < 5 || input.titulo.length > 200)
      validation.titulo = "Escribe un título de entre 5 y 200 caracteres.";
    if (input.descripcion.length < 10)
      validation.descripcion =
        "La descripción debe tener al menos 10 caracteres.";
    if (!AREAS.includes(input.area))
      validation.area = "Selecciona el área relacionada con tu solicitud.";
    setErrors(validation);
    setError("");
    if (Object.keys(validation).length) {
      const first = Object.keys(validation)[0];
      formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
      return;
    }
    busy.current = true;
    setPending(true);
    try {
      const created = await api.crear(input);
      const key = created.jira_integracion?.jira_issue_key;
      if (
        key &&
        created.jira_integracion?.estado_integracion === "sincronizado"
      ) {
        toast.success(`Ticket ${key} creado en Jira`, {
          description: created.titulo,
          action: {
            label: "Abrir en Jira ↗",
            onClick: () => {
              window.open(jiraIssueUrl(key), "_blank", "noopener,noreferrer");
            },
          },
        });
      } else {
        toast.warning("Solicitud guardada; el envío a Jira no se completó", {
          description: "Revisa el detalle antes de volver a enviarla.",
        });
      }
      const failures: { file: File; error: string }[] = [];
      for (const [index, file] of files.entries()) {
        setUploadProgress(
          `Enviando archivo ${index + 1} de ${files.length}: ${file.name}`,
        );
        if (
          !key ||
          created.jira_integracion?.estado_integracion !== "sincronizado"
        ) {
          failures.push({
            file,
            error: "No se envió porque el ticket de Jira no se pudo crear.",
          });
          continue;
        }
        try {
          await api.uploadAdjunto(created.id, file);
        } catch (failure) {
          failures.push({ file, error: errorMessage(failure) });
        }
      }
      setUploadFailures(failures);
      if (failures.length)
        toast.warning(
          `${failures.length} archivos no tienen subida confirmada`,
          {
            description:
              "La solicitud está guardada. Revisa Jira antes de reenviar archivos.",
          },
        );
      else if (files.length)
        toast.success(`${files.length} archivos adjuntos enviados a Jira`);
      setResult(created);
    } catch (failure) {
      setError(
        failure instanceof ApiError &&
          (failure.status === 0 || failure.status >= 500)
          ? "No pudimos confirmar el resultado del registro. Revisa tu listado de solicitudes antes de volver a enviarlo."
          : errorMessage(failure),
      );
      if (failure instanceof ApiError) setErrors(failure.fields);
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  if (result) {
    const key = result.jira_integracion?.jira_issue_key;
    const synced =
      result.jira_integracion?.estado_integracion === "sincronizado";
    return (
      <section className="panel success-panel" aria-labelledby="created-title">
        <span className={`success-icon ${synced ? "" : "success-pending"}`}>
          {synced ? (
            <CheckCircle2 size={36} aria-hidden="true" />
          ) : (
            <AlertTriangle size={36} aria-hidden="true" />
          )}
        </span>
        <p className="eyebrow">SOLICITUD GUARDADA</p>
        <h1 id="created-title">Tu solicitud ya está registrada</h1>
        <p>
          {synced && key ? (
            <>
              También creamos el ticket <strong>{key}</strong> en Jira Cloud.
              Puedes seguir su avance en el detalle.
            </>
          ) : (
            "El registro está guardado en el portal, pero el envío a Jira no se completó. No necesitas crear otra solicitud; el equipo podrá revisar el intento."
          )}
        </p>
        <h2>{result.titulo}</h2>
        {uploadFailures.length ? (
          <div
            className="notice notice-warning attachment-failures"
            role="alert"
          >
            <div>
              <strong>
                La solicitud está guardada. Estos archivos no tienen subida
                confirmada:
              </strong>
              <ul>
                {uploadFailures.map(({ file, error }, index) => (
                  <li key={index}>
                    <strong>{file.name}</strong>
                    <p>{error}</p>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => saveFile(file, file.name)}
                    >
                      Conservar archivo local
                    </button>
                  </li>
                ))}
              </ul>
              <p>
                Revisa el ticket en Jira antes de reenviarlos para evitar
                duplicados.
              </p>
            </div>
          </div>
        ) : null}
        <div className="success-actions">
          <Link
            className="button button-primary"
            to={`/solicitudes/${result.id}`}
          >
            Ver detalle
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
          {key ? (
            <a
              className="button button-secondary"
              href={jiraIssueUrl(key)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Abrir {key} en Jira
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          ) : null}
        </div>
        <Link className="text-button" to="/solicitudes">
          Volver a solicitudes
        </Link>
      </section>
    );
  }

  return (
    <>
      <Link to="/solicitudes" className="back-link">
        <ArrowLeft size={16} aria-hidden="true" />
        Volver a solicitudes
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">HAGAMOS QUE LAS COSAS AVANCEN</p>
          <h1>Nueva solicitud</h1>
          <p className="page-description">
            Cuéntanos qué sucede o qué te gustaría mejorar.
          </p>
        </div>
        <span className="step-label">REGISTRO DE SOLICITUD</span>
      </div>
      <div className="form-layout">
        <section className="panel form-panel" aria-labelledby="form-title">
          <div className="section-heading">
            <h2 id="form-title">
              <FileText size={19} aria-hidden="true" />
              Información de la solicitud
            </h2>
            <span className="helper-text">
              Los archivos adjuntos son opcionales
            </span>
          </div>
          <form ref={formRef} onSubmit={submit} noValidate aria-busy={pending}>
            {error ? (
              <div className="notice notice-error" role="alert">
                {error}
                <Link to="/solicitudes" className="text-button block">
                  Consultar mis solicitudes
                </Link>
              </div>
            ) : null}
            <fieldset disabled={pending} className="form-fields">
              <div className="field">
                <label htmlFor="titulo">Título</label>
                <input
                  id="titulo"
                  name="titulo"
                  required
                  minLength={5}
                  maxLength={200}
                  placeholder="Ej. No puedo acceder al sistema de ventas"
                  value={form.titulo}
                  onChange={(event) => update("titulo", event.target.value)}
                  aria-invalid={Boolean(errors.titulo)}
                  aria-describedby="titulo-help"
                />
                <span
                  id="titulo-help"
                  className={errors.titulo ? "field-error" : "helper-text"}
                >
                  {errors.titulo ||
                    "Una frase breve que nos ayude a entender tu solicitud."}
                </span>
              </div>
              <fieldset className="type-choice">
                <legend>Tipo de solicitud</legend>
                <div>
                  {(
                    [
                      [
                        "incidente",
                        "Incidente",
                        "Algo no funciona como debería.",
                        Bug,
                      ],
                      [
                        "mejora",
                        "Mejora",
                        "Una idea para trabajar mejor.",
                        Sparkles,
                      ],
                    ] as const
                  ).map(([value, label, description, Icon]) => (
                    <label
                      key={value}
                      className={form.tipo === value ? "checked" : ""}
                    >
                      <input
                        type="radio"
                        name="tipo"
                        value={value}
                        checked={form.tipo === value}
                        onChange={() => update("tipo", value as TipoSolicitud)}
                      />
                      <Icon size={21} aria-hidden="true" />
                      <span>
                        <strong>{label}</strong>
                        <small>{description}</small>
                      </span>
                      <span className="radio-indicator" aria-hidden="true">
                        {form.tipo === value ? <Check size={12} /> : null}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="form-row">
                <div className="field">
                  <label htmlFor="area">Área</label>
                  <select
                    id="area"
                    name="area"
                    value={form.area}
                    required
                    onChange={(event) => update("area", event.target.value)}
                    aria-invalid={Boolean(errors.area)}
                    aria-describedby={errors.area ? "area-error" : undefined}
                  >
                    <option value="">Selecciona un área</option>
                    {AREAS.map((area) => (
                      <option key={area}>{area}</option>
                    ))}
                  </select>
                  {errors.area ? (
                    <span className="field-error" id="area-error">
                      {errors.area}
                    </span>
                  ) : null}
                </div>
                <div className="field">
                  <label htmlFor="prioridad_solicitada">
                    Prioridad solicitada
                  </label>
                  <select
                    id="prioridad_solicitada"
                    name="prioridad_solicitada"
                    value={form.prioridad_solicitada}
                    onChange={(event) =>
                      update(
                        "prioridad_solicitada",
                        event.target.value as PrioridadTipo,
                      )
                    }
                  >
                    <option value="baja">Baja</option>
                    <option value="media">Media</option>
                    <option value="alta">Alta</option>
                    <option value="urgente">Urgente</option>
                  </select>
                </div>
              </div>
              <div className="field">
                <label htmlFor="descripcion">Descripción</label>
                <textarea
                  id="descripcion"
                  name="descripcion"
                  required
                  minLength={10}
                  rows={7}
                  placeholder="Describe el problema o la mejora. ¿Qué ocurre, a quién afecta y qué esperabas que sucediera?"
                  value={form.descripcion}
                  onChange={(event) =>
                    update("descripcion", event.target.value)
                  }
                  aria-invalid={Boolean(errors.descripcion)}
                  aria-describedby="descripcion-help"
                />
                <span
                  id="descripcion-help"
                  className={errors.descripcion ? "field-error" : "helper-text"}
                >
                  {errors.descripcion ||
                    "Incluye el contexto y los pasos necesarios. Mínimo 10 caracteres."}
                </span>
              </div>
              <FileUploadZone
                files={files}
                onChange={setFiles}
                disabled={pending}
              />
            </fieldset>
            {pending ? (
              <div className="notice notice-info" role="status">
                <LoaderCircle
                  size={19}
                  className="animate-spin shrink-0"
                  aria-hidden="true"
                />
                <span className="upload-progress">
                  {uploadProgress ||
                    "Registrando en base de datos y creando ticket en Jira Cloud..."}
                </span>
              </div>
            ) : null}
            <div className="form-actions">
              <Link to="/solicitudes" className="button button-secondary">
                {pending ? "Ver solicitudes" : "Cancelar"}
              </Link>
              <button className="button button-primary" disabled={pending}>
                {pending ? (
                  <LoaderCircle
                    size={17}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Send size={17} aria-hidden="true" />
                )}
                {pending
                  ? uploadProgress
                    ? "Enviando archivos…"
                    : "Registrando…"
                  : "Registrar solicitud"}
              </button>
            </div>
          </form>
        </section>
        <aside className="form-aside">
          <span className="aside-icon">
            <ShieldCheck size={25} aria-hidden="true" />
          </span>
          <h2>
            De tu equipo,
            <br />
            al equipo técnico.
          </h2>
          <p>Un registro claro ayuda a encontrar una solución más rápido.</p>
          <ol>
            <li>
              <span>1</span>
              <div>
                <strong>Registramos tu solicitud</strong>
                <p>El portal conserva la información que envías.</p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>La conectamos con Jira</strong>
                <p>El equipo técnico recibe un ticket para gestionarla.</p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Puedes seguir el avance</strong>
                <p>Consulta el estado y la trazabilidad en el detalle.</p>
              </div>
            </li>
          </ol>
          <p className="aside-note">
            La prioridad definitiva la determina el equipo técnico en Jira.
          </p>
        </aside>
      </div>
    </>
  );
}
