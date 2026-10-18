"use client";

import { useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import {
  generarScriptPythonScipy,
  generarScriptPinnPyTorch,
  generarScriptJulia,
  generarJupyterNotebook,
} from "./exportarSimulacion";
import { derivarCapaLimite } from "./analisisCapaLimite";
import { auditarMallaNumerica } from "./analisisEstabilidadNumerica";
import { descargarTexto } from "./paquetePublicacion";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function ModalSimulacion({
  abierto,
  cerrar,
  nombreModelo,
  f,
}: {
  abierto: boolean;
  cerrar: () => void;
  nombreModelo: string;
  f: FormulacionNucleo;
}) {
  const [pestana, setPestana] = useState<"python" | "notebook" | "pinn" | "julia" | "asintotica" | "estabilidad">("python");
  const [copiado, setCopiado] = useState(false);

  if (!abierto) return null;

  const slug = nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const scriptPython = generarScriptPythonScipy(f, nombreModelo);
  const scriptPinn = generarScriptPinnPyTorch(f, nombreModelo);
  const scriptJulia = generarScriptJulia(f, nombreModelo);
  const scriptNotebook = generarJupyterNotebook(f, nombreModelo);
  const capaLimite = derivarCapaLimite(f);
  const auditoria = auditarMallaNumerica(f);

  let contenidoActivo = "";
  let nombreArchivoActivo = "";
  let tipoMime = "text/plain";

  switch (pestana) {
    case "python":
      contenidoActivo = scriptPython;
      nombreArchivoActivo = `simulacion_${slug}_scipy.py`;
      tipoMime = "text/x-python";
      break;
    case "notebook":
      contenidoActivo = scriptNotebook;
      nombreArchivoActivo = `simulacion_${slug}_interactiva.ipynb`;
      tipoMime = "application/x-ipynb+json";
      break;
    case "pinn":
      contenidoActivo = scriptPinn;
      nombreArchivoActivo = `pinn_${slug}_pytorch.py`;
      tipoMime = "text/x-python";
      break;
    case "julia":
      contenidoActivo = scriptJulia;
      nombreArchivoActivo = `simulacion_${slug}.jl`;
      tipoMime = "text/x-julia";
      break;
    case "asintotica":
      contenidoActivo = capaLimite.explicacionFisica;
      nombreArchivoActivo = `analisis_capa_limite_${slug}.txt`;
      break;
    case "estabilidad":
      contenidoActivo = auditoria.diagnosticoComputacional;
      nombreArchivoActivo = `auditoria_malla_${slug}.txt`;
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
    <div className="adim-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="adim-sim-title">
      <div className="adim-modal">
        <header className="adim-modal-header">
          <div>
            <span className="adim-eyebrow">Simulación Numérica e Inteligencia Computacional</span>
            <h2 id="adim-sim-title">Generador de Solvers Numéricos y PINNs (Python / Julia)</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Código ejecutable listo para correr en tu entorno local, Google Colab o clúster de cómputo.
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
              className={`adim-modal-tab ${pestana === "python" ? "is-active" : ""}`}
              onClick={() => setPestana("python")}
            >
              🐍 Python (SciPy solve_ivp)
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "notebook" ? "is-active" : ""}`}
              onClick={() => setPestana("notebook")}
            >
              📓 Jupyter Notebook (.ipynb)
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "pinn" ? "is-active" : ""}`}
              onClick={() => setPestana("pinn")}
            >
              🧠 PINN (PyTorch)
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "julia" ? "is-active" : ""}`}
              onClick={() => setPestana("julia")}
            >
              🟣 Julia (DiffEq.jl)
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "asintotica" ? "is-active" : ""}`}
              onClick={() => setPestana("asintotica")}
            >
              📐 Expansiones Acopladas (Capa Límite)
            </button>
            <button
              type="button"
              className={`adim-modal-tab ${pestana === "estabilidad" ? "is-active" : ""}`}
              onClick={() => setPestana("estabilidad")}
            >
              ⚡ Auditoría de Malla (CFL / Péclet)
            </button>
          </div>

          <div className="adim-modal-actions">
            <button
              type="button"
              className="adim-button"
              onClick={copiarAlPortapapeles}
              title="Copiar contenido al portapapeles"
            >
              {copiado ? "✓ Copiado" : "📋 Copiar"}
            </button>
            <button
              type="button"
              className="adim-btn-primary"
              onClick={() => descargarTexto(nombreArchivoActivo, contenidoActivo, tipoMime)}
              title="Descargar archivo"
            >
              💾 Descargar {nombreArchivoActivo}
            </button>
          </div>
        </div>

        <div className="adim-modal-body">
          {pestana === "asintotica" ? (
            <div className="p-4 bg-zinc-900 rounded text-zinc-100 text-sm space-y-4">
              <h4 className="text-emerald-400 font-semibold text-base">
                Teoría Formal de Expansiones Asintóticas Acopladas (Matched Asymptotic Expansions)
              </h4>
              <p className="text-zinc-300 leading-relaxed">{capaLimite.explicacionFisica}</p>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                <span className="text-xs text-zinc-400 block mb-1">1. Solución Regular Exterior (Outer Solution):</span>
                <FormulaLatex bloque latex={capaLimite.ecuacionExteriorLatex} lectura="Solución exterior" />
              </div>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                <span className="text-xs text-zinc-400 block mb-1">
                  2. Solución de Capa Límite Interior (Inner Solution) con coordenada estirada:
                </span>
                <FormulaLatex bloque latex={capaLimite.ecuacionInteriorLatex} lectura="Solución interior" />
              </div>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                <span className="text-xs text-zinc-400 block mb-1">
                  3. Principio de Acoplamiento Asintótico de Prandtl - Van Dyke:
                </span>
                <FormulaLatex bloque latex={capaLimite.condicionAcoplamientoLatex} lectura="Acoplamiento asintótico" />
              </div>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                <span className="text-xs text-zinc-400 block mb-1">4. Solución Uniformemente Válida Compuesta:</span>
                <FormulaLatex bloque latex={capaLimite.solucionCompuestaLatex} lectura="Solución compuesta" />
              </div>
            </div>
          ) : pestana === "estabilidad" ? (
            <div className="p-4 bg-zinc-900 rounded text-zinc-100 text-sm space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-amber-400 font-semibold text-base">
                  Auditoría Computacional de Malla y Criterios de Estabilidad Numérica (CFL / Péclet)
                </h4>
                <span className={`px-2.5 py-1 rounded text-xs font-semibold ${auditoria.esRigido ? "bg-rose-900/80 text-rose-200 border border-rose-700" : "bg-emerald-900/80 text-emerald-200 border border-emerald-700"}`}>
                  {auditoria.esRigido ? "⚠️ Sistema Rígido (Stiff PDE)" : "✓ Malla Bien Condicionada"}
                </span>
              </div>
              <p className="text-zinc-300 leading-relaxed">
                Diagnóstico automatizado de límites de discretización espaciotemporal según el número de Péclet de celda y la condición Courant-Friedrichs-Lewy (CFL).
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                  <span className="text-xs text-zinc-400 block mb-1">Péclet de celda (Pe_Δξ = Pe·Δξ):</span>
                  <span className={`text-lg font-mono font-bold ${auditoria.criterioOscilacionSatisfecho ? "text-emerald-400" : "text-rose-400"}`}>
                    {auditoria.pecletCelda.toFixed(3)}
                  </span>
                  <small className="block text-[11px] text-zinc-500 mt-1">
                    {auditoria.criterioOscilacionSatisfecho ? "✓ ≤ 2 (Sin oscilaciones espurias)" : `Alerta: > 2 (Requiere Upwind o Nx ≥ ${auditoria.nxMinimoRecomendado})`}
                  </small>
                </div>

                <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                  <span className="text-xs text-zinc-400 block mb-1">CFL Difusivo (Δτ ≤ Δξ² / 2Fo):</span>
                  <span className="text-lg font-mono font-bold text-sky-400">
                    {auditoria.dtMaxDifusivo.toExponential(3)}
                  </span>
                  <small className="block text-[11px] text-zinc-500 mt-1">
                    Paso temporal crítico para esquemas explícitos
                  </small>
                </div>

                <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                  <span className="text-xs text-zinc-400 block mb-1">Índice de Rigidez Asintótica (S):</span>
                  <span className={`text-lg font-mono font-bold ${auditoria.esRigido ? "text-amber-400" : "text-emerald-400"}`}>
                    {auditoria.indiceRigidez.toFixed(1)}
                  </span>
                  <small className="block text-[11px] text-zinc-500 mt-1">
                    Pasos requeridos en solver explícito: ~{auditoria.pasosTiempoEstimados.toLocaleString()}
                  </small>
                </div>
              </div>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950 space-y-2">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span>Esquema espacial recomendado:</span>
                  <span className="font-semibold text-zinc-200">{auditoria.esquemaEspacialRecomendado}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span>Integrador temporal recomendado:</span>
                  <span className="font-semibold text-emerald-400">{auditoria.integradorTemporalRecomendado}</span>
                </div>
              </div>

              <div className="border border-zinc-700 p-3 rounded bg-zinc-950">
                <span className="text-xs text-zinc-400 block mb-1">Dictamen del Auditor Matemático:</span>
                <p className="text-zinc-200 text-xs leading-relaxed">{auditoria.diagnosticoComputacional}</p>
              </div>
            </div>
          ) : (
            <pre className="adim-code-preview">
              <code>{contenidoActivo}</code>
            </pre>
          )}
        </div>

        <footer className="adim-modal-footer">
          <span>Integración rígida BDF de orden superior · Parámetros calculados algebraicamente del sistema canónico</span>
          <button type="button" className="adim-button" onClick={cerrar}>
            Cerrar
          </button>
        </footer>
      </div>
    </div>
  );
}
