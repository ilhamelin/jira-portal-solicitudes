import { useEffect, useId, useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";

export const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MIME: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  pdf: "application/pdf",
  txt: "text/plain",
};

export function formatFileSize(size: number) {
  return size >= 1024 * 1024
    ? `${(size / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.ceil(size / 1024))} KB`;
}

export function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function FilePreview({ file }: { file: File }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!file.type.startsWith("image/")) return;
    const preview = URL.createObjectURL(file);
    setUrl(preview);
    return () => URL.revokeObjectURL(preview);
  }, [file]);
  return url ? (
    <img
      className="file-preview"
      src={url}
      alt={`Vista previa de ${file.name}`}
    />
  ) : (
    <FileText size={24} aria-hidden="true" />
  );
}

export function FileUploadZone({
  files,
  onChange,
  disabled = false,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const helpId = useId();
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  function addFiles(incoming: File[]) {
    if (disabled) return;
    const messages: string[] = [];
    const next = [...files];
    for (const file of incoming) {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!MIME[extension] || (file.type && file.type !== MIME[extension])) {
        messages.push(`${file.name}: solo PNG, JPEG, PDF y TXT.`);
      } else if (file.size === 0 || file.size > MAX_FILE_SIZE) {
        messages.push(
          `${file.name}: el tamaño debe ser mayor que cero y hasta 10 MB.`,
        );
      } else if (
        !next.some(
          (existing) =>
            existing.name === file.name &&
            existing.size === file.size &&
            existing.lastModified === file.lastModified,
        )
      ) {
        // Algunos navegadores no informan MIME para .txt; normalizar antes de enviarlo.
        next.push(
          file.type
            ? file
            : new File([file], file.name, {
                type: MIME[extension],
                lastModified: file.lastModified,
              }),
        );
      }
    }
    setErrors(messages);
    onChange(next);
  }
  return (
    <section className="file-upload-section" aria-label="Archivos adjuntos">
      <h2>
        Archivos adjuntos <span className="helper-text">(opcional)</span>
      </h2>
      <div
        className={`file-dropzone ${dragging && !disabled ? "file-dropzone-active" : ""}`}
        aria-disabled={disabled}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          addFiles(Array.from(event.dataTransfer.files));
        }}
      >
        <UploadCloud size={28} aria-hidden="true" />
        <p>Arrastra tus archivos aquí</p>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => input.current?.click()}
          disabled={disabled}
          aria-describedby={helpId}
        >
          Seleccionar archivos
        </button>
        <input
          ref={input}
          type="file"
          hidden
          multiple
          accept=".png,.jpg,.jpeg,.pdf,.txt"
          disabled={disabled}
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <p className="helper-text" id={helpId}>
          PNG, JPEG, PDF o TXT. Hasta 10 MB por archivo. Se envían después de
          crear el ticket.
        </p>
      </div>
      {errors.length ? (
        <ul className="field-error" role="alert">
          {errors.map((error, index) => (
            <li key={index}>{error}</li>
          ))}
        </ul>
      ) : null}
      {files.length ? (
        <ul className="attachment-list" aria-label="Archivos seleccionados">
          {files.map((file, index) => (
            <li key={`${file.name}-${file.lastModified}-${file.size}`}>
              <FilePreview file={file} />
              <div className="attachment-info">
                <strong>{file.name}</strong>
                <small>{formatFileSize(file.size)}</small>
              </div>
              <button
                type="button"
                className="icon-button"
                disabled={disabled}
                aria-label={`Quitar ${file.name}`}
                onClick={() =>
                  onChange(files.filter((_, position) => position !== index))
                }
              >
                <X size={17} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
