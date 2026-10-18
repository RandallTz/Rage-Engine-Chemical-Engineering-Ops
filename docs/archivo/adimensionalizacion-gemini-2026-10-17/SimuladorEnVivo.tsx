"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import FormulaLatex from "../flowsheet/FormulaLatex";

type TipoCinetica = "lineal" | "langmuir" | "biestable" | "cuadratica";

export default function SimuladorEnVivo({
  f,
  nombreModelo = "Sistema"
}: {
  f: FormulacionNucleo;
  nombreModelo?: string;
}) {
  // Extraer parámetros iniciales desde la formulación
  const [pe, setPe] = useState(() => {
    const g = (f.grupos ?? []).find(g => g.id.toLowerCase().includes("pe") || g.id.toLowerCase().includes("cfl"));
    return g ? 5.0 : 1.0;
  });
  const [da, setDa] = useState(() => {
    const g = (f.grupos ?? []).find(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("k"));
    return g ? 2.0 : 1.0;
  });
  const [fo, setFo] = useState(() => {
    const g = (f.grupos ?? []).find(g => g.id.toLowerCase().includes("fo"));
    return g ? 1.0 : 0.8;
  });

  const [cinetica, setCinetica] = useState<TipoCinetica>("langmuir");
  const [corriendo, setCorriendo] = useState(true);
  const [tiempo, setTiempo] = useState(0.0);
  const [fps, setFps] = useState(60);

  // Modo de restitución dimensional
  const [modoDimensional, setModoDimensional] = useState<"adimensional" | "fisico">("adimensional");
  const [escalaX, setEscalaX] = useState(0.1); // m (longitud característica)
  const [escalaT, setEscalaT] = useState(10.0); // s (tiempo de referencia)
  const [escalaC, setEscalaC] = useState(100.0); // mol/m³ (concentración característica)

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const estadoRef = useRef<{
    u: Float64Array;
    tiempo: number;
    corriendo: boolean;
    pe: number;
    da: number;
    fo: number;
    cinetica: TipoCinetica;
    modoDimensional: "adimensional" | "fisico";
    escalaX: number;
    escalaT: number;
    escalaC: number;
  }>({
    u: new Float64Array(80),
    tiempo: 0,
    corriendo: true,
    pe,
    da,
    fo,
    cinetica,
    modoDimensional,
    escalaX,
    escalaT,
    escalaC,
  });

  // Mantener referencias actualizadas para el bucle de animación a 60fps
  useEffect(() => {
    estadoRef.current.corriendo = corriendo;
    estadoRef.current.pe = pe;
    estadoRef.current.da = da;
    estadoRef.current.fo = fo;
    estadoRef.current.cinetica = cinetica;
    estadoRef.current.modoDimensional = modoDimensional;
    estadoRef.current.escalaX = escalaX;
    estadoRef.current.escalaT = escalaT;
    estadoRef.current.escalaC = escalaC;
  }, [corriendo, pe, da, fo, cinetica, modoDimensional, escalaX, escalaT, escalaC]);

  const Nx = 80;
  const dxi = 1.0 / (Nx - 1);

  // Inicializar perfil con una distribución suave
  const reiniciar = useCallback(() => {
    const u = new Float64Array(Nx);
    for (let i = 0; i < Nx; i++) {
      const xi = i * dxi;
      u[i] = Math.exp(-Math.pow((xi - 0.2) / 0.1, 2));
    }
    estadoRef.current.u = u;
    estadoRef.current.tiempo = 0.0;
    setTiempo(0.0);
  }, [dxi]);

  const inyectarPulso = useCallback(() => {
    const u = estadoRef.current.u;
    for (let i = 0; i < Nx; i++) {
      const xi = i * dxi;
      u[i] = Math.min(1.5, u[i] + 0.8 * Math.exp(-Math.pow((xi - 0.5) / 0.08, 2)));
    }
  }, [dxi]);

  const exportarCsv = useCallback(() => {
    const u = estadoRef.current.u;
    const esFisico = modoDimensional === "fisico";
    let csv = esFisico ? "posicion_m,concentracion_mol_m3,tiempo_s,xi_adim,theta_adim,tau_adim\n" : "xi,u_adim,tau\n";
    for (let i = 0; i < Nx; i++) {
      const xi = i * dxi;
      const valU = u[i];
      const tau = estadoRef.current.tiempo;
      if (esFisico) {
        const xFis = (xi * escalaX).toFixed(6);
        const cFis = (valU * escalaC).toFixed(6);
        const tFis = (tau * escalaT).toFixed(4);
        csv += `${xFis},${cFis},${tFis},${xi.toFixed(4)},${valU.toFixed(6)},${tau.toFixed(4)}\n`;
      } else {
        csv += `${xi.toFixed(4)},${valU.toFixed(6)},${tau.toFixed(4)}\n`;
      }
    }
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `simulacion_perfil_${esFisico ? "unidades_reales_" : ""}${nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "_")}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [dxi, nombreModelo, modoDimensional, escalaX, escalaT, escalaC]);

  const exportarJson = useCallback(() => {
    const u = Array.from(estadoRef.current.u);
    const xi = Array.from({ length: Nx }, (_, i) => i * dxi);
    const esFisico = modoDimensional === "fisico";
    const data = {
      modelo: nombreModelo,
      modo: modoDimensional,
      escalasFisicas: esFisico ? { x_ref_m: escalaX, t_ref_s: escalaT, c_ref_mol_m3: escalaC } : undefined,
      tau: Number(estadoRef.current.tiempo.toFixed(4)),
      tiempoReal_s: esFisico ? Number((estadoRef.current.tiempo * escalaT).toFixed(4)) : undefined,
      pe,
      da,
      fo,
      cinetica,
      perfil: xi.map((x, i) => ({
        xi: Number(x.toFixed(4)),
        u_adim: Number(u[i].toFixed(6)),
        ...(esFisico ? {
          x_m: Number((x * escalaX).toFixed(6)),
          c_mol_m3: Number((u[i] * escalaC).toFixed(6))
        } : {})
      })),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `simulacion_perfil_${esFisico ? "unidades_reales_" : ""}${nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "_")}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [dxi, pe, da, fo, cinetica, nombreModelo, modoDimensional, escalaX, escalaT, escalaC]);

  useEffect(() => {
    reiniciar();
  }, [reiniciar]);

  // Bucle de integración numérica y renderizado Canvas
  useEffect(() => {
    let animId: number;
    let ultimoTiempo = performance.now();
    let contadorFrames = 0;
    let temporizadorFps = performance.now();

    const pasoTiempo = () => {
      const ahora = performance.now();
      const dtReal = (ahora - ultimoTiempo) / 1000;
      ultimoTiempo = ahora;

      contadorFrames++;
      if (ahora - temporizadorFps >= 500) {
        setFps(Math.round((contadorFrames * 1000) / (ahora - temporizadorFps)));
        contadorFrames = 0;
        temporizadorFps = ahora;
      }

      const st = estadoRef.current;

      if (st.corriendo) {
        // Integrar varios micro-pasos para estabilidad CFL
        const dtSub = 0.0004;
        const subPasos = 15;

        for (let s = 0; s < subPasos; s++) {
          const u = st.u;
          const du = new Float64Array(Nx);

          for (let i = 1; i < Nx - 1; i++) {
            // Difusión central: Fo * d2u/dxi2
            const d2u = (u[i + 1] - 2.0 * u[i] + u[i - 1]) / (dxi * dxi);

            // Convección Upwind para robustez no oscilatoria: -Pe * du/dxi
            const du_dxi = (u[i] - u[i - 1]) / dxi;

            // Términos de reacción empírica constitutiva
            let reac = 0;
            switch (st.cinetica) {
              case "lineal":
                reac = -st.da * u[i];
                break;
              case "langmuir":
                reac = -(st.da * u[i]) / (1.0 + 2.0 * Math.max(0, u[i]));
                break;
              case "biestable":
                reac = st.da * u[i] * (1.0 - u[i] * u[i]);
                break;
              case "cuadratica":
                reac = -st.da * u[i] * Math.abs(u[i]);
                break;
            }

            du[i] = st.fo * d2u - st.pe * du_dxi + reac;
          }

          // Frontera entrada Dirichlet: u(0) = 1.0
          du[0] = 0;
          u[0] = 1.0;

          // Frontera salida Flujo nulo Neumann: du/dxi = 0
          du[Nx - 1] = du[Nx - 2];
          u[Nx - 1] = u[Nx - 2];

          // Actualización de Euler
          for (let i = 1; i < Nx - 1; i++) {
            u[i] += dtSub * du[i];
            if (isNaN(u[i])) u[i] = 0;
          }
          st.tiempo += dtSub;
        }

        setTiempo(st.tiempo);
      }

      // Dibujar en Canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const w = canvas.width;
          const h = canvas.height;
          const padL = 45;
          const padR = 20;
          const padT = 25;
          const padB = 35;

          ctx.clearRect(0, 0, w, h);

          // Fondo de la gráfica
          ctx.fillStyle = "#09090b";
          ctx.fillRect(0, 0, w, h);

          // Ejes y cuadrícula tenue
          ctx.strokeStyle = "#27272a";
          ctx.lineWidth = 1;

          const esFis = st.modoDimensional === "fisico";

          for (let gy = 0; gy <= 4; gy++) {
            const yPos = padT + (gy / 4) * (h - padT - padB);
            ctx.beginPath();
            ctx.moveTo(padL, yPos);
            ctx.lineTo(w - padR, yPos);
            ctx.stroke();

            // Etiqueta eje Y
            const valY = esFis
              ? (1.5 * (1 - gy / 4) * st.escalaC).toFixed(1)
              : (1.5 * (1 - gy / 4)).toFixed(2);
            ctx.fillStyle = "#71717a";
            ctx.font = "10px monospace";
            ctx.textAlign = "right";
            ctx.fillText(valY, padL - 8, yPos + 3);
          }

          for (let gx = 0; gx <= 5; gx++) {
            const xPos = padL + (gx / 5) * (w - padL - padR);
            ctx.beginPath();
            ctx.moveTo(xPos, padT);
            ctx.lineTo(xPos, h - padB);
            ctx.stroke();

            // Etiqueta eje X
            const valX = esFis
              ? ((gx / 5) * st.escalaX).toFixed(3)
              : (gx / 5).toFixed(1);
            ctx.fillStyle = "#71717a";
            ctx.font = "10px monospace";
            ctx.textAlign = "center";
            ctx.fillText(valX, xPos, h - padB + 16);
          }

          // Curva de la solución numérica continua
          const u = st.u;
          const plotW = w - padL - padR;
          const plotH = h - padT - padB;
          const maxY = 1.5;

          // Área bajo la curva con gradiente
          const grad = ctx.createLinearGradient(0, padT, 0, h - padB);
          grad.addColorStop(0, "rgba(16, 185, 129, 0.35)");
          grad.addColorStop(1, "rgba(16, 185, 129, 0.02)");

          ctx.beginPath();
          ctx.moveTo(padL, h - padB);
          for (let i = 0; i < Nx; i++) {
            const xi = i / (Nx - 1);
            const xPix = padL + xi * plotW;
            const yPix = h - padB - (Math.max(0, Math.min(u[i], maxY)) / maxY) * plotH;
            ctx.lineTo(xPix, yPix);
          }
          ctx.lineTo(w - padR, h - padB);
          ctx.closePath();
          ctx.fillStyle = grad;
          ctx.fill();

          // Trazo principal de la curva
          ctx.beginPath();
          for (let i = 0; i < Nx; i++) {
            const xi = i / (Nx - 1);
            const xPix = padL + xi * plotW;
            const yPix = h - padB - (Math.max(0, Math.min(u[i], maxY)) / maxY) * plotH;
            if (i === 0) ctx.moveTo(xPix, yPix);
            else ctx.lineTo(xPix, yPix);
          }
          ctx.strokeStyle = "#10b981";
          ctx.lineWidth = 2.5;
          ctx.stroke();

          // Etiquetas de los ejes
          ctx.fillStyle = "#a1a1aa";
          ctx.font = "11px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(
            esFis ? `Posición espacial física x [m] (L = ${st.escalaX} m)` : "Coordenada espacial adimensional (ξ)",
            padL + plotW / 2,
            h - 8
          );

          ctx.save();
          ctx.translate(14, padT + plotH / 2);
          ctx.rotate(-Math.PI / 2);
          ctx.fillText(
            esFis ? `Concentración c(x, t) [mol/m³]` : "Campo adimensional θ̂(ξ, τ)",
            0,
            0
          );
          ctx.restore();
        }
      }

      animId = requestAnimationFrame(pasoTiempo);
    };

    animId = requestAnimationFrame(pasoTiempo);
    return () => cancelAnimationFrame(animId);
  }, [Nx, dxi]);

  const pecletCelda = pe * dxi;

  return (
    <div className="adim-live-sim-container rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl my-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 font-mono">
            Laboratorio Numérico en Tiempo Real
          </span>
          <h3 className="text-lg font-medium text-zinc-100 flex items-center gap-2">
            Simulador Interactivo en Vivo de la EDP Adimensional (60 FPS)
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Resuelve numéricamente el Método de Líneas en tiempo real con reacción, advección y difusión acopladas.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Conmutador de modo de unidades */}
          <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800 text-xs">
            <button
              type="button"
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                modoDimensional === "adimensional"
                  ? "bg-emerald-600 text-white font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
              onClick={() => setModoDimensional("adimensional")}
            >
              📐 Adimensional (ξ, τ, θ)
            </button>
            <button
              type="button"
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                modoDimensional === "fisico"
                  ? "bg-cyan-600 text-white font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
              onClick={() => setModoDimensional("fisico")}
            >
              🧪 Unidades Reales (m, s, mol/m³)
            </button>
          </div>

          <span className="text-xs font-mono px-2.5 py-1 rounded bg-zinc-900 border border-zinc-700 text-zinc-300">
            {modoDimensional === "fisico" ? `t = ${(tiempo * escalaT).toFixed(2)} s` : `τ = ${tiempo.toFixed(2)}`}
          </span>
          <span className="text-xs font-mono px-2 py-1 rounded bg-zinc-900 border border-zinc-700 text-emerald-400">
            {fps} FPS
          </span>
        </div>
      </div>

      {/* Barra de configuración de escalas físicas (visible en modo físico) */}
      {modoDimensional === "fisico" && (
        <div className="bg-cyan-950/20 border border-cyan-800/40 rounded-lg p-3 mb-4 flex flex-wrap items-center justify-between gap-4 text-xs">
          <span className="text-cyan-300 font-medium">Factores de Escala de Restitución Física:</span>
          <div className="flex items-center gap-4 flex-wrap">
            <label className="flex items-center gap-1.5 text-zinc-300">
              <span>L (longitud):</span>
              <input
                type="number"
                step="0.01"
                min="0.001"
                value={escalaX}
                onChange={e => setEscalaX(Math.max(0.001, parseFloat(e.target.value) || 0.1))}
                className="w-16 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-100 font-mono"
              />
              <span className="text-zinc-400">m</span>
            </label>
            <label className="flex items-center gap-1.5 text-zinc-300">
              <span>t_ref (tiempo):</span>
              <input
                type="number"
                step="1"
                min="0.1"
                value={escalaT}
                onChange={e => setEscalaT(Math.max(0.1, parseFloat(e.target.value) || 10))}
                className="w-16 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-100 font-mono"
              />
              <span className="text-zinc-400">s</span>
            </label>
            <label className="flex items-center gap-1.5 text-zinc-300">
              <span>c_ref (concentración):</span>
              <input
                type="number"
                step="10"
                min="0.1"
                value={escalaC}
                onChange={e => setEscalaC(Math.max(0.1, parseFloat(e.target.value) || 100))}
                className="w-20 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-xs text-zinc-100 font-mono"
              />
              <span className="text-zinc-400">mol/m³</span>
            </label>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 items-start">
        {/* Gráfica Canvas interactiva */}
        <div>
          <div className="relative rounded-lg overflow-hidden border border-zinc-800 bg-zinc-950 shadow-inner">
            <canvas
              ref={canvasRef}
              width={640}
              height={320}
              className="w-full h-auto block"
            />
          </div>

          {/* Botones de control del simulador */}
          <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all shadow-md ${
                  corriendo
                    ? "bg-amber-600 hover:bg-amber-500 text-white"
                    : "bg-emerald-600 hover:bg-emerald-500 text-white"
                }`}
                onClick={() => setCorriendo(!corriendo)}
              >
                {corriendo ? "⏸ Pausar" : "▶ Reanudar"}
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700"
                onClick={reiniciar}
              >
                🔄 Reiniciar
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-sky-300 border border-sky-800/60"
                onClick={inyectarPulso}
                title="Inyecta una perturbación gaussiana local en el centro del dominio"
              >
                ⚡ Inyectar Perturbación
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700"
                onClick={exportarCsv}
                title="Exportar perfil numérico actual en CSV"
              >
                📥 CSV
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-700"
                onClick={exportarJson}
                title="Exportar estado de simulación en JSON"
              >
                📊 JSON
              </button>
            </div>

            <div className="text-xs text-zinc-400 flex items-center gap-2">
              <span>Péclet de celda:</span>
              <span
                className={`font-mono font-semibold ${
                  pecletCelda > 2.0 ? "text-amber-400" : "text-emerald-400"
                }`}
              >
                {pecletCelda.toFixed(2)} {pecletCelda <= 2.0 ? "✓ (estable)" : "⚠ (convectivo)"}
              </span>
            </div>
          </div>
        </div>

        {/* Panel de sliders de invariantes adimensionales en vivo */}
        <div className="space-y-4 bg-zinc-900/60 p-5 rounded-lg border border-zinc-800/80">
          <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider border-b border-zinc-800 pb-2">
            Controles de Invariantes Adimensionales
          </h4>

          {/* Slider Péclet */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-300 font-medium">Péclet (Pe) · Convección</span>
              <span className="font-mono text-emerald-400 font-bold">{pe.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="0.5"
              value={pe}
              onChange={e => setPe(Number(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500">Transporte advectivo hacia la derecha.</p>
          </div>

          {/* Slider Damköhler */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-300 font-medium">Damköhler (Da) · Reactividad</span>
              <span className="font-mono text-emerald-400 font-bold">{da.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="8"
              step="0.2"
              value={da}
              onChange={e => setDa(Number(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500">Tasa de consumo o producción cinética.</p>
          </div>

          {/* Slider Fourier */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-300 font-medium">Fourier (Fo) · Difusión</span>
              <span className="font-mono text-emerald-400 font-bold">{fo.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="2.5"
              step="0.05"
              value={fo}
              onChange={e => setFo(Number(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500">Dispersión y homogeneización molecular.</p>
          </div>

          {/* Selector de Ley Constitutiva Empírica */}
          <div className="space-y-1 pt-2 border-t border-zinc-800">
            <label className="text-xs text-zinc-300 font-medium block">
              Ley Constitutiva / Cinética Empírica:
            </label>
            <select
              value={cinetica}
              onChange={e => setCinetica(e.target.value as TipoCinetica)}
              className="w-full text-xs rounded bg-zinc-950 border border-zinc-700 text-zinc-200 p-2"
            >
              <option value="langmuir">Saturación Langmuir / Michaelis-Menten: -Da·θ/(1+2θ)</option>
              <option value="lineal">Consumo Lineal de 1er Orden: -Da·θ</option>
              <option value="biestable">Campo de Fase Biestable Cúbico: Da·θ(1 - θ²)</option>
              <option value="cuadratica">Amortiguamiento Cuadrático: -Da·θ|θ|</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
