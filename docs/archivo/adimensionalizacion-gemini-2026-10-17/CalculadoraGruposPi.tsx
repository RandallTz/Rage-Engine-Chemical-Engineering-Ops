"use client";

import { useId, useMemo, useState } from "react";
import type { Expresion } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";

function evaluarExpresionNumerica(expr: Expresion, valores: Record<string, number>): number {
  switch (expr.tipo) {
    case "numero":
      return expr.valor;
    case "simbolo":
      return valores[expr.id] ?? 1.0;
    case "suma":
      return expr.argumentos.reduce((acc, a) => acc + evaluarExpresionNumerica(a, valores), 0);
    case "producto":
      return expr.argumentos.reduce((acc, a) => acc * evaluarExpresionNumerica(a, valores), 1);
    case "cociente": {
      const num = evaluarExpresionNumerica(expr.numerador, valores);
      const den = evaluarExpresionNumerica(expr.denominador, valores);
      return Math.abs(den) > 1e-15 ? num / den : num / 1e-15;
    }
    case "potencia": {
      const b = evaluarExpresionNumerica(expr.base, valores);
      const e = evaluarExpresionNumerica(expr.exponente, valores);
      return Math.pow(Math.max(b, 1e-15), e);
    }
    case "funcion": {
      const arg = expr.argumentos[0] ? evaluarExpresionNumerica(expr.argumentos[0], valores) : 0;
      switch (expr.nombre) {
        case "exp": return Math.exp(arg);
        case "log": return Math.log(Math.max(arg, 1e-15));
        case "abs": return Math.abs(arg);
        case "tanh": return Math.tanh(arg);
        default: return arg;
      }
    }
    default:
      return 1.0;
  }
}

function extraerSimbolos(expr: Expresion): Set<string> {
  const simbolos = new Set<string>();
  function recorrer(e: Expresion) {
    if (e.tipo === "simbolo") {
      simbolos.add(e.id);
      return;
    }
    if (e.tipo === "suma" || e.tipo === "producto") {
      for (const arg of e.argumentos) recorrer(arg);
      return;
    }
    if (e.tipo === "cociente") {
      recorrer(e.numerador);
      recorrer(e.denominador);
      return;
    }
    if (e.tipo === "potencia") {
      recorrer(e.base);
      recorrer(e.exponente);
      return;
    }
    if (e.tipo === "funcion" || e.tipo === "llamada") {
      for (const arg of e.argumentos) recorrer(arg);
      return;
    }
  }
  recorrer(expr);
  return simbolos;
}

export interface SustanciaTransporte {
  nombre: string;
  formula: string;
  fase: "Líquido" | "Gas";
  rho: number; // kg/m3
  mu: number; // Pa.s
  D: number; // m2/s
  Cp: number; // J/(kg.K)
  kTerm: number; // W/(m.K)
  descripcion: string;
}

export const CATALOGO_SUSTANCIAS: Record<string, SustanciaTransporte> = {
  agua: {
    nombre: "Agua líquida (25 °C)",
    formula: "H₂O",
    fase: "Líquido",
    rho: 997.0,
    mu: 8.91e-4,
    D: 1.5e-9,
    Cp: 4184.0,
    kTerm: 0.606,
    descripcion: "Solvente polar de referencia en destilación y reactores acuosos."
  },
  etanol: {
    nombre: "Etanol puro (25 °C)",
    formula: "C₂H₅OH",
    fase: "Líquido",
    rho: 789.0,
    mu: 1.07e-3,
    D: 1.2e-9,
    Cp: 2440.0,
    kTerm: 0.167,
    descripcion: "Compuesto clave en mezclas de destilación reactiva multicomponente."
  },
  acetona: {
    nombre: "Acetona pura (25 °C)",
    formula: "C₃H₆O",
    fase: "Líquido",
    rho: 784.0,
    mu: 3.06e-4,
    D: 1.8e-9,
    Cp: 2150.0,
    kTerm: 0.180,
    descripcion: "Disolvente orgánico volátil de baja viscosidad y rápida difusión."
  },
  tolueno: {
    nombre: "Tolueno puro (25 °C)",
    formula: "C₇H₈",
    fase: "Líquido",
    rho: 867.0,
    mu: 5.60e-4,
    D: 1.6e-9,
    Cp: 1700.0,
    kTerm: 0.131,
    descripcion: "Hidrocarburo aromático no polar para destilación azeotrópica."
  },
  aire: {
    nombre: "Aire seco (25 °C, 1 atm)",
    formula: "N₂ / O₂",
    fase: "Gas",
    rho: 1.184,
    mu: 1.85e-5,
    D: 2.1e-5,
    Cp: 1005.0,
    kTerm: 0.026,
    descripcion: "Fase gaseosa con difusión molecular rápida y número de Lewis ~ 1."
  }
};

