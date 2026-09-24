"use client";

import { useState } from "react";
import Link from "next/link";
import { useSimulacion, nombresDe } from "../../components/SimulacionProvider";
import DiagramaTernario, { type CurvaTernaria, type PuntoMarcado } from "../../components/DiagramaTernario";
import DiagramaCuaternario from "../../components/DiagramaCuaternario";
import DescargarGrafico from "../../components/DescargarGrafico";
import type { RespuestaMapa } from "../residuales/page";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface PropiedadesReaccion {
  dH_rxn: number; dG_rxn: number; K_eq_std: number; K_eq: number;
  T_referencia: number; velocidad_equimolar: number | null; exotermica: boolean;
  aviso_balance: string | null;
}
interface RespuestaAzeotropos {
  componentes: string[];
  modo: string;
  azeotropos: { x: number[]; T: number | null; residual: number; desde: number[] }[];
  semillas_probadas: number;
}

export default function ReactivaPage() {
  const { componentes, listo } = useSimulacion();
  const nombres = nombresDe(componentes);
  const n = nombres.length;

  // La estequiometria se escribe por componente, en el MISMO orden que la
  // mezcla: negativo reactivo, positivo producto.
  const [nu, setNu] = useState<string[]>([]);
  const [A, setA] = useState("1e6");
  const [Ea, setEa] = useState("60000");
  const [Da, setDa] = useState("1");
  const [P, setP] = useState("101325");
  const [ref, setRef] = useState("0");
  const [nCurvas, setNCurvas] = useState("24");
  const [modo, setModo] = useState<"cinetico" | "equilibrio">("cinetico");
  const [Tref, setTref] = useState("350");
  const [discretas, setDiscretas] = useState(true);

  const [props, setProps] = useState<PropiedadesReaccion | null>(null);
  const [mapa, setMapa] = useState<RespuestaMapa | null>(null);
  const [azeo, setAzeo] = useState<RespuestaAzeotropos | null>(null);
  const [cargando, setCargando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const coeficientes = Array.from({ length: n }, (_, i) => nu[i] ?? "0");
  const reaccion = () => ({
    nu: coeficientes.map(Number),
    A: Number(A),
    Ea: Number(Ea),
    componente_referencia: Number(ref),
  });

  const ecuacion = () => {
    const izq: string[] = [], der: string[] = [];
    coeficientes.forEach((c, i) => {
      const v = Number(c);
      if (!Number.isFinite(v) || v === 0) return;
      const coef = Math.abs(v) === 1 ? "" : `${Math.abs(v)} `;
      (v < 0 ? izq : der).push(`${coef}${nombres[i]}`);
    });
    if (!izq.length || !der.length) return null;
    return `${izq.join(" + ")} ⇌ ${der.join(" + ")}`;
  };

  async function pedir(ruta: string, cuerpo: object, etiqueta: string) {
    setCargando(etiqueta);
    setError(null);
    try {
      const r = await fetch(`${API_URL}${ruta}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      const datos = await r.json();
      if (!r.ok) throw new Error(datos?.detail ?? "el servidor rechazó la petición");
      return datos;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setCargando(null);
    }
  }

  const curvas: CurvaTernaria[] = (mapa?.curvas ?? []).map((c) => ({ puntos: c.puntos, inicio: c.inicio }));
  const marcados: PuntoMarcado[] = (azeo?.azeotropos ?? []).map((a, i) => ({
    x: a.x, etiqueta: `azeótropo ${i + 1}`, T: a.T, color: "#fbbf24",
  }));

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-6 py-6">
      <div className="mx-auto max-w-5xl">
        <Link href="/termodinamica" className="text-xs text-zinc-500 hover:text-zinc-300">← Termodinámica</Link>
        <h1 className="mb-1 mt-1 text-lg font-semibold text-zinc-100">Destilación reactiva</h1>
        <p className="mb-5 max-w-3xl text-xs text-zinc-500">
          Con reacción, la trayectoria del residuo deja de depender solo del equilibrio líquido–vapor:{" "}
          <code className="text-zinc-400">dx/dξ = (x − y*) + Da·(ν − ν_tot·x)·r</code>. El número de Damköhler{" "}
          <strong className="text-zinc-400">Da</strong> pesa la reacción contra la evaporación: con Da = 0 sale el
          mapa inerte, y al subirlo el mapa se deforma. Eso es lo interesante del método:{" "}
          <span className="text-zinc-400">la reacción puede borrar una frontera de destilación</span> que en el
          sistema inerte hacía imposible la separación.
        </p>

        {listo && n !== 3 && n !== 4 && (
          <div className="rounded border border-amber-800 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
            Necesita 3 o 4 componentes; la simulación tiene {n}.{" "}
            <Link href="/configuracion" className="underline">Cámbialos aquí</Link>.
          </div>
        )}

        {(n === 3 || n === 4) && (
          <>
            {/* ------------------------------------------- la reacción */}
            <div className="mb-4 rounded border border-zinc-800 bg-zinc-900 p-3">
              <h2 className="mb-2 text-sm font-semibold text-zinc-200">La reacción</h2>
              <div className="mb-3 flex flex-wrap gap-3">
                {nombres.map((nombre, i) => (
                  <label key={nombre} className="text-xs">
                    <span className="mb-1 block text-zinc-400">ν {nombre}</span>
                    <input
                      className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                      value={coeficientes[i]}
                      onChange={(e) => {
                        const copia = [...coeficientes];
                        copia[i] = e.target.value;
                        setNu(copia);
                      }}
                    />
                  </label>
                ))}
              </div>
              <p className="mb-3 text-[11px] text-zinc-500">
                Negativo = reactivo, positivo = producto.{" "}
                {ecuacion()
                  ? <span className="font-mono text-emerald-300">{ecuacion()}</span>
                  : <span className="text-amber-500">Escribe al menos un reactivo y un producto.</span>}
              </p>

              <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs">
                  <span className="mb-1 block text-zinc-400">A (Arrhenius)</span>
                  <input className="w-24 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                    value={A} onChange={(e) => setA(e.target.value)} />
                </label>
                <label className="text-xs">
                  <span className="mb-1 block text-zinc-400">Ea [J/mol]</span>
                  <input className="w-24 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                    value={Ea} onChange={(e) => setEa(e.target.value)} />
                </label>
                <label className="text-xs">
                  <span className="mb-1 block text-zinc-400">Da</span>
                  <input className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                    value={Da} onChange={(e) => setDa(e.target.value)} />
                </label>
                <label className="text-xs">
                  <span className="mb-1 block text-zinc-400">Referencia (k)</span>
                  <select className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-100"
                    value={ref} onChange={(e) => setRef(e.target.value)}>
                    {nombres.map((nom, i) => <option key={nom} value={i}>{nom}</option>)}
                  </select>
                </label>
                <button
                  onClick={async () => {
                    const d = await pedir("/termodinamica/reaccion",
                      { componentes: nombres, reaccion: reaccion(), T_referencia: 350 }, "props");
                    if (d) setProps(d);
                  }}
                  disabled={cargando !== null}
                  className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
                  title="Barato: comprueba que la estequiometría y la cinética tengan sentido antes de integrar un mapa entero."
                >
                  {cargando === "props" ? "…" : "Comprobar la reacción"}
                </button>
              </div>

              {(props?.aviso_balance || mapa?.aviso_balance) && (
                <div className="mt-3 rounded border border-red-700 bg-red-950/50 px-3 py-2 text-[11px] leading-snug text-red-200">
                  <strong>La estequiometría no cierra.</strong>{" "}
                  {props?.aviso_balance ?? mapa?.aviso_balance}
                </div>
              )}
              {props && (
                <div className="mt-3 grid gap-x-6 gap-y-1 border-t border-zinc-800 pt-3 text-[11px] sm:grid-cols-2">
                  <div>
                    <span className="text-zinc-500">ΔH°rxn: </span>
                    <span className="font-mono text-zinc-200">{(props.dH_rxn / 1000).toFixed(2)} kJ/mol</span>
                    <span className={props.exotermica ? "text-orange-400" : "text-sky-400"}>
                      {" "}({props.exotermica ? "exotérmica" : "endotérmica"})
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">ΔG°rxn: </span>
                    <span className="font-mono text-zinc-200">{(props.dG_rxn / 1000).toFixed(2)} kJ/mol</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">K_eq(298 K): </span>
                    <span className="font-mono text-zinc-200">{props.K_eq_std.toPrecision(4)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">K_eq({props.T_referencia} K): </span>
                    <span className="font-mono text-zinc-200">{props.K_eq.toPrecision(4)}</span>
                  </div>
                  <div className="sm:col-span-2 text-zinc-500">
                    {props.exotermica
                      ? "Al ser exotérmica, subir la temperatura reduce K_eq: la conversión de equilibrio empeora al calentar, que es la tensión central de la destilación reactiva."
                      : "Al ser endotérmica, subir la temperatura aumenta K_eq: calentar favorece a la vez la reacción y la separación."}
                  </div>
                </div>
              )}
            </div>

            {/* ---------------------------------------------- acciones */}
            <div className="mb-4 flex flex-wrap items-end gap-3 rounded border border-zinc-800 bg-zinc-900 p-3">
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">Presión [Pa]</span>
                <input className="w-28 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={P} onChange={(e) => setP(e.target.value)} />
              </label>
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">Curvas</span>
                <input className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={nCurvas} onChange={(e) => setNCurvas(e.target.value)} />
              </label>
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">T ref [K]</span>
                <input className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={Tref} onChange={(e) => setTref(e.target.value)}
                  title="T a la que se evalúan K_eq (curva de equilibrio químico) y los saltos discretos." />
              </label>
              <label className="flex items-center gap-2 pb-1 text-[11px] text-zinc-300">
                <input type="checkbox" checked={discretas} onChange={(e) => setDiscretas(e.target.checked)} />
                trayectorias etapa a etapa
              </label>
              <button
                onClick={async () => {
                  const d = await pedir("/termodinamica/mapa-residual", {
                    componentes: nombres, P_sistema: Number(P), reaccion: reaccion(),
                    Da: Number(Da), n_curvas: Number(nCurvas), n_puntos: 120, xi_max: 40,
                    T_referencia: Number(Tref), incluir_trayectorias_discretas: discretas,
                    max_etapas: 60,
                  }, "mapa");
                  if (d) setMapa(d);
                }}
                disabled={cargando !== null || !ecuacion()}
                className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {cargando === "mapa" ? "Integrando…" : "Mapa reactivo"}
              </button>

              <div className="ml-auto flex items-end gap-2">
                <label className="text-xs">
                  <span className="mb-1 block text-zinc-400">Azeótropos por</span>
                  <select className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-100"
                    value={modo} onChange={(e) => setModo(e.target.value as "cinetico" | "equilibrio")}>
                    <option value="cinetico">control cinético</option>
                    <option value="equilibrio">equilibrio químico</option>
                  </select>
                </label>
                <button
                  onClick={async () => {
                    const d = await pedir("/termodinamica/azeotropos", {
                      componentes: nombres, P_sistema: Number(P), reaccion: reaccion(),
                      Da: Number(Da), modo, n_semillas: 12,
                    }, "azeo");
                    if (d) setAzeo(d);
                  }}
                  disabled={cargando !== null || !ecuacion()}
                  className="rounded border border-amber-700 px-3 py-1.5 text-xs text-amber-200 hover:bg-amber-950/50 disabled:opacity-50"
                >
                  {cargando === "azeo" ? "Buscando…" : "Buscar azeótropos"}
                </button>
              </div>
            </div>

            {error && (
              <div className="mb-4 rounded border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-200">{error}</div>
            )}

            {azeo && (
              <div className="mb-4 rounded border border-zinc-800 bg-zinc-900 p-3 text-xs">
                <h3 className="mb-1 text-sm font-semibold text-zinc-200">
                  Azeótropos reactivos ({azeo.modo === "cinetico" ? "control cinético" : "equilibrio químico"})
                </h3>
                {azeo.azeotropos.length === 0 ? (
                  <p className="text-zinc-500">
                    Ninguno converge desde las {azeo.semillas_probadas} semillas probadas. Eso no demuestra que no
                    existan: significa que este barrido no los encontró.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {azeo.azeotropos.map((a, i) => (
                      <li key={i} className="font-mono text-zinc-300">
                        <span className="text-amber-400">#{i + 1}</span>{" "}
                        {a.x.map((v, j) => `${nombres[j]}=${v.toFixed(4)}`).join("  ")}
                        {a.T && <span className="text-zinc-500"> · {a.T.toFixed(2)} K</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {mapa && mapa.curvas_fallidas > 0 && (
              <div className="mb-4 rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-[11px] text-amber-200">
                {mapa.curvas_fallidas} trayectorias no se pudieron integrar.
                {mapa.motivo_fallos && <> Primer motivo: <span className="font-mono">{mapa.motivo_fallos}</span></>}
              </div>
            )}

            {mapa && n === 3 && (
              <DescargarGrafico nombre={`mapa-reactivo-Da${Da}-${nombres.join("-")}`}>
                <DiagramaTernario
                  componentes={mapa.componentes}
                  curvas={curvas}
                  marcados={marcados}
                  T_vertices={mapa.T_vertices}
                  trayectoriasReactivas={mapa.trayectorias_reactivas}
                  curvaEquilibrio={mapa.curva_equilibrio_quimico}
                  lineasEstequiometricas={mapa.lineas_estequiometricas}
                  polo={mapa.polo}
                  titulo="Mapa de topología reactiva"
                  subtitulo={`Da = ${mapa.Da} · ${mapa.curvas.length} trayectorias · ${(mapa.P_sistema / 1000).toFixed(1)} kPa`}
                />
              </DescargarGrafico>
            )}

            {mapa && n === 4 && (
              <DiagramaCuaternario
                componentes={mapa.componentes}
                curvas={curvas}
                titulo="Mapa reactivo (4 componentes)"
                subtitulo={`Da = ${mapa.Da} · ${mapa.curvas.length} trayectorias`}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
