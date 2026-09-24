"use client";

import { createContext, useContext } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { desdeSI, molARepresentacionMasica, type Unidades } from "./unidades";
import {
  DatosCorriente,
  DatosOperacion,
  puertosDe,
  ecuacionReaccion,
  variablesDeCorriente,
  variablesDeOperacion,
  etiquetaVariable,
  estadoDe,
  valorDe,
  formatear,
  UNIDAD,
} from "./modelo";

export type Modo = "editar" | "resultados";

interface ContextoValores {
  componentes: string[];
  dados: Record<string, string>;
  pool: Record<string, number>;
  modo: Modo;
  clavesIncoherentes: Set<string>;
  unidades: Unidades | null;
  /** MW [g/mol] por corriente, del backend, para mostrar caudales en masa. */
  masasMolares: Record<string, number>;
}

export const ValoresContext = createContext<ContextoValores>({
  componentes: [],
  dados: {},
  pool: {},
  modo: "editar",
  clavesIncoherentes: new Set(),
  unidades: null,
  masasMolares: {},
});

/**
 * El enfasis depende del modo, y es justo lo que el usuario pidio:
 *  - editar    -> destaca lo que FALTA por introducir; lo ya calculado
 *                 se atenua (es contexto, no la tarea de ahora).
 *  - resultados-> destaca lo CALCULADO (la informacion nueva); lo que
 *                 diste se atenua porque ya lo conocias.
 */
function claseValor(estado: string, modo: Modo, incoherente: boolean): string {
  if (incoherente) return "text-red-400 font-semibold";
  if (modo === "editar") {
    if (estado === "desconocido") return "text-amber-400";
    if (estado === "dado") return "text-emerald-300";
    return "text-zinc-600";
  }
  if (estado === "calculado") return "text-sky-300 font-semibold";
  if (estado === "dado") return "text-zinc-500";
  return "text-amber-400";
}

function FilaVariable({ nodoId, variable, componentes }: { nodoId: string; variable: string; componentes: string[] }) {
  const { dados, pool, modo, clavesIncoherentes, unidades, masasMolares } = useContext(ValoresContext);
  const clave = `${nodoId}.${variable}`;
  const estado = estadoDe(clave, dados, pool);
  const incoherente = clavesIncoherentes.has(clave);
  const unidad = unidades?.unidadDe(clave) ?? null;

  // Lo que escribio el usuario ya esta en la unidad elegida; lo del pool
  // llega en SI y hay que convertirlo. Un caudal pedido en masa se
  // convierte con la MW de la mezcla de ESA corriente.
  const crudo = valorDe(clave, dados, pool);
  const mw = masasMolares[nodoId];
  const masica = variable === "F" && unidad?.magnitud === "flujo_masico";
  let valor: number | null = null;
  if (crudo !== null) {
    if (estado === "dado") valor = crudo;
    else if (masica) valor = mw ? molARepresentacionMasica(crudo, mw, unidad!) : null;
    else valor = desdeSI(crudo, unidad);
  }
  const simbolo = unidades?.etiquetaDe(clave) || UNIDAD[variable];

  return (
    <div className="flex items-baseline justify-between gap-2 leading-tight">
      <span className={`text-[10px] ${modo === "editar" && estado === "desconocido" ? "text-amber-500/80" : "text-zinc-500"}`}>
        {etiquetaVariable(variable, componentes)}
      </span>
      <span className={`font-mono text-[10px] ${claseValor(estado, modo, incoherente)}`}>
        {valor === null ? (modo === "editar" ? "falta" : "?") : formatear(valor, variable)}
        {valor !== null && simbolo ? <span className="text-zinc-600"> {simbolo}</span> : null}
        {incoherente && <span className="ml-1">⚠</span>}
      </span>
    </div>
  );
}

