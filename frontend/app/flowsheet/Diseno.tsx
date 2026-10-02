"use client";

import { useMemo, useState } from "react";
import type { Node } from "@xyflow/react";
import {
  DatosNodo,
  DatosOperacion,
  variablesDeCorriente,
  variablesDeOperacion,
  etiquetaVariable,
  formatear,
  type RespuestaResolver,
} from "./modelo";
import { aSI, desdeSI, type Unidades } from "./unidades";

/**
 * Las dos preguntas que no son "cuanto da".
 *
 * El resto de la aplicacion resuelve hacia adelante: se dan datos y sale
 * un resultado. Esta vista hace las dos preguntas que de verdad se hacen
 * al disenar, y que hasta ahora solo existian desde Python:
 *
 *   - Especificaciones: "quiero N = 12 etapas; que reflujo hace falta".
 *     El objetivo y la variable que se mueve pueden estar en equipos
 *     distintos, con un reciclo en medio.
 *   - Barridos: "que pasa si subo el reflujo". No es calculo sino
 *     comprension, y por eso la respuesta es una tabla con su grafica y
 *     no un numero.
 *
 * Las dos cuestan caro: cada iteracion del lazo y cada punto del barrido
 * son una resolucion COMPLETA del diagrama, reciclos incluidos. Por eso
 * la vista insiste en el coste (muestra cuantas resoluciones costo) en
 * lugar de esconderlo.
 */

interface Especificacion {
  objetivo: string;
  valor: string;
  manipulada: string;
  minimo: string;
  maximo: string;
}

interface Cumplida {
  objetivo: string;
  pedido: number;
  obtenido: number | null;
  error: number | null;
  manipulada: string;
  valor: number;
}

interface PuntoBarrido {
  valor: number;
  pool: Record<string, number>;
  completo: boolean;
  error: string | null;
}

const MAX_PUNTOS = 40;

export default function Diseno({
  nodos, componentes, dados, unidades, apiUrl, construirPeticion, onResuelto,
}: {
  nodos: Node<DatosNodo>[];
  componentes: string[];
  dados: Record<string, string>;
  unidades: Unidades;
  apiUrl: string;
  construirPeticion: () => Record<string, unknown>;
  onResuelto: (datos: RespuestaResolver) => void;
}) {
  const [pestana, setPestana] = useState<"especificaciones" | "barrido">("especificaciones");

  // Todas las claves del pool, para los selectores. Se calculan en local
  // con las mismas funciones que usa el panel lateral, en vez de pedirlas
  // al servidor: asi los desplegables ya estan llenos ANTES de la primera
  // resolucion, que es justo cuando se plantea un objetivo de diseno.
  const variables = useMemo(() => {
    const claves: string[] = [];
    for (const n of nodos) {
      if (n.data.clase === "corriente") {
        for (const v of variablesDeCorriente(componentes.length)) claves.push(`${n.id}.${v}`);
      } else {
        for (const v of variablesDeOperacion(n.data as DatosOperacion)) claves.push(`${n.id}.${v}`);
      }
    }
    return claves.sort();
  }, [nodos, componentes.length]);

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 p-4">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex rounded border border-zinc-700 p-0.5 text-xs">
          {([["especificaciones", "Especificaciones de diseño"], ["barrido", "Barrido de sensibilidad"]] as const).map(
            ([valor, etiqueta]) => (
              <button
                key={valor}
                onClick={() => setPestana(valor)}
                className={`rounded px-3 py-1 ${
                  pestana === valor ? "bg-emerald-600 text-white" : "text-zinc-400 hover:text-zinc-100"
                }`}
              >
                {etiqueta}
              </button>
            )
          )}
        </div>

        {pestana === "especificaciones" ? (
          <PanelEspecificaciones
            variables={variables} componentes={componentes} dados={dados}
            unidades={unidades} apiUrl={apiUrl}
            construirPeticion={construirPeticion} onResuelto={onResuelto}
          />
        ) : (
          <PanelBarrido
            variables={variables} componentes={componentes} dados={dados}
            unidades={unidades} apiUrl={apiUrl} construirPeticion={construirPeticion}
          />
        )}
      </div>
    </div>
  );
}

