"use client";

import { useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import {
  BIBTEX_PUBLICACION,
  MANUSCRITO_TEORICO_TEX,
  generarReadmePublicacion,
  descargarTexto,
  descargarPaqueteCompleto,
  descargarPaqueteZip,
} from "./paquetePublicacion";
import { exportarDesarrollo } from "./exportarDesarrollo";

export default function ModalPaquetePublicacion({
  abierto,
  cerrar,
  nombreModelo,
  indiceForma,
  f,
}: {
  abierto: boolean;
  cerrar: () => void;
  nombreModelo: string;
  indiceForma: number;
  f: FormulacionNucleo;
}) {
  const [pestana, setPestana] = useState<"deduccion" | "manuscrito" | "bibtex" | "readme">("deduccion");
  const [copiado, setCopiado] = useState(false);

  if (!abierto) return null;

  const slug = nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const deduccionTex = exportarDesarrollo(f);
  const readmeMd = generarReadmePublicacion(nombreModelo);

  let contenidoActivo = "";
  let nombreArchivoActivo = "";
  let tipoMime = "text/plain";

  switch (pestana) {
    case "deduccion":
      contenidoActivo = deduccionTex;
      nombreArchivoActivo = `deduccion-${slug}-forma-${indiceForma + 1}.tex`;
      tipoMime = "text/x-tex";
      break;
    case "manuscrito":
      contenidoActivo = MANUSCRITO_TEORICO_TEX;
      nombreArchivoActivo = "manuscrito_teorico.tex";
      tipoMime = "text/x-tex";
      break;
    case "bibtex":
      contenidoActivo = BIBTEX_PUBLICACION;
      nombreArchivoActivo = "referencias.bib";
      tipoMime = "text/x-bibtex";
      break;
    case "readme":
      contenidoActivo = readmeMd;
      nombreArchivoActivo = "README.md";
      tipoMime = "text/markdown";
      break;
  }

  function copiarAlPortapapeles() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(contenidoActivo).then(() => {
        setCopiado(true);
        setTimeout(() => setCopiado(false), 2000);
      });
    }
  }

  return (
    <div className="adim-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="adim-modal-title">
      <div className="adim-modal">
        <header className="adim-modal-header">
          <div>
            <span className="adim-eyebrow">Publicación y Documentación Académica</span>
            <h2 id="adim-modal-title">Paquete Científico de Publicación (LaTeX + BibTeX)</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Archivos fuente listos para compilar en Overleaf, TeX Live o publicar en un repositorio de GitHub.
            </p>
          </div>
          <button type="button" className="adim-modal-close-btn" onClick={cerrar} aria-label="Cerrar modal">
            ✕
          </button>
        </header>

        <div className="adim-modal-toolbar">
          <div className="adim-modal-tabs">
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "deduccion" ? "is-active" : ""}`}
              onClick={() => setPestana("deduccion")}
            >
              📄 deduccion_modelo.tex
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "manuscrito" ? "is-active" : ""}`}
              onClick={() => setPestana("manuscrito")}
            >
              📜 manuscrito_teorico.tex
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "bibtex" ? "is-active" : ""}`}
              onClick={() => setPestana("bibtex")}
            >
              📚 referencias.bib
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "readme" ? "is-active" : ""}`}
              onClick={() => setPestana("readme")}
            >
              📖 README.md
            </button>
          </div>

          <div className="adim-modal-actions">
            <button
              type="button"
              className="adim-button"
              onClick={copiarAlPortapapeles}
              title="Copiar contenido al portapapeles"
            >
              {copiado ? "✓ Copiado" : "📋 Copiar archivo"}
            </button>
            <button
              type="button"
              className="adim-button"
              onClick={() => descargarTexto(nombreArchivoActivo, contenidoActivo, tipoMime)}
              title="Descargar este archivo individualmente"
            >
              💾 Descargar {nombreArchivoActivo}
            </button>
            <button
              type="button"
              className="adim-button"
              onClick={() => descargarPaqueteCompleto(nombreModelo, indiceForma, f)}
              title="Descargar los 4 archivos secuencialmente"
            >
              📥 4 archivos sueltos
            </button>
            <button
              type="button"
              className="adim-btn-primary"
              onClick={() => descargarPaqueteZip(nombreModelo, indiceForma, f)}
              title="Descargar paquete completo comprimido (.ZIP) listo para subir directamente a Overleaf o descomprimir"
            >
              📦 Descargar Paquete (.ZIP para Overleaf)
            </button>
          </div>
        </div>

        <div className="adim-modal-body">
          <pre className="adim-code-preview">
            <code>{contenidoActivo}</code>
          </pre>
        </div>

        <footer className="adim-modal-footer">
          <span>Formato amsmath estándar · Sin paquetes externos incompatibles · Compatible con Overleaf y pdflatex</span>
          <button type="button" className="adim-button" onClick={cerrar}>
            Cerrar
          </button>
        </footer>
      </div>
    </div>
  );
}