export function NodoCorriente({ id, selected }: NodeProps & { data: DatosCorriente }) {
  const { componentes, modo, clavesIncoherentes } = useContext(ValoresContext);
  const variables = variablesDeCorriente(componentes.length);
  const tieneProblema = variables.some((v) => clavesIncoherentes.has(`${id}.${v}`));

  return (
    <div
      className={`w-[170px] rounded border-2 bg-zinc-900 shadow-lg ${
        tieneProblema ? "border-red-500" : selected ? "border-emerald-400" : "border-zinc-600"
      }`}
    >
      <Handle type="target" position={Position.Left} style={{ background: "#71717a", width: 8, height: 8 }} />
      <div className="border-b border-zinc-800 px-2 py-1">
        <div className="text-xs font-semibold text-zinc-100">{id}</div>
        <div className="text-[9px] uppercase tracking-wide text-zinc-500">corriente</div>
      </div>
      <div className="space-y-0.5 px-2 py-1.5">
        {variables.map((v) => (
          <FilaVariable key={v} nodoId={id} variable={v} componentes={componentes} />
        ))}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: "#71717a", width: 8, height: 8 }} />
    </div>
  );
}

const ESTILO_OPERACION: Record<string, string> = {
  columna: "border-blue-500 bg-blue-950",
  mezclador: "border-emerald-500 bg-emerald-950",
  divisor: "border-purple-500 bg-purple-950",
  bomba: "border-amber-500 bg-amber-950",
};

// Los puertos se llaman como los espera el backend, pero se muestran
// abreviados: "alimentacion" no cabe en el nodo sin recortarse.
const ABREVIATURA_PUERTO: Record<string, string> = {
  alimentacion: "alim",
  destilado: "dest",
  fondos: "fondos",
  entrada_1: "ent 1",
  entrada_2: "ent 2",
  salida_1: "sal 1",
  salida_2: "sal 2",
};

export function NodoOperacion({ id, data, selected }: NodeProps & { data: DatosOperacion }) {
  const { componentes, clavesIncoherentes } = useContext(ValoresContext);
  const puertos = puertosDe(data);
  const variables = variablesDeOperacion(data);
  const tieneProblema = variables.some((v) => clavesIncoherentes.has(`${id}.${v}`));

  return (
    <div
      className={`w-[200px] rounded-md border-2 shadow-lg ${ESTILO_OPERACION[data.tipo]} ${
        tieneProblema ? "!border-red-500" : ""
      } ${selected ? "ring-2 ring-emerald-400" : ""}`}
    >
      <div className="border-b border-white/10 px-2.5 py-1.5">
        <div className="text-sm font-semibold text-zinc-100">{id}</div>
        <div className="text-[9px] uppercase tracking-wide text-zinc-400">
          {data.tipo}
          {data.metodo ? ` · ${data.metodo}` : ""}
        </div>
        {/* La reaccion, sobre el propio reactor: en un diagrama de
            proceso lo primero que se quiere saber de un reactor es QUE
            reaccion ocurre dentro, y antes habia que abrir el panel y
            descifrar una cadena de coeficientes para averiguarlo. */}
        {data.tipo === "reactor_cstr" && (
          <div className="mt-1 rounded bg-black/40 px-1.5 py-0.5 text-center font-mono text-[9px] leading-tight">
            {ecuacionReaccion(data.nu, componentes) ? (
              <span className="text-emerald-300">{ecuacionReaccion(data.nu, componentes)}</span>
            ) : (
              <span className="text-amber-500">sin reacción definida</span>
            )}
          </div>
        )}
      </div>

      {variables.length > 0 && (
        <div className="space-y-0.5 border-b border-white/10 px-2.5 py-1.5">
          {variables.map((v) => (
            <FilaVariable key={v} nodoId={id} variable={v} componentes={componentes} />
          ))}
        </div>
      )}

      <div className="relative px-2.5 py-1.5" style={{ minHeight: Math.max(puertos.entrada.length, puertos.salida.length) * 16 + 6 }}>
        {puertos.entrada.map((puerto, i) => (
          <div key={puerto} style={{ position: "absolute", left: 8, top: 4 + i * 16 }}>
            <Handle type="target" position={Position.Left} id={puerto}
              style={{ top: 6, left: -12, width: 8, height: 8, background: "#a1a1aa" }} />
            <span className="text-[9px] text-zinc-400">{ABREVIATURA_PUERTO[puerto] ?? puerto}</span>
          </div>
        ))}
        {puertos.salida.map((puerto, i) => (
          <div key={puerto} style={{ position: "absolute", right: 8, top: 4 + i * 16 }}>
            <Handle type="source" position={Position.Right} id={puerto}
              style={{ top: 6, right: -12, width: 8, height: 8, background: "#a1a1aa" }} />
            <span className="text-[9px] text-zinc-400">{ABREVIATURA_PUERTO[puerto] ?? puerto}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