const PRESETS_FISICOS: Record<string, { nombre: string; valores: Record<string, number> }> = {
  liquido_reactivo: {
    nombre: "Líquido Reactivo Convencional (D ~ 10⁻⁹ m²/s)",
    valores: {
      D: 1e-9, D_A: 1e-9, D_B: 8e-10, D_C: 6e-10,
      k: 0.1, k1: 0.2, k2: 0.05,
      u: 0.01, v: 0.005,
      x_ref: 0.05, y_ref: 0.01, z_ref: 0.01,
      t_ref: 10.0,
      cA: 100.0, cB: 100.0, c_A: 100.0, c_B: 100.0,
      L: 0.05
    }
  },
  gas_rapido: {
    nombre: "Fase Gas con Reacción Rápida (D ~ 10⁻⁵ m²/s)",
    valores: {
      D: 1e-5, D_A: 1e-5, D_B: 1.2e-5, D_C: 9e-6,
      k: 50.0, k1: 100.0, k2: 10.0,
      u: 1.5, v: 0.2,
      x_ref: 0.2, y_ref: 0.02, z_ref: 0.02,
      t_ref: 0.1,
      cA: 40.0, cB: 40.0, c_A: 40.0, c_B: 40.0,
      L: 0.2
    }
  },
  difusion_pura: {
    nombre: "Catálisis / Membrana (Advección Nula)",
    valores: {
      D: 5e-10, D_A: 5e-10, D_B: 4e-10, D_C: 3e-10,
      k: 0.5, k1: 1.0, k2: 0.1,
      u: 0.0, v: 0.0,
      x_ref: 0.002, y_ref: 0.002, z_ref: 0.002,
      t_ref: 8.0,
      cA: 500.0, cB: 500.0, c_A: 500.0, c_B: 500.0,
      L: 0.002
    }
  }
};

