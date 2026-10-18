"use client";

import { useId, useMemo, useState } from "react";
import FormulaLatex from "../flowsheet/FormulaLatex";

type TipoNoLinealidad = "arrhenius" | "cubica" | "langmuir";

export default function PanelBifurcaciones({ daNominal = 2.0 }: { daNominal?: number }) {
  const baseId = useId();
  const [tipo, setTipo] = useState<TipoNoLinealidad>("arrhenius");
  const [da, setDa] = useState(() => Math.max(0.2, Math.min(10.0, daNominal)));
  const [beta, setBeta] = useState(1.5); // Tasa de disipación / enfriamiento
  const [gamma, setGamma] = useState(20.0); // Parámetro de Arrhenius

  // Cálculo analítico de la curva en S: Da en función de theta_ss
  // F(theta) = Da * R(theta) - beta * theta = 0 => Da = beta * theta / R(theta)
  const puntosCurva = useMemo(() => {
    const N = 120;
    const datos: Array<{ theta: number; daCalculado: number; estabilidad: "estable" | "inestable" }> = [];

    const thetaMax = tipo === "arrhenius" ? 1.0 : tipo === "cubica" ? 1.2 : 4.0;
    const dTheta = thetaMax / N;

    for (let i = 1; i <= N; i++) {
      const th = i * dTheta;
      let r = 1.0;

      if (tipo === "arrhenius") {
        // Modelo S-curve de Frank-Kamenetskii / Semenov
        r = Math.exp(gamma * th / (1.0 + th));
      } else if (tipo === "cubica") {
        // Cinética de campo de fase autocatalítica
        r = Math.max(1e-4, (1.0 - th) * (th + 0.2));
      } else {
        // Langmuir-Hinshelwood con inhibición por producto
        r = th / (1.0 + 3.0 * th * th);
      }

      const daCalc = (beta * th) / Math.max(1e-6, r);

      if (Number.isFinite(daCalc) && daCalc > 0 && daCalc < 20) {
        datos.push({
          theta: th,
          daCalculado: daCalc,
          estabilidad: "estable" // Se clasificará abajo según derivadas
        });
      }
    }

    // Clasificar ramas por pendiente d(Da)/d(theta):
    // Si d(Da)/d(theta) < 0 => la rama es inestable (fuelle de la curva en S)
    for (let i = 1; i < datos.length - 1; i++) {
      const dDa = (datos[i + 1].daCalculado - datos[i - 1].daCalculado) / (2 * dTheta);
      datos[i].estabilidad = dDa >= 0 ? "estable" : "inestable";
    }

    return datos;
  }, [tipo, beta, gamma]);

  // Encontrar puntos de bifurcación silla-nodo (extremos locales de Da)
  const bifurcaciones = useMemo(() => {
    let daIgnicion: number | null = null;
    let daExtincion: number | null = null;

    for (let i = 1; i < puntosCurva.length - 1; i++) {
      const prev = puntosCurva[i - 1].daCalculado;
      const curr = puntosCurva[i].daCalculado;
      const next = puntosCurva[i + 1].daCalculado;

      if (curr > prev && curr > next) {
        daIgnicion = curr; // Máximo local: límite de ignición
      }
      if (curr < prev && curr < next) {
        daExtincion = curr; // Mínimo local: límite de extinción
      }
    }

    const tieneHisteresis = daIgnicion !== null && daExtincion !== null && daIgnicion > daExtincion;

    return {
      daIgnicion,
      daExtincion,
      tieneHisteresis,
      zonaActual: tieneHisteresis && da >= daExtincion! && da <= daIgnicion! ? "biestable" : "monoestable"
    };
  }, [puntosCurva, da]);

  // Dimensiones SVG
  const width = 560;
  const height = 240;
  const padL = 45;
  const padR = 20;
  const padT = 20;
  const padB = 35;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const maxDaGrafica = 15.0;
  const maxThetaGrafica = tipo === "arrhenius" ? 1.0 : tipo === "cubica" ? 1.2 : 4.0;

  const toSvgX = (d: number) => padL + Math.min(1, Math.max(0, d / maxDaGrafica)) * plotW;
  const toSvgY = (th: number) => padT + (1 - Math.min(1, Math.max(0, th / maxThetaGrafica))) * plotH;

  // Segmentación de curvas estables e inestables
  const ramas = useMemo(() => {
    const segmentos: Array<{ path: string; estabilidad: "estable" | "inestable" }> = [];
    let actual: Array<{ da: number; th: number }> = [];
    let estActual: "estable" | "inestable" = "estable";

    for (const p of puntosCurva) {
      if (p.estabilidad !== estActual) {
        if (actual.length > 1) {
          const pathStr = actual.map((pt, i) => `${i === 0 ? "M" : "L"} ${toSvgX(pt.da).toFixed(1)} ${toSvgY(pt.th).toFixed(1)}`).join(" ");
          segmentos.push({ path: pathStr, estabilidad: estActual });
        }
        actual = [{ da: p.daCalculado, th: p.theta }];
        estActual = p.estabilidad;
      } else {
        actual.push({ da: p.daCalculado, th: p.theta });
      }
    }
    if (actual.length > 1) {
      const pathStr = actual.map((pt, i) => `${i === 0 ? "M" : "L"} ${toSvgX(pt.da).toFixed(1)} ${toSvgY(pt.th).toFixed(1)}`).join(" ");
      segmentos.push({ path: pathStr, estabilidad: estActual });
    }
    return segmentos;
  }, [puntosCurva, toSvgX, toSvgY]);

  // Raíces para el Da actual
  const raicesActuales = useMemo(() => {
    const r: number[] = [];
    for (let i = 0; i < puntosCurva.length - 1; i++) {
      const d1 = puntosCurva[i].daCalculado;
      const d2 = puntosCurva[i + 1].daCalculado;
      if ((d1 <= da && d2 >= da) || (d1 >= da && d2 <= da)) {
        const factor = Math.abs(d2 - d1) > 1e-6 ? (da - d1) / (d2 - d1) : 0;
        r.push(puntosCurva[i].theta + factor * (puntosCurva[i + 1].theta - puntosCurva[i].theta));
      }
    }
    return r;
  }, [puntosCurva, da]);

  return (
    <div className="adim-group-pill p-5 mt-6 border border-zinc-700 bg-zinc-950/80 rounded-xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <h4 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <span>📈</span>
            <span>Analizador de Multiplicidad de Estados Estacionarios & Curva en S</span>
          </h4>
          <p className="text-xs text-zinc-400 mt-0.5">
            Detección de bifurcaciones de ensilladura (Saddle-Node), histéresis y biestabilidad térmica/cinética.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {(["arrhenius", "cubica", "langmuir"] as const).map(t => (
            <button
              key={t}
              type="button"
              className={`adim-button text-xs py-1 px-2.5 ${tipo === t ? "is-active font-semibold" : ""}`}
              onClick={() => setTipo(t)}
            >
              {t === "arrhenius" ? "Térmico (Arrhenius)" : t === "cubica" ? "Cúbica (Autocatálisis)" : "Langmuir-Hinshelwood"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-6 items-center">
        {/* Gráfico SVG de la curva en S */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 overflow-hidden">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto block select-none">
            <rect x={padL} y={padT} width={plotW} height={plotH} fill="#09090b" />

            {/* Franja de Biestabilidad / Histéresis si existe */}
            {bifurcaciones.tieneHisteresis && (
              <rect
                x={toSvgX(bifurcaciones.daExtincion!)}
                y={padT}
                width={toSvgX(bifurcaciones.daIgnicion!) - toSvgX(bifurcaciones.daExtincion!)}
                height={plotH}
                fill="rgba(239, 68, 68, 0.12)"
                stroke="rgba(239, 68, 68, 0.35)"
                strokeDasharray="3 3"
              />
            )}

            {/* Líneas de cuadrícula */}
            {[0, maxThetaGrafica / 2, maxThetaGrafica].map(val => (
              <g key={val}>
                <line
                  x1={padL}
                  y1={toSvgY(val)}
                  x2={width - padR}
                  y2={toSvgY(val)}
                  stroke="#27272a"
                  strokeWidth="1"
                />
                <text x={padL - 6} y={toSvgY(val) + 3} fill="#71717a" fontSize="10" textAnchor="end" fontFamily="monospace">
                  {val.toFixed(1)}
                </text>
              </g>
            ))}

            {[0, 5, 10, 15].map(val => (
              <g key={val}>
                <line
                  x1={toSvgX(val)}
                  y1={padT}
                  x2={toSvgX(val)}
                  y2={height - padB}
                  stroke="#27272a"
                  strokeWidth="1"
                />
                <text x={toSvgX(val)} y={height - padB + 14} fill="#71717a" fontSize="10" textAnchor="middle" fontFamily="monospace">
                  {val.toFixed(0)}
                </text>
              </g>
            ))}

            {/* Línea vertical para el Da actual */}
            <line
              x1={toSvgX(da)}
              y1={padT}
              x2={toSvgX(da)}
              y2={height - padB}
              stroke="#06b6d4"
              strokeWidth="1.5"
              strokeDasharray="4 2"
            />

            {/* Ramas de la Curva en S */}
            {ramas.map((r, i) => (
              <path
                key={i}
                d={r.path}
                fill="none"
                stroke={r.estabilidad === "estable" ? "#10b981" : "#ef4444"}
                strokeWidth={r.estabilidad === "estable" ? "2.5" : "2"}
                strokeDasharray={r.estabilidad === "estable" ? undefined : "4 3"}
              />
            ))}

            {/* Puntos de bifurcación */}
            {bifurcaciones.daIgnicion && (
              <circle
                cx={toSvgX(bifurcaciones.daIgnicion)}
                cy={toSvgY(puntosCurva.find(p => Math.abs(p.daCalculado - bifurcaciones.daIgnicion!) < 0.1)?.theta ?? 0)}
                r="4.5"
                fill="#f59e0b"
                stroke="#fff"
                strokeWidth="1.5"
              />
            )}
            {bifurcaciones.daExtincion && (
              <circle
                cx={toSvgX(bifurcaciones.daExtincion)}
                cy={toSvgY(puntosCurva.find(p => Math.abs(p.daCalculado - bifurcaciones.daExtincion!) < 0.1)?.theta ?? 0)}
                r="4.5"
                fill="#f59e0b"
                stroke="#fff"
                strokeWidth="1.5"
              />
            )}

            {/* Raíces estacionarias bajo el Da actual */}
            {raicesActuales.map((rTheta, idx) => (
              <circle
                key={idx}
                cx={toSvgX(da)}
                cy={toSvgY(rTheta)}
                r="5"
                fill="#06b6d4"
                stroke="#09090b"
                strokeWidth="2"
              />
            ))}

            {/* Etiquetas */}
            <text x={padL + plotW / 2} y={height - 6} fill="#a1a1aa" fontSize="11" textAnchor="middle">
              Número de Damköhler (Da)
            </text>
            <text
              x={14}
              y={padT + plotH / 2}
              fill="#a1a1aa"
              fontSize="11"
              textAnchor="middle"
              transform={`rotate(-90, 14, ${padT + plotH / 2})`}
            >
              Estado Estacionario θ_ss
            </text>
          </svg>

          {/* Leyenda */}
          <div className="flex flex-wrap items-center justify-center gap-4 mt-2 text-xs">
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-3 h-0.5 bg-emerald-400 inline-block"></span>
              Rama Estable
            </span>
            <span className="flex items-center gap-1.5 text-rose-400 font-medium">
              <span className="w-3 h-0.5 bg-rose-400 border-b border-dashed inline-block"></span>
              Rama Inestable (Silla)
            </span>
            <span className="flex items-center gap-1.5 text-amber-400 font-medium">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"></span>
              Bifurcación Saddle-Node
            </span>
            <span className="flex items-center gap-1.5 text-cyan-400 font-medium">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block"></span>
              Operación Actual ({raicesActuales.length} {raicesActuales.length === 1 ? "raíz" : "raíces"})
            </span>
          </div>
        </div>

        {/* Panel de Controles y Diagnóstico para /motor */}
        <div className="space-y-4 text-xs bg-zinc-900/60 p-4 rounded-lg border border-zinc-800">
          <div>
            <div className="flex justify-between items-baseline mb-1">
              <span className="text-zinc-300 font-semibold">Número de Damköhler (Da):</span>
              <span className="font-mono text-cyan-400 font-bold">{da.toFixed(2)}</span>
            </div>
            <input
              id={`${baseId}-slider-da`}
              aria-label="Numero de Damkohler Da"
              type="range"
              min="0.1"
              max="14.0"
              step="0.1"
              value={da}
              onChange={e => setDa(parseFloat(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between items-baseline mb-1">
              <span className="text-zinc-300 font-semibold">Parámetro de Disipación β:</span>
              <span className="font-mono text-emerald-400 font-bold">{beta.toFixed(2)}</span>
            </div>
            <input
              id={`${baseId}-slider-beta`}
              aria-label="Parametro de disipacion beta"
              type="range"
              min="0.5"
              max="4.0"
              step="0.1"
              value={beta}
              onChange={e => setBeta(parseFloat(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
          </div>

          {tipo === "arrhenius" && (
            <div>
              <div className="flex justify-between items-baseline mb-1">
                <span className="text-zinc-300 font-semibold">Energía de Activación γ:</span>
                <span className="font-mono text-amber-400 font-bold">{gamma.toFixed(1)}</span>
              </div>
              <input
                id={`${baseId}-slider-gamma`}
                aria-label="Energia de activacion gamma"
                type="range"
                min="5.0"
                max="30.0"
                step="1.0"
                value={gamma}
                onChange={e => setGamma(parseFloat(e.target.value))}
                className="w-full accent-amber-500 cursor-pointer"
              />
            </div>
          )}

          <div className="border-t border-zinc-800 pt-3 space-y-2">
            <h5 className="font-semibold uppercase tracking-wider text-amber-400 text-[11px]">
              Alerta de Convergencia para el Solver
            </h5>
            <div className={`p-2.5 rounded border text-[11px] leading-relaxed ${
              bifurcaciones.zonaActual === "biestable"
                ? "bg-rose-950/20 border-rose-800/60 text-rose-200"
                : "bg-emerald-950/20 border-emerald-800/60 text-emerald-200"
            }`}>
              {bifurcaciones.zonaActual === "biestable" ? (
                <>
                  <strong>⚠ Zona Biestable Activa (3 Raíces):</strong> Coexisten dos ramas estables separadas por un punto de ensilladura. 
                  El método de Newton en <em>Euler implícito</em> puede ciclar indefinidamente o saltar bruscamente (ignición/extinción).
                </>
              ) : (
                <>
                  <strong>✓ Zona Monoestable Segura (1 Raíz):</strong> El sistema converge monótonamente hacia el único estado estacionario físico sin riesgo de histéresis.
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
