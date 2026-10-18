"use client";

import { useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import FormulaLatex from "../flowsheet/FormulaLatex";
import DiagramaCapaLimite from "./DiagramaCapaLimite";

type ZonaRegimen = "conveccion" | "frente" | "difusion_reaccion" | "mezcla" | "acoplado";

export default function MapaRegimenes({ f }: { f: FormulacionNucleo }) {
  const [zonaSeleccionada, setZonaSeleccionada] = useState<ZonaRegimen>("acoplado");

  // Detectar números presentes en los grupos calculados
  const grupos = f.grupos ?? [];
  const tienePe = grupos.some(g => g.id.toLowerCase().includes("pe") || g.id.toLowerCase().includes("cfl"));
  const tieneDa = grupos.some(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("reac") || g.id.includes("k"));
  const tieneFo = grupos.some(g => g.id.toLowerCase().includes("fo"));
  const tieneA = grupos.some(g => g.id.toLowerCase().includes("a_") || g.id.toLowerCase().includes("esbeltez"));

  const infoZonas: Record<ZonaRegimen, {
    titulo: string;
    subtitulo: string;
    condicion: string;
    ecuacionReducidaLatex: string;
    descripcion: string;
    simplificaciones: string[];
    color: string;
    bg: string;
  }> = {
    conveccion: {
      titulo: "Zona I: Convección Dominante / Transporte Hiperbólico",
      subtitulo: "Flujo advectivo forzado sin resistencia química",
      condicion: "\\mathrm{Pe} \\gg 1, \\quad \\mathrm{Da} \\ll 1",
      ecuacionReducidaLatex: "\\frac{\\partial \\hat{c}}{\\partial \\hat{t}} + \\hat{u} \\frac{\\partial \\hat{c}}{\\partial \\hat{x}} \\approx 0",
      descripcion: "El transporte por velocidad convectiva supera por órdenes de magnitud la difusión molecular. Los frentes de concentración se propagan como ondas casi no dispersivas y la cinética química se comporta como congelada (frozen chemistry).",
      simplificaciones: [
        "El término difusivo molecular se anula como perturbación singular de orden O(1/Pe).",
        "La reacción química es demasiado lenta respecto al tiempo de residencia axial.",
        "Se forman capas límite finas de espesor delta ~ L / sqrt(Pe) en fronteras sólidas o salidas."
      ],
      color: "#0284c7",
      bg: "#f0f9ff"
    },
    frente: {
      titulo: "Zona II: Frente Reactivo Convectivo / Capa de Transición Rápida",
      subtitulo: "Interacción acoplada entre convección y cinética rápida",
      condicion: "\\mathrm{Pe} \\gg 1, \\quad \\mathrm{Da} \\gg 1",
      ecuacionReducidaLatex: "\\hat{u} \\frac{\\partial \\hat{c}}{\\partial \\hat{x}} \\approx \\mathrm{Da}\\,\\hat{R}(\\hat{c})",
      descripcion: "Régimen físico de ondas reactivas de alta velocidad, frentes de combustión o interfases cinéticas rápidas con acoplamiento convectivo. La zona de reacción se confina a un frente delgado o capa límite reactiva interna.",
      simplificaciones: [
        "Las especies químicas alcanzan rápidamente la variedad de equilibrio químico local.",
        "La difusión solo es relevante dentro de la capa reactiva interior (análisis por expansiones asintóticas acopladas).",
        "Ecuación rectora cuasi-estacionaria dominada por balance advectivo-cinético."
      ],
      color: "#d97706",
      bg: "#fffbeb"
    },
    difusion_reaccion: {
      titulo: "Zona III: Difusión-Reacción Homogénea (Longitud Intrínseca RD)",
      subtitulo: "Equilibrio entre dispersión molecular y consumo cinético",
      condicion: "\\mathrm{Pe} \\ll 1, \\quad \\mathrm{Da} \\sim \\mathcal{O}(1)",
      ecuacionReducidaLatex: "\\hat{\\nabla}^2 \\hat{c} \\approx \\phi^2\\,\\hat{c}, \\qquad \\phi = \\sqrt{\\mathrm{Da}}",
      descripcion: "Equilibrio canónico entre dispersión browniana y reactividad local (difusión-reacción en medios biológicos activos, esferoides celulares, organoides o morfógenos de Turing). La convección es despreciable y el perfil estacionario está gobernado puramente por la relación entre la escala geométrica y la longitud intrínseca de reacción-difusión.",
      simplificaciones: [
        "La velocidad convectiva es nula o despreciable frente a la relajación molecular.",
        "Ecuación elíptica pura de Helmholtz o difusión no lineal.",
        "Factor de efectividad eta = tanh(phi) / phi o penetración interfacial directamente aplicable."
      ],
      color: "#7c3aed",
      bg: "#faf5ff"
    },
    mezcla: {
      titulo: "Zona IV: Homogenización Difusiva Rápida / Régimen Espacialmente Uniforme",
      subtitulo: "Homogeneización rápida por relajación molecular",
      condicion: "\\mathrm{Pe} \\ll 1, \\quad \\mathrm{Da} \\ll 1",
      ecuacionReducidaLatex: "\\hat{\\nabla}^2 \\hat{c} \\approx 0 \\implies \\hat{c} \\approx \\text{constante}",
      descripcion: "La difusión molecular es tan rápida en comparación con el transporte neto y la reacción que los gradientes espaciales se disipan casi instantáneamente, conduciendo a un medio espacialmente uniforme gobernado por dinámicas puntuales homogéneas.",
      simplificaciones: [
        "El sistema es espacialmente uniforme (casi cero resistencia al transporte interno).",
        "No se desarrollan capas límite ni zonas de estancamiento.",
        "Las ecuaciones en derivadas parciales se reducen analíticamente a balances algebraicos o EDO ordinarias."
      ],
      color: "#16a34a",
      bg: "#f0fdf4"
    },
    acoplado: {
      titulo: "Zona Central: Balance Transitorio Acoplado Completo",
      subtitulo: "Competencia simultánea de todos los operadores del sistema continuo",
      condicion: "\\mathrm{Pe} \\sim 1, \\quad \\mathrm{Da} \\sim 1, \\quad \\mathrm{Fo} \\sim 1",
      ecuacionReducidaLatex: "\\frac{\\partial \\hat{c}}{\\partial \\hat{t}} + \\hat{u} \\frac{\\partial \\hat{c}}{\\partial \\hat{x}} = \\frac{1}{\\mathrm{Pe}} \\hat{\\nabla}^2 \\hat{c} + \\mathrm{Da}\\,\\hat{R}(\\hat{c})",
      descripcion: "Régimen físico transitorio no simplificable donde la acumulación temporal, la advección forzada, la dispersión molecular y la cinética química poseen el mismo orden de magnitud unidad O(1). Requiere integración numérica completa.",
      simplificaciones: [
        "Todos los sumandos del balance continuo son esenciales.",
        "Ningún término puede despreciarse sin perder fenómenos físicos críticos.",
        "La base canónica seleccionada garantiza el mejor condicionamiento matricial sin rigidez artificial."
      ],
      color: "#3f3f46",
      bg: "#f4f4f5"
    }
  };

  const actual = infoZonas[zonaSeleccionada];

  return (
    <div className="adim-regime-card">
      <div className="adim-regime-header">
        <div>
          <span className="adim-eyebrow">Análisis de Balanza Dominante y Perturbaciones Singulares</span>
          <h4 className="text-base font-medium text-zinc-900">Mapa Interactivo de Regímenes Asintóticos</h4>
          <p className="text-xs text-zinc-600 mt-1">
            Explora las reducciones de las EDP según los órdenes de magnitud de los números adimensionales deducidos.
          </p>
        </div>
        <div className="adim-regime-indicators">
          {tienePe && <span className="adim-stat-pill" title="Número de Péclet presente">Pe identificado</span>}
          {tieneDa && <span className="adim-stat-pill" title="Número de Damköhler presente">Da identificado</span>}
          {tieneFo && <span className="adim-stat-pill" title="Número de Fourier presente">Fo identificado</span>}
          {tieneA && <span className="adim-stat-pill" title="Factor de esbeltez presente">Esbeltez A presente</span>}
        </div>
      </div>

      <div className="adim-regime-layout">
        {/* Diagrama SVG del espacio de regímenes */}
        <div className="adim-regime-diagram-container">
          <svg viewBox="0 0 320 280" className="adim-regime-svg" aria-label="Plano logarítmico de regímenes asintóticos">
            {/* Fondo y cuadrantes */}
            <defs>
              <linearGradient id="grad-conveccion" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#e0f2fe" />
                <stop offset="100%" stopColor="#bae6fd" />
              </linearGradient>
              <linearGradient id="grad-frente" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#fef3c7" />
                <stop offset="100%" stopColor="#fde68a" />
              </linearGradient>
              <linearGradient id="grad-dif-reac" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#f3e8ff" />
                <stop offset="100%" stopColor="#e9d5ff" />
              </linearGradient>
              <linearGradient id="grad-mezcla" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#dcfce7" />
                <stop offset="100%" stopColor="#bbf7d0" />
              </linearGradient>
            </defs>

            {/* Ejes principales */}
            <rect x="35" y="25" width="260" height="220" fill="#fafafa" rx="6" stroke="#d4d4d8" strokeWidth="1" />

            {/* Cuadrante Superior Derecho: Frente Reactivo (Pe >> 1, Da >> 1) */}
            <rect
              x="165" y="25" width="130" height="110"
              fill={zonaSeleccionada === "frente" ? "#fef08a" : "url(#grad-frente)"}
              opacity="0.8"
              className="cursor-pointer transition-all hover:opacity-100"
              onClick={() => setZonaSeleccionada("frente")}
            />
            <text x="230" y="70" textAnchor="middle" fontSize="11" fontWeight="600" fill="#92400e">
              Frente Reactivo
            </text>
            <text x="230" y="85" textAnchor="middle" fontSize="9" fill="#b45309">
              Pe ≫ 1, Da ≫ 1
            </text>

            {/* Cuadrante Inferior Derecho: Convección Dominante (Pe >> 1, Da << 1) */}
            <rect
              x="165" y="135" width="130" height="110"
              fill={zonaSeleccionada === "conveccion" ? "#7dd3fc" : "url(#grad-conveccion)"}
              opacity="0.8"
              className="cursor-pointer transition-all hover:opacity-100"
              onClick={() => setZonaSeleccionada("conveccion")}
            />
            <text x="230" y="180" textAnchor="middle" fontSize="11" fontWeight="600" fill="#0369a1">
              Convección Pura
            </text>
            <text x="230" y="195" textAnchor="middle" fontSize="9" fill="#0284c7">
              Pe ≫ 1, Da ≪ 1
            </text>

            {/* Cuadrante Superior Izquierdo: Difusión-Reacción (Pe << 1, Da >> 1) */}
            <rect
              x="35" y="25" width="130" height="110"
              fill={zonaSeleccionada === "difusion_reaccion" ? "#d8b4fe" : "url(#grad-dif-reac)"}
              opacity="0.8"
              className="cursor-pointer transition-all hover:opacity-100"
              onClick={() => setZonaSeleccionada("difusion_reaccion")}
            />
            <text x="100" y="70" textAnchor="middle" fontSize="11" fontWeight="600" fill="#6b21a8">
              Módulo de Thiele
            </text>
            <text x="100" y="85" textAnchor="middle" fontSize="9" fill="#7e22ce">
              Pe ≪ 1, Da ≫ 1
            </text>

            {/* Cuadrante Inferior Izquierdo: Mezcla Perfecta (Pe << 1, Da << 1) */}
            <rect
              x="35" y="135" width="130" height="110"
              fill={zonaSeleccionada === "mezcla" ? "#86efac" : "url(#grad-mezcla)"}
              opacity="0.8"
              className="cursor-pointer transition-all hover:opacity-100"
              onClick={() => setZonaSeleccionada("mezcla")}
            />
            <text x="100" y="180" textAnchor="middle" fontSize="11" fontWeight="600" fill="#15803d">
              Mezcla Perfecta
            </text>
            <text x="100" y="195" textAnchor="middle" fontSize="9" fill="#16a34a">
              Pe ≪ 1, Da ≪ 1
            </text>

            {/* Líneas divisorias centrales */}
            <line x1="165" y1="25" x2="165" y2="245" stroke="#a1a1aa" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="35" y1="135" x2="295" y2="135" stroke="#a1a1aa" strokeWidth="1" strokeDasharray="3 3" />

            {/* Punto central del balance completo */}
            <circle
              cx="165" cy="135" r="22"
              fill={zonaSeleccionada === "acoplado" ? "#3f3f46" : "#e4e4e7"}
              stroke="#71717a" strokeWidth="1.5"
              className="cursor-pointer transition-transform hover:scale-110"
              onClick={() => setZonaSeleccionada("acoplado")}
            />
            <text
              x="165" y="138"
              textAnchor="middle" fontSize="8.5" fontWeight="600"
              fill={zonaSeleccionada === "acoplado" ? "#ffffff" : "#27272a"}
              pointerEvents="none"
            >
              Acoplado
            </text>

            {/* Etiquetas de los ejes */}
            <text x="165" y="265" textAnchor="middle" fontSize="10" fontWeight="600" fill="#3f3f46">
              log₁₀(Pe) → (Transporte Convectivo / Difusivo)
            </text>
            <text
              x="18" y="135" textAnchor="middle" fontSize="10" fontWeight="600" fill="#3f3f46"
              transform="rotate(-90 18 135)"
            >
              log₁₀(Da) → (Cinética / Transporte)
            </text>
          </svg>
          <div className="adim-regime-quick-nav">
            <button
              type="button"
              className={`adim-chip-btn ${zonaSeleccionada === "acoplado" ? "is-active" : ""}`}
              onClick={() => setZonaSeleccionada("acoplado")}
            >
              Balance Completo
            </button>
            <button
              type="button"
              className={`adim-chip-btn ${zonaSeleccionada === "conveccion" ? "is-active" : ""}`}
              onClick={() => setZonaSeleccionada("conveccion")}
            >
              Pe ≫ 1 (Convección)
            </button>
            <button
              type="button"
              className={`adim-chip-btn ${zonaSeleccionada === "frente" ? "is-active" : ""}`}
              onClick={() => setZonaSeleccionada("frente")}
            >
              Da ≫ 1, Pe ≫ 1 (Frente)
            </button>
            <button
              type="button"
              className={`adim-chip-btn ${zonaSeleccionada === "difusion_reaccion" ? "is-active" : ""}`}
              onClick={() => setZonaSeleccionada("difusion_reaccion")}
            >
              Thiele (Dif-Reacción)
            </button>
            <button
              type="button"
              className={`adim-chip-btn ${zonaSeleccionada === "mezcla" ? "is-active" : ""}`}
              onClick={() => setZonaSeleccionada("mezcla")}
            >
              Mezcla Perfecta
            </button>
          </div>
        </div>

        {/* Panel explicativo de la reducción asintótica */}
        <div className="adim-regime-details" style={{ backgroundColor: actual.bg, borderColor: actual.color }}>
          <div className="adim-regime-detail-header">
            <h5 style={{ color: actual.color }}>{actual.titulo}</h5>
            <span className="adim-regime-cond-badge">
              <FormulaLatex latex={actual.condicion} lectura={actual.subtitulo} />
            </span>
          </div>

          <p className="adim-regime-desc">{actual.descripcion}</p>

          <div className="adim-regime-eq-box">
            <span className="adim-regime-eq-label">Forma Asintótica Reducida de la EDP:</span>
            <FormulaLatex bloque latex={actual.ecuacionReducidaLatex} lectura="Ecuación reducida" />
          </div>

          <div className="adim-regime-points">
            <span className="adim-regime-points-label">Simplificaciones Físicas Convalidadas:</span>
            <ul>
              {actual.simplificaciones.map((s, idx) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <DiagramaCapaLimite peNominal={tienePe ? 15 : 5} />
    </div>
  );
}