/** "col1.R" -> "col1 · R (reflujo)", con el componente si es una fraccion. */
function etiquetaClave(clave: string, componentes: string[]): string {
  const [nodo, ...resto] = clave.split(".");
  return `${nodo} · ${etiquetaVariable(resto.join("."), componentes)}`;
}

function SelectorVariable({
  valor, onCambio, variables, componentes, excluir, vacio, nombre,
}: {
  valor: string;
  onCambio: (v: string) => void;
  variables: string[];
  componentes: string[];
  excluir?: string;
  vacio: string;
  nombre: string;
}) {
  return (
    <select
      value={valor}
      onChange={(e) => onCambio(e.target.value)}
      data-campo={nombre}
      aria-label={nombre}
      className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100"
    >
      <option value="">{vacio}</option>
      {variables.filter((v) => v !== excluir).map((v) => (
        <option key={v} value={v}>{etiquetaClave(v, componentes)}</option>
      ))}
    </select>
  );
}

function Campo({
  valor, onCambio, sufijo, ancho = "w-24", nombre,
}: {
  valor: string;
  onCambio: (v: string) => void;
  sufijo?: string;
  ancho?: string;
  /**
   * Identificador estable del campo (`data-campo`). Varias de estas cajas
   * son identicas por fuera -- el minimo y el maximo de un rango, por
   * ejemplo -- asi que sin esto no hay forma de referirse a una sola, ni
   * desde una prueba ni desde un lector de pantalla.
   */
  nombre: string;
}) {
  return (
    <div className="flex items-center gap-1">
      <input
        value={valor}
        onChange={(e) => onCambio(e.target.value)}
        inputMode="decimal"
        data-campo={nombre}
        aria-label={nombre}
        className={`${ancho} rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100`}
      />
      {sufijo && <span className="text-[10px] text-zinc-500">{sufijo}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------
// Especificaciones
// ---------------------------------------------------------------------

function PanelEspecificaciones({
  variables, componentes, dados, unidades, apiUrl, construirPeticion, onResuelto,
}: {
  variables: string[];
  componentes: string[];
  dados: Record<string, string>;
  unidades: Unidades;
  apiUrl: string;
  construirPeticion: () => Record<string, unknown>;
  onResuelto: (datos: RespuestaResolver) => void;
}) {
  const [specs, setSpecs] = useState<Especificacion[]>([
    { objetivo: "", valor: "", manipulada: "", minimo: "", maximo: "" },
  ]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cumplidas, setCumplidas] = useState<Cumplida[] | null>(null);
  const [evaluaciones, setEvaluaciones] = useState<number | null>(null);

  function cambiar(i: number, cambio: Partial<Especificacion>) {
    setSpecs((s) => s.map((e, j) => (j === i ? { ...e, ...cambio } : e)));
  }

  const sim = (clave: string) => unidades.unidadDe(clave)?.simbolo ?? "";

  // Lo que se puede decir ANTES de gastar una peticion. La frontera HTTP
  // rechaza todo esto con sus propios mensajes, pero esperar un 422 para
  // enterarse de que falta rellenar un campo es una mala forma de
  // trabajar.
  const problemas: string[] = [];
  const completas = specs.filter((s) => s.objetivo && s.manipulada);
  for (const s of completas) {
    if (s.objetivo === s.manipulada) {
      problemas.push(`${etiquetaClave(s.objetivo, componentes)} no puede ser a la vez el objetivo y lo que se mueve.`);
    }
    if (dados[s.manipulada] !== undefined && dados[s.manipulada] !== "") {
      // El caso que mas desconcierta: la especificacion CONVIERTE la
      // manipulada en incognita, asi que darla tambien como dato es
      // ambiguo y el nucleo lo rechaza. Mejor decirlo aqui, con el arreglo.
      problemas.push(
        `${etiquetaClave(s.manipulada, componentes)} está dada como dato en el diagrama. ` +
        `Una especificación la convierte en incógnita: bórrala del equipo o cambia de variable.`
      );
    }
    if (s.minimo !== "" && s.maximo !== "" && Number(s.minimo) >= Number(s.maximo)) {
      problemas.push(`El rango de ${etiquetaClave(s.manipulada, componentes)} está al revés o vacío.`);
    }
    if (s.valor === "" || s.minimo === "" || s.maximo === "") {
      problemas.push(`Falta rellenar el valor o el rango de ${etiquetaClave(s.objetivo, componentes)}.`);
    }
  }
  const listo = completas.length > 0 && problemas.length === 0;

  async function resolver() {
    setCargando(true);
    setError(null);
    setCumplidas(null);
    try {
      // La frontera de unidades, con el detalle que es facil pasar por
      // alto: 'valor' esta en la unidad del OBJETIVO, mientras que el
      // rango esta en la de la MANIPULADA. Son variables distintas y
      // pueden tener unidades distintas (pedir una temperatura en degC
      // moviendo un caudal en kg/h).
      const especificaciones = completas.map((s) => ({
        objetivo: s.objetivo,
        valor: aSI(Number(s.valor), unidades.unidadDe(s.objetivo)),
        manipulada: s.manipulada,
        minimo: aSI(Number(s.minimo), unidades.unidadDe(s.manipulada)),
        maximo: aSI(Number(s.maximo), unidades.unidadDe(s.manipulada)),
      }));
      const resp = await fetch(`${apiUrl}/diagrama/resolver`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...construirPeticion(), especificaciones }),
      });
      if (!resp.ok) {
        const detalle = await resp.json().catch(() => null);
        throw new Error(detalle?.detail ?? `Error HTTP ${resp.status}`);
      }
      const datos = await resp.json();
      setCumplidas(datos.especificaciones?.cumplidas ?? []);
      setEvaluaciones(datos.especificaciones?.evaluaciones ?? null);
      // El diagrama resuelto se vuelca en el estado comun, para poder
      // pasar a "Resultados" y verlo con sus graficas como cualquier otro.
      onResuelto(datos);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-zinc-400">
        En vez de dar el reflujo y obtener la pureza, se pide la pureza y el simulador busca el
        reflujo. <strong className="text-zinc-300">La variable que se mueve no se da como dato</strong>:
        la especificación la convierte en incógnita, y al conteo de grados de libertad le suma una
        ecuación. El objetivo puede estar en otro equipo, con un reciclo en medio.
      </p>

      {specs.map((s, i) => (
        <div key={i} className="rounded border border-zinc-800 bg-zinc-900/50 p-3">
          <div className="grid grid-cols-[1fr_auto] items-start gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="w-20 text-[10px] uppercase tracking-wide text-zinc-500">Quiero que</span>
                <div className="min-w-56 flex-1">
                  <SelectorVariable
                    valor={s.objetivo} onCambio={(v) => cambiar(i, { objetivo: v })}
                    variables={variables} componentes={componentes}
                    excluir={s.manipulada} vacio="— elige el objetivo —" nombre="objetivo"
                  />
                </div>
                <span className="text-xs text-zinc-500">valga</span>
                <Campo nombre="valor" valor={s.valor} onCambio={(v) => cambiar(i, { valor: v })} sufijo={sim(s.objetivo)} />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="w-20 text-[10px] uppercase tracking-wide text-zinc-500">Moviendo</span>
                <div className="min-w-56 flex-1">
                  <SelectorVariable
                    valor={s.manipulada} onCambio={(v) => cambiar(i, { manipulada: v })}
                    variables={variables} componentes={componentes}
                    excluir={s.objetivo} vacio="— elige qué se mueve —" nombre="manipulada"
                  />
                </div>
                <span className="text-xs text-zinc-500">entre</span>
                <Campo nombre="minimo" valor={s.minimo} onCambio={(v) => cambiar(i, { minimo: v })} ancho="w-20" />
                <span className="text-xs text-zinc-500">y</span>
                <Campo nombre="maximo" valor={s.maximo} onCambio={(v) => cambiar(i, { maximo: v })} ancho="w-20" sufijo={sim(s.manipulada)} />
              </div>
            </div>

            {specs.length > 1 && (
              <button
                onClick={() => setSpecs((x) => x.filter((_, j) => j !== i))}
                className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-400 hover:border-red-600 hover:text-red-400"
              >
                quitar
              </button>
            )}
          </div>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => setSpecs((s) => [...s, { objetivo: "", valor: "", manipulada: "", minimo: "", maximo: "" }])}
          className="rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:border-emerald-500"
        >
          + otra especificación
        </button>
        <button
          onClick={resolver}
          disabled={cargando || !listo}
          className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {cargando ? "Buscando..." : "Resolver con especificaciones"}
        </button>
        {cargando && (
          <span className="text-[11px] text-zinc-500">
            cada iteración resuelve el diagrama completo, reciclos incluidos
          </span>
        )}
      </div>

      {/* El rango acota la busqueda a la zona donde el diagrama se puede
          resolver; no es un detalle de implementacion. */}
      <p className="text-[11px] leading-relaxed text-zinc-600">
        El rango no es decoración: casi toda variable de proceso tiene un rango físico (un reflujo no
        es negativo, una fracción no pasa de 1), y acotarlo es lo que evita que la búsqueda acabe
        donde el diagrama no se puede resolver. Si el objetivo no se alcanza dentro de él, el
        simulador dice qué intervalo recorre de verdad.
      </p>

      {problemas.length > 0 && (
        <ul className="space-y-1 rounded border border-amber-800 bg-amber-950/40 p-3 text-[11px] text-amber-200">
          {[...new Set(problemas)].map((p) => <li key={p}>— {p}</li>)}
        </ul>
      )}

      {error && (
        <div className="rounded border border-red-800 bg-red-950/40 p-3 text-xs leading-relaxed text-red-200">
          {error}
        </div>
      )}

      {cumplidas && cumplidas.length > 0 && (
        <div className="rounded border border-emerald-800 bg-emerald-950/30 p-3">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-zinc-500">
                <th className="pb-1">Objetivo</th>
                <th className="pb-1">Pedido</th>
                <th className="pb-1">Obtenido</th>
                <th className="pb-1">Error</th>
                <th className="pb-1">Hizo falta</th>
              </tr>
            </thead>
            <tbody>
              {cumplidas.map((c) => {
                const uObj = unidades.unidadDe(c.objetivo);
                const uMan = unidades.unidadDe(c.manipulada);
                const vObj = c.objetivo.split(".").slice(1).join(".");
                const vMan = c.manipulada.split(".").slice(1).join(".");
                return (
                  <tr key={c.objetivo} className="border-t border-zinc-800">
                    <td className="py-1 text-zinc-300">{etiquetaClave(c.objetivo, componentes)}</td>
                    <td className="py-1 font-mono text-zinc-400">
                      {formatear(desdeSI(c.pedido, uObj), vObj)} {uObj?.simbolo ?? ""}
                    </td>
                    <td className="py-1 font-mono text-emerald-300">
                      {c.obtenido === null ? "—" : formatear(desdeSI(c.obtenido, uObj), vObj)}
                    </td>
                    {/* El error va en notacion exponencial a proposito: es
                        la unica forma de ver que 1e-12 no es "casi" sino
                        exacto a efectos practicos. */}
                    <td className="py-1 font-mono text-[10px] text-zinc-500">
                      {c.error === null ? "—" : c.error.toExponential(2)}
                    </td>
                    <td className="py-1 font-mono text-sky-300">
                      {etiquetaClave(c.manipulada, componentes)} = {formatear(desdeSI(c.valor, uMan), vMan)}{" "}
                      {uMan?.simbolo ?? ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {evaluaciones !== null && (
            <p className="mt-2 text-[11px] text-zinc-500">
              Costó <strong className="text-zinc-400">{evaluaciones}</strong> resoluciones completas del
              diagrama. El resultado ya está cargado: pasa a «Resultados» para verlo con sus gráficas.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------
// Barrido
// ---------------------------------------------------------------------

function PanelBarrido({
  variables, componentes, dados, unidades, apiUrl, construirPeticion,
}: {
  variables: string[];
  componentes: string[];
  dados: Record<string, string>;
  unidades: Unidades;
  apiUrl: string;
  construirPeticion: () => Record<string, unknown>;
}) {
  const [variable, setVariable] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [puntos, setPuntos] = useState("9");
  const [seguir, setSeguir] = useState<string[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<{ puntos: PuntoBarrido[]; resueltos: number; fallidos: number } | null>(null);

  const n = Math.round(Number(puntos));
  const problemas: string[] = [];
  if (variable && dados[variable] !== undefined && dados[variable] !== "") {
    problemas.push(
      `${etiquetaClave(variable, componentes)} está dada como dato. Bórrala del equipo: el barrido es ` +
      `quien le pone valor en cada punto.`
    );
  }
  if (desde !== "" && hasta !== "" && Number(desde) === Number(hasta)) {
    problemas.push("El principio y el final del rango son el mismo número.");
  }
  if (puntos !== "" && (!Number.isFinite(n) || n < 2 || n > MAX_PUNTOS)) {
    problemas.push(`El número de puntos va de 2 a ${MAX_PUNTOS}: cada punto es una resolución completa del diagrama.`);
  }
  if (seguir.length === 0) problemas.push("Elige al menos una variable que seguir.");
  const listo = variable !== "" && desde !== "" && hasta !== "" && problemas.length === 0;

  async function correr() {
    setCargando(true);
    setError(null);
    setResultado(null);
    try {
      const unidad = unidades.unidadDe(variable);
      const a = Number(desde);
      const b = Number(hasta);
      const valores_barrido = Array.from({ length: n }, (_, i) =>
        aSI(a + ((b - a) * i) / (n - 1), unidad)
      );
      const resp = await fetch(`${apiUrl}/diagrama/barrido`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...construirPeticion(), variable, valores_barrido, seguir }),
      });
      if (!resp.ok) {
        const detalle = await resp.json().catch(() => null);
        throw new Error(detalle?.detail ?? `Error HTTP ${resp.status}`);
      }
      setResultado(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCargando(false);
    }
  }

  const unidadX = unidades.unidadDe(variable);
  const varX = variable.split(".").slice(1).join(".");

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-zinc-400">
        No es una herramienta de cálculo sino de comprensión: la pregunta no es «cuánto da» sino{" "}
        <strong className="text-zinc-300">«qué pasa si subo el reflujo»</strong>. Un punto que no se
        pueda resolver no tumba el barrido — se marca con su motivo y el resto sigue, porque el borde
        de la zona viable es parte de lo que interesa ver.
      </p>

      <div className="space-y-3 rounded border border-zinc-800 bg-zinc-900/50 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-[10px] uppercase tracking-wide text-zinc-500">Variar</span>
          <div className="min-w-56 flex-1">
            <SelectorVariable
              valor={variable} onCambio={setVariable} variables={variables}
              componentes={componentes} vacio="— elige la variable —" nombre="variable"
            />
          </div>
          <span className="text-xs text-zinc-500">de</span>
          <Campo nombre="desde" valor={desde} onCambio={setDesde} ancho="w-20" />
          <span className="text-xs text-zinc-500">a</span>
          <Campo nombre="hasta" valor={hasta} onCambio={setHasta} ancho="w-20" sufijo={unidadX?.simbolo ?? ""} />
          <span className="text-xs text-zinc-500">en</span>
          <Campo nombre="puntos" valor={puntos} onCambio={setPuntos} ancho="w-14" sufijo="puntos" />
        </div>

        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">Seguir</div>
          <div className="flex max-h-32 flex-wrap gap-1 overflow-auto rounded border border-zinc-800 p-2">
            {variables.filter((v) => v !== variable).map((v) => {
              const activa = seguir.includes(v);
              return (
                <button
                  key={v}
                  onClick={() => setSeguir((s) => (activa ? s.filter((x) => x !== v) : [...s, v]))}
                  className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
                    activa
                      ? "border-emerald-600 bg-emerald-950/60 text-emerald-200"
                      : "border-zinc-800 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
                  }`}
                >
                  {v}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={correr}
          disabled={cargando || !listo}
          className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {cargando ? `Resolviendo ${n} puntos...` : "Barrer"}
        </button>
        {cargando && (
          <span className="text-[11px] text-zinc-500">
            {n} resoluciones completas del diagrama, una por punto
          </span>
        )}
      </div>

      {problemas.length > 0 && (
        <ul className="space-y-1 rounded border border-amber-800 bg-amber-950/40 p-3 text-[11px] text-amber-200">
          {[...new Set(problemas)].map((p) => <li key={p}>— {p}</li>)}
        </ul>
      )}

      {error && (
        <div className="rounded border border-red-800 bg-red-950/40 p-3 text-xs leading-relaxed text-red-200">
          {error}
        </div>
      )}

      {resultado && (
        <>
          <div className="text-[11px] text-zinc-500">
            {resultado.resueltos} punto(s) resueltos
            {resultado.fallidos > 0 && (
              <>
                {" · "}
                <span className="text-amber-400">{resultado.fallidos} fuera de la zona viable</span>
              </>
            )}
          </div>

          {seguir.map((clave) => (
            <GraficaBarrido
              key={clave} puntos={resultado.puntos} clave={clave}
              variableX={variable} componentes={componentes} unidades={unidades}
            />
          ))}

          <div className="overflow-auto rounded border border-zinc-800">
            <table className="w-full text-xs">
              <thead className="bg-zinc-900">
                <tr className="text-left text-[10px] uppercase tracking-wide text-zinc-500">
                  <th className="px-2 py-1">
                    {variable ? etiquetaClave(variable, componentes) : ""} [{unidadX?.simbolo ?? "SI"}]
                  </th>
                  {seguir.map((v) => (
                    <th key={v} className="px-2 py-1">
                      {etiquetaClave(v, componentes)} [{unidades.unidadDe(v)?.simbolo ?? "SI"}]
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultado.puntos.map((p, i) => (
                  <tr key={i} className="border-t border-zinc-800">
                    <td className="px-2 py-1 font-mono text-zinc-300">
                      {formatear(desdeSI(p.valor, unidadX), varX)}
                    </td>
                    {p.error ? (
                      <td colSpan={seguir.length} className="px-2 py-1 text-[11px] text-amber-400">
                        {p.error}
                      </td>
                    ) : (
                      seguir.map((v) => {
                        const u = unidades.unidadDe(v);
                        const bruto = p.pool[v];
                        return (
                          <td key={v} className="px-2 py-1 font-mono text-sky-300">
                            {bruto === undefined || bruto === null
                              ? "—"
                              : formatear(desdeSI(bruto, u), v.split(".").slice(1).join("."))}
                          </td>
                        );
                      })
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Grafica de una variable seguida frente a la barrida.
 *
 * SVG a mano y no una libreria: son dos ejes y una polilinea, y lo que
 * importa de verdad es que los puntos que NO se pudieron resolver se vean
 * como un hueco con su marca, y no interpolados como si ahi hubiera un
 * valor. Una linea que cruza la zona inviable mentiria sobre justo lo que
 * el barrido sirve para encontrar.
 */
function GraficaBarrido({
  puntos, clave, variableX, componentes, unidades,
}: {
  puntos: PuntoBarrido[];
  clave: string;
  variableX: string;
  componentes: string[];
  unidades: Unidades;
}) {
  const uX = unidades.unidadDe(variableX);
  const uY = unidades.unidadDe(clave);
  const datos = puntos
    .map((p) => ({
      x: desdeSI(p.valor, uX),
      y: p.pool[clave] === undefined || p.pool[clave] === null ? null : desdeSI(p.pool[clave], uY),
      error: p.error,
    }))
    .filter((d) => Number.isFinite(d.x));

  const buenos = datos.filter((d) => d.y !== null && Number.isFinite(d.y));
  if (buenos.length < 2) return null;

  const W = 640, H = 200, M = { t: 10, r: 12, b: 28, l: 56 };
  const xs = datos.map((d) => d.x);
  const ys = buenos.map((d) => d.y as number);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (y0 === y1) { y0 -= 1; y1 += 1; }   // una variable que no responde: eje plano, no division por cero
  const px = (x: number) => M.l + ((x - x0) / (x1 - x0 || 1)) * (W - M.l - M.r);
  const py = (y: number) => H - M.b - ((y - y0) / (y1 - y0)) * (H - M.t - M.b);

  // Se parte la linea en tramos continuos: cada hueco corta el trazo.
  const tramos: { x: number; y: number }[][] = [];
  let actual: { x: number; y: number }[] = [];
  for (const d of datos) {
    if (d.y === null || !Number.isFinite(d.y)) {
      if (actual.length) { tramos.push(actual); actual = []; }
    } else {
      actual.push({ x: d.x, y: d.y });
    }
  }
  if (actual.length) tramos.push(actual);

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/50 p-2">
      <div className="mb-1 px-1 text-[10px] uppercase tracking-wide text-zinc-500">
        {etiquetaClave(clave, componentes)} frente a {etiquetaClave(variableX, componentes)}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        <line x1={M.l} y1={H - M.b} x2={W - M.r} y2={H - M.b} stroke="#3f3f46" />
        <line x1={M.l} y1={M.t} x2={M.l} y2={H - M.b} stroke="#3f3f46" />
        {[y0, (y0 + y1) / 2, y1].map((v, i) => (
          <text key={i} x={M.l - 6} y={py(v) + 3} textAnchor="end" fill="#71717a" fontSize="9" fontFamily="monospace">
            {Math.abs(v) >= 10000 || (v !== 0 && Math.abs(v) < 0.01) ? v.toPrecision(3) : v.toFixed(2)}
          </text>
        ))}
        {[x0, x1].map((v, i) => (
          <text key={i} x={px(v)} y={H - M.b + 14} textAnchor={i === 0 ? "start" : "end"} fill="#71717a" fontSize="9" fontFamily="monospace">
            {Math.abs(v) >= 10000 || (v !== 0 && Math.abs(v) < 0.01) ? v.toPrecision(3) : v.toFixed(2)}
          </text>
        ))}
        {tramos.map((tramo, i) => (
          <polyline
            key={i} fill="none" stroke="#34d399" strokeWidth="1.5"
            points={tramo.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")}
          />
        ))}
        {buenos.map((d, i) => (
          <circle key={i} cx={px(d.x)} cy={py(d.y as number)} r="2.5" fill="#34d399" />
        ))}
        {/* Los inviables, como cruces en el eje: el borde se VE. */}
        {datos.filter((d) => d.y === null).map((d, i) => (
          <g key={i} stroke="#f59e0b" strokeWidth="1.2">
            <line x1={px(d.x) - 3} y1={H - M.b - 3} x2={px(d.x) + 3} y2={H - M.b + 3} />
            <line x1={px(d.x) - 3} y1={H - M.b + 3} x2={px(d.x) + 3} y2={H - M.b - 3} />
          </g>
        ))}
      </svg>
    </div>
  );
}