export default function CalculadoraGruposPi({ f }: { f: FormulacionNucleo }) {
  const baseId = useId();
  const grupos = f.grupos ?? [];

  const parametrosDetectados = useMemo(() => {
    const s = new Set<string>();
    for (const g of grupos) {
      const extraidos = extraerSimbolos(g.definicion);
      for (const id of extraidos) s.add(id);
    }
    return Array.from(s).sort();
  }, [grupos]);

  const [valores, setValores] = useState<Record<string, number>>(() => {
    const inicial: Record<string, number> = {};
    const defaults = PRESETS_FISICOS.liquido_reactivo.valores;
    for (const p of parametrosDetectados) {
      inicial[p] = defaults[p] ?? 1.0;
    }
    return inicial;
  });

  const [sustanciaActiva, setSustanciaActiva] = useState<keyof typeof CATALOGO_SUSTANCIAS | "personalizado">("agua");
  const [longitudL, setLongitudL] = useState(0.05);
  const [velocidadU, setVelocidadU] = useState(0.02);
  const [celdas, setCeldas] = useState(40);

  function cambiarValor(p: string, strVal: string) {
    const num = parseFloat(strVal);
    setValores(prev => ({
      ...prev,
      [p]: isNaN(num) ? 0 : num
    }));
  }

  function aplicarSustancia(clave: keyof typeof CATALOGO_SUSTANCIAS) {
    setSustanciaActiva(clave);
    const s = CATALOGO_SUSTANCIAS[clave];
    setValores(prev => {
      const nuevo = { ...prev };
      if ("D" in nuevo || parametrosDetectados.includes("D")) nuevo["D"] = s.D;
      if ("D_A" in nuevo || parametrosDetectados.includes("D_A")) nuevo["D_A"] = s.D;
      if ("D_B" in nuevo || parametrosDetectados.includes("D_B")) nuevo["D_B"] = s.D * 0.9;
      if ("D_C" in nuevo || parametrosDetectados.includes("D_C")) nuevo["D_C"] = s.D * 0.8;
      if ("u" in nuevo || parametrosDetectados.includes("u")) nuevo["u"] = velocidadU;
      if ("L" in nuevo || parametrosDetectados.includes("L")) nuevo["L"] = longitudL;
      if ("x_ref" in nuevo || parametrosDetectados.includes("x_ref")) nuevo["x_ref"] = longitudL;
      return nuevo;
    });
  }

  function aplicarPreset(clave: keyof typeof PRESETS_FISICOS) {
    setSustanciaActiva("personalizado");
    const preset = PRESETS_FISICOS[clave].valores;
    setValores(prev => {
      const nuevo = { ...prev };
      for (const p of parametrosDetectados) {
        if (preset[p] !== undefined) {
          nuevo[p] = preset[p];
        }
      }
      return nuevo;
    });
  }

  // Grupos adimensionales de transporte físico
  const gruposTransporte = useMemo(() => {
    const s = sustanciaActiva !== "personalizado"
      ? CATALOGO_SUSTANCIAS[sustanciaActiva]
      : { rho: 997.0, mu: 8.91e-4, D: valores["D"] ?? 1e-9, Cp: 4184.0, kTerm: 0.606 };

    const L = longitudL > 0 ? longitudL : 0.05;
    const u = velocidadU >= 0 ? velocidadU : 0.01;
    const rho = s.rho;
    const mu = s.mu;
    const D = valores["D"] ?? s.D;
    const Cp = s.Cp;
    const kTerm = s.kTerm;

    const Re = (rho * u * L) / Math.max(mu, 1e-15);
    const Sc = mu / Math.max(rho * D, 1e-15);
    const Pr = (Cp * mu) / Math.max(kTerm, 1e-15);
    const Le = Sc / Math.max(Pr, 1e-15);
    const Pem = (u * L) / Math.max(D, 1e-15);
    const Peh = (rho * Cp * u * L) / Math.max(kTerm, 1e-15);

    return {
      Re,
      Sc,
      Pr,
      Le,
      Pem,
      Peh,
      esLaminar: Re < 2100,
      esTurbulento: Re > 4000
    };
  }, [sustanciaActiva, longitudL, velocidadU, valores]);

  // Evaluación dinámica de los grupos
  const gruposEvaluados = useMemo(() => {
    return grupos.map(g => {
      const val = evaluarExpresionNumerica(g.definicion, valores);
      return {
        id: g.id,
        definicion: g.definicion,
        valor: val,
        esValido: Number.isFinite(val) && !isNaN(val)
      };
    });
  }, [grupos, valores]);

  // Estimadores de estabilidad y acondicionamiento
  const metricasNumericas = useMemo(() => {
    const vals = gruposEvaluados.map(g => g.valor).filter(v => Number.isFinite(v) && v > 0);
    const maxVal = vals.length > 0 ? Math.max(...vals) : 1;
    const minVal = vals.length > 0 ? Math.min(...vals) : 1;
    const rigidez = maxVal / Math.max(minVal, 1e-12);

    // Búsqueda de Pe y Da
    const peGrupo = gruposEvaluados.find(g => /pe|cfl/i.test(g.id))?.valor ?? (valores["u"] && valores["x_ref"] && valores["D"] ? (valores["u"] * valores["x_ref"]) / valores["D"] : 1.0);
    const daGrupo = gruposEvaluados.find(g => /da|k/i.test(g.id))?.valor ?? (valores["k"] && valores["t_ref"] ? valores["k"] * valores["t_ref"] : 1.0);

    const deltaXi = 1.0 / Math.max(celdas, 1);
    const peCelda = peGrupo * deltaXi;

    return {
      rigidez,
      peGrupo,
      daGrupo,
      peCelda,
      deltaXi,
      esStiff: rigidez > 1e3,
      oscilacionGibbs: peCelda > 2.0
    };
  }, [gruposEvaluados, valores, celdas]);

  return (
    <div className="adim-group-pill p-5 mt-6 border border-zinc-700 bg-zinc-950/80 rounded-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <h4 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <span>🧮</span>
            <span>Calculadora Numérica de Grupos Π & Diagnóstico del Solver</span>
          </h4>
          <p className="text-xs text-zinc-400 mt-0.5">
            Ingresa magnitudes físicas para evaluar los invariantes de similitud y diagnosticar la estabilidad en el motor de multifísica.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Preajustes Genéricos:</span>
          {Object.entries(PRESETS_FISICOS).map(([k, p]) => (
            <button
              key={k}
              type="button"
              className="adim-button text-xs py-1 px-2.5"
              onClick={() => aplicarPreset(k as keyof typeof PRESETS_FISICOS)}
              title={p.nombre}
            >
              {k === "liquido_reactivo" ? "💧 Líquido" : k === "gas_rapido" ? "💨 Gas Rápido" : "🔬 Membrana"}
            </button>
          ))}
        </div>
      </div>

      {/* Catálogo de Sustancias Reales de Ingeniería */}
      <div className="border border-zinc-800 bg-zinc-900/50 p-4 rounded-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h5 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <span>🧪</span>
              <span>Catálogo de Sustancias Reales (/motor)</span>
            </h5>
            <p className="text-[11px] text-zinc-400">
              Selecciona una sustancia pura para inferir automáticamente propiedades de transporte y evaluar invariantes físicos.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {Object.entries(CATALOGO_SUSTANCIAS).map(([k, s]) => {
              const estaActiva = sustanciaActiva === k;
              return (
                <button
                  key={k}
                  type="button"
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    estaActiva
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-700 shadow-sm"
                      : "bg-zinc-900 text-zinc-400 border border-zinc-800 hover:text-zinc-200 hover:bg-zinc-800"
                  }`}
                  onClick={() => aplicarSustancia(k as keyof typeof CATALOGO_SUSTANCIAS)}
                >
                  <span>{s.nombre.split(" ")[0]}</span>
                  <span className="text-[10px] opacity-75 font-mono">({s.formula})</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Inputs físicos complementarios: L y u */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-zinc-800/80 text-xs">
          <div className="flex items-center justify-between bg-zinc-950 p-2 rounded-lg border border-zinc-800">
            <span className="text-zinc-400">Longitud <FormulaLatex latex="L" lectura="L" />:</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                step="0.005"
                min="0.001"
                value={longitudL}
                onChange={e => {
                  const val = parseFloat(e.target.value) || 0.01;
                  setLongitudL(val);
                  setValores(prev => ({ ...prev, L: val, x_ref: val }));
                }}
                className="w-16 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-right font-mono text-xs text-zinc-100"
              />
              <span className="text-zinc-500 font-mono">m</span>
            </div>
          </div>

          <div className="flex items-center justify-between bg-zinc-950 p-2 rounded-lg border border-zinc-800">
            <span className="text-zinc-400">Velocidad <FormulaLatex latex="u" lectura="u" />:</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                step="0.005"
                min="0"
                value={velocidadU}
                onChange={e => {
                  const val = parseFloat(e.target.value) || 0;
                  setVelocidadU(val);
                  setValores(prev => ({ ...prev, u: val }));
                }}
                className="w-16 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-right font-mono text-xs text-zinc-100"
              />
              <span className="text-zinc-500 font-mono">m/s</span>
            </div>
          </div>

          <div className="flex items-center justify-between bg-zinc-950 p-2 rounded-lg border border-zinc-800">
            <span className="text-zinc-400">Densidad <FormulaLatex latex="\rho" lectura="rho" />:</span>
            <span className="font-mono text-zinc-200">
              {sustanciaActiva !== "personalizado" ? CATALOGO_SUSTANCIAS[sustanciaActiva].rho : 997} kg/m³
            </span>
          </div>

          <div className="flex items-center justify-between bg-zinc-950 p-2 rounded-lg border border-zinc-800">
            <span className="text-zinc-400">Viscosidad <FormulaLatex latex="\mu" lectura="mu" />:</span>
            <span className="font-mono text-zinc-200">
              {sustanciaActiva !== "personalizado" ? CATALOGO_SUSTANCIAS[sustanciaActiva].mu.toExponential(2) : "8.9e-4"} Pa·s
            </span>
          </div>
        </div>

        {/* Tarjetas de Números Adimensionales de Transporte */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-2">
          {/* Reynolds */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400 flex items-center justify-center gap-1">
              <FormulaLatex latex="\mathrm{Re}" lectura="Reynolds" />
              <span className={`text-[9px] px-1 rounded ${gruposTransporte.esLaminar ? "bg-emerald-950 text-emerald-400" : "bg-amber-950 text-amber-400"}`}>
                {gruposTransporte.esLaminar ? "Laminar" : "Turbulento"}
              </span>
            </div>
            <div className="text-sm font-bold font-mono text-emerald-300 my-1">
              {gruposTransporte.Re.toFixed(1)}
            </div>
            <div className="text-[9px] text-zinc-500">Inercia / Viscosidad</div>
          </div>

          {/* Schmidt */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400">
              <FormulaLatex latex="\mathrm{Sc}" lectura="Schmidt" />
            </div>
            <div className="text-sm font-bold font-mono text-cyan-300 my-1">
              {gruposTransporte.Sc.toFixed(1)}
            </div>
            <div className="text-[9px] text-zinc-500">Viscosa / Masa</div>
          </div>

          {/* Prandtl */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400">
              <FormulaLatex latex="\mathrm{Pr}" lectura="Prandtl" />
            </div>
            <div className="text-sm font-bold font-mono text-cyan-300 my-1">
              {gruposTransporte.Pr.toFixed(2)}
            </div>
            <div className="text-[9px] text-zinc-500">Viscosa / Calor</div>
          </div>

          {/* Lewis */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400">
              <FormulaLatex latex="\mathrm{Le}" lectura="Lewis" />
            </div>
            <div className="text-sm font-bold font-mono text-amber-300 my-1">
              {gruposTransporte.Le.toFixed(1)}
            </div>
            <div className="text-[9px] text-zinc-500">Térmica / Masa</div>
          </div>

          {/* Péclet Masa */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400">
              <FormulaLatex latex="\mathrm{Pe}_m" lectura="Peclet de masa" />
            </div>
            <div className="text-sm font-bold font-mono text-purple-300 my-1">
              {gruposTransporte.Pem >= 1e4 ? gruposTransporte.Pem.toExponential(2) : gruposTransporte.Pem.toFixed(0)}
            </div>
            <div className="text-[9px] text-zinc-500">Advección / Difusión</div>
          </div>

          {/* Péclet Térmico */}
          <div className="bg-zinc-950/90 border border-zinc-800 p-2.5 rounded-lg text-center flex flex-col justify-between">
            <div className="text-[11px] font-semibold text-zinc-400">
              <FormulaLatex latex="\mathrm{Pe}_h" lectura="Peclet termico" />
            </div>
            <div className="text-sm font-bold font-mono text-purple-300 my-1">
              {gruposTransporte.Peh >= 1e4 ? gruposTransporte.Peh.toExponential(2) : gruposTransporte.Peh.toFixed(0)}
            </div>
            <div className="text-[9px] text-zinc-500">Convección / Calor</div>
          </div>
        </div>
      </div>

      {/* Grid de Parámetros Físicos */}
      <div>
        <h5 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">
          Parámetros Físicos del Modelo ({parametrosDetectados.length})
        </h5>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {parametrosDetectados.map(p => (
            <div key={p} className="bg-zinc-900 border border-zinc-800 p-2.5 rounded-lg flex flex-col justify-between">
              <label htmlFor={`${baseId}-param-${p}`} className="text-xs font-mono font-medium text-zinc-300 block mb-1">
                {p}
              </label>
              <input
                id={`${baseId}-param-${p}`}
                type="number"
                step="any"
                value={valores[p] ?? 1.0}
                onChange={e => cambiarValor(p, e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-100 font-mono focus:border-cyan-500 focus:outline-none"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Grid de Grupos Evaluados */}
      <div>
        <h5 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">
          Invariantes Adimensionales Calculados
        </h5>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {gruposEvaluados.map(g => {
            const valFormateado = Math.abs(g.valor) >= 1e4 || (Math.abs(g.valor) <= 1e-3 && g.valor !== 0)
              ? g.valor.toExponential(3)
              : g.valor.toFixed(4);

            return (
              <div key={g.id} className="bg-zinc-900/90 border border-zinc-800 p-3 rounded-lg flex flex-col justify-between">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-semibold text-cyan-300">{g.id}</span>
                  <span className="text-[10px] text-zinc-400 font-mono">
                    {g.valor > 100 ? "Dominante" : g.valor < 0.01 ? "Atenuado" : "Orden O(1)"}
                  </span>
                </div>
                <div className="my-1.5 overflow-x-auto text-xs text-zinc-300">
                  <FormulaLatex latex={`${nombreLatex(g.id)} = ${latexExpresion(g.definicion)}`} lectura={g.id} />
                </div>
                <div className="mt-2 pt-2 border-t border-zinc-800 flex items-baseline justify-between font-mono">
                  <span className="text-xs text-zinc-500">Valor numérico:</span>
                  <span className="text-sm font-semibold text-amber-300">{valFormateado}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Diagnóstico Numérico y Estabilidad para /motor */}
      <div className="border border-zinc-800 bg-zinc-900/60 p-4 rounded-xl space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h5 className="text-xs font-semibold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
            <span>🛡️</span>
            <span>Diagnóstico de Estabilidad para el Motor de Multifísica</span>
          </h5>
          <div className="flex items-center gap-2 text-xs text-zinc-300 font-mono">
            <label htmlFor={`${baseId}-celdas-malla`}>Malla espacial $N$ (celdas):</label>
            <input
              id={`${baseId}-celdas-malla`}
              type="number"
              min={4}
              max={200}
              value={celdas}
              onChange={e => setCeldas(Math.max(4, parseInt(e.target.value) || 4))}
              className="w-16 bg-zinc-950 border border-zinc-700 rounded px-1.5 py-0.5 text-center text-xs text-zinc-100"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Tarjeta Rigidez */}
          <div className={`p-3 rounded-lg border text-xs ${metricasNumericas.esStiff ? "bg-amber-950/20 border-amber-800/60 text-amber-200" : "bg-emerald-950/20 border-emerald-800/60 text-emerald-200"}`}>
            <div className="font-semibold flex items-center justify-between mb-1">
              <span className="flex items-center gap-1">Rigidez Asintótica <FormulaLatex latex="\mathcal{S}" lectura="Rigidez" /></span>
              <span>{metricasNumericas.rigidez.toExponential(2)}</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              {metricasNumericas.esStiff
                ? "Sistema muy rígido. RK45 adaptativo sufrirá rechazo de pasos. Se recomienda integrador BDF2 / Euler implícito."
                : "Rigidez moderada. El integrador RK45 adaptativo operará con alta eficiencia computacional."}
            </p>
          </div>

          {/* Tarjeta Péclet Celda */}
          <div className={`p-3 rounded-lg border text-xs ${metricasNumericas.oscilacionGibbs ? "bg-rose-950/20 border-rose-800/60 text-rose-200" : "bg-emerald-950/20 border-emerald-800/60 text-emerald-200"}`}>
            <div className="font-semibold flex items-center justify-between mb-1">
              <span className="flex items-center gap-1">Péclet de Celda <FormulaLatex latex="\mathrm{Pe}_{\Delta\xi}" lectura="Péclet de celda" /></span>
              <span>{metricasNumericas.peCelda.toFixed(2)}</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              {metricasNumericas.oscilacionGibbs
                ? `Alerta: Pe_celda > 2.0. Las diferencias centradas generarán oscilaciones espurias. Aumente celdas a N ≥ ${Math.ceil(metricasNumericas.peGrupo / 2)} o use Upwind.`
                : "Condición de Péclet satisfecha (Pe_celda ≤ 2.0). El frente difusivo se resolverá sin oscilaciones numéricas de Gibbs."}
            </p>
          </div>

          {/* Tarjeta Régimen Kruskal Activo */}
          <div className="p-3 rounded-lg border border-cyan-800/60 bg-cyan-950/20 text-cyan-200 text-xs">
            <div className="font-semibold flex items-center justify-between mb-1">
              <span>Régimen Físico Rector</span>
              <span>
                {metricasNumericas.peGrupo > 10 && metricasNumericas.daGrupo > 10
                  ? "Zona II (Frente)"
                  : metricasNumericas.peGrupo > 10
                  ? "Zona I (Convección)"
                  : metricasNumericas.daGrupo > 10
                  ? "Zona III (Dif-Reac)"
                  : "Zona IV (Mezcla)"}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed">
              {metricasNumericas.peGrupo > 10 && metricasNumericas.daGrupo > 10
                ? "Ondas reactivas de alta velocidad gobernadas por acoplamiento convectivo-químico."
                : metricasNumericas.peGrupo > 10
                ? "Transporte hiperbólico dominante. La difusión es una perturbación singular O(1/Pe)."
                : metricasNumericas.daGrupo > 10
                ? "Cinética rápida limitada por difusión molecular interna."
                : "Medio cuasi-homogéneo. Gradientes espaciales disipados rápidamente."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
