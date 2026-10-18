"use client";

import { useEffect, useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import type { EstudioSimulacion, OpcionesEstudio } from "./contratoEstudio";
import GraficaResultados from "../../componentes/graficas/GraficaResultados";
import { especificacionesPorOmision } from "../../componentes/graficas/datos";
import type { ConjuntoResultados } from "../../motores/resultados/contrato";
import { Estado, descargarArchivo, numero } from "./presentacionEstudio";
import { numeroDe } from "./usoEstudio";
import type { OrigenMotor } from "./desdeMotor";
import ComparacionMotor from "./ComparacionMotor";

type OpcionesSimulacion = NonNullable<OpcionesEstudio["simulacion"]>;

export default function VistaSimulacion({ f, simulacion, cargando, simular, nombreModelo, origen }: {
  f: FormulacionNucleo; simulacion?: EstudioSimulacion; cargando: boolean; nombreModelo: string;
  simular: (op: OpcionesSimulacion) => void; origen?: OrigenMotor | null;
}) {
  const sinLugar = f.condiciones.filter(c => c.tipo !== "inicial" && !(c as { lugar?: unknown }).lugar);
  // Desde el motor: el horizonte de la hoja, en segundos, y su frontera.
  const [tFinal, setTFinal] = useState(origen ? String(origen.simulacion.tFinalSI) : "1"), [muestras, setMuestras] = useState(origen ? String(Math.min(201, origen.simulacion.muestras)) : "41"), [nodos, setNodos] = useState("");
  const [extremos, setExtremos] = useState<Record<string, "desde" | "hasta" | "">>({});
  const [error, setError] = useState("");
  const [indice, setIndice] = useState(0), [reproduciendo, setReproduciendo] = useState(false), [fisico, setFisico] = useState(!!origen);
  const n = simulacion?.tiempos?.length ?? 0;
  useEffect(() => {
    if (!reproduciendo || n < 2) return;
    const id = setInterval(() => setIndice(i => (i + 1) % n), 120);
    return () => clearInterval(id);
  }, [reproduciendo, n]);
  const lanzar = () => {
    const tf = numeroDe(tFinal), m = numeroDe(muestras), N = nodos.trim() ? numeroDe(nodos) : null;
    if (tf === null || tf <= 0) { setError(origen ? "Indica un tiempo final positivo, en segundos." : "Indica un tiempo final adimensional positivo."); return; }
    const faltan = sinLugar.filter(c => !extremos[c.id]);
    if (faltan.length) { setError(`Indica en qué extremo se impone: ${faltan.map(c => c.id).join(", ")}.`); return; }
    setError(""); setIndice(0); setReproduciendo(false);
    simular({ ...(origen ? { tFinalSI: tf, ...(origen.simulacion.periodica ? { periodica: true } : {}) } : { tFinal: tf }), muestras: Math.max(2, Math.min(201, Math.round(m ?? 41))), ...(N ? { nodos: Math.max(5, Math.min(801, Math.round(N))) } : {}),
      ...(sinLugar.length ? { fronteras: sinLugar.map(c => ({ condicionId: c.id, extremo: extremos[c.id] as "desde" | "hasta" })) } : {}) });
  };
  const fis = simulacion?.fisico;
  const usarFisico = fisico && fis && fis.tiempo.valoresSI && Object.values(fis.campos).every(Boolean) && (!simulacion?.coordenada || fis.coordenada?.valoresSI);
  return (
    <div className="adim-estudio-vista">
      <section className="adim-estudio-bloque">
        <h3>Simulación de esta formulación</h3>
        <p className="adim-estudio-nota">Resuelve las ecuaciones publicadas con los valores dados: método de líneas, diferencias centradas, condiciones declaradas e integración BDF. No es un modelo de ejemplo: son tus ecuaciones.</p>
        <form className="adim-form-linea" onSubmit={e => { e.preventDefault(); lanzar(); }}>
          <label>{origen ? "Tiempo final (s)" : "Tiempo final (τ)"}<input inputMode="decimal" value={tFinal} onChange={e => setTFinal(e.target.value)} /></label>
          <label>Instantes<input inputMode="numeric" value={muestras} onChange={e => setMuestras(e.target.value)} /></label>
          <label>Nodos<input inputMode="numeric" value={nodos} onChange={e => setNodos(e.target.value)} placeholder="automático" /></label>
          {sinLugar.map(c => <label key={c.id}>Extremo de {c.id}<select value={extremos[c.id] ?? ""} onChange={e => setExtremos({ ...extremos, [c.id]: e.target.value as "desde" | "hasta" })}><option value="">elige…</option><option value="desde">inicial</option><option value="hasta">final</option></select></label>)}
          <button className="adim-button is-primary" type="submit" disabled={cargando}>{cargando ? "Simulando…" : "Simular"}</button>
        </form>
        {error && <p className="adim-input-error">{error}</p>}
        {simulacion && simulacion.estado !== "calculado" && <Estado estado={simulacion.estado} motivo={simulacion.motivo} />}
      </section>
      {simulacion?.estado === "calculado" && simulacion.tiempos && simulacion.campos && (
        <section className="adim-estudio-bloque">
          <div className="adim-sim-barra">
            <button type="button" className="adim-button" onClick={() => setReproduciendo(!reproduciendo)} disabled={n < 2}>{reproduciendo ? "Pausar" : "Reproducir"}</button>
            <input type="range" min={0} max={Math.max(0, n - 1)} value={Math.min(indice, n - 1)} onChange={e => { setReproduciendo(false); setIndice(Number(e.target.value)); }} aria-label="Instante" />
            <span className="adim-sim-tiempo">τ = {numero(simulacion.tiempos[Math.min(indice, n - 1)])}{usarFisico && fis?.tiempo.valoresSI ? ` · t = ${numero(fis.tiempo.valoresSI[Math.min(indice, n - 1)])} s` : ""}</span>
            {fis && <label className="adim-conmutador"><input type="checkbox" checked={fisico} onChange={e => setFisico(e.target.checked)} /> Unidades físicas (SI)</label>}
          </div>
          {simulacion.resultados ? (() => {
            const c = simulacion.resultados!, k = Math.min(indice, n - 1);
            const ejes = usarFisico && c.ejes.some(e => e.id === "t") ? ["t", "x"] : ["tau", "xi"];
            return especificacionesPorOmision(c, { ejes, instante: k }).map(e => (
              <GraficaResultados key={e.id} conjunto={c} alto={simulacion.coordenada ? 340 : 320}
                especificacion={{ ...e, titulo: simulacion.coordenada ? "Perfil" : "Evolución temporal" }} limitesY={rangoSeries(c, e.y)} />
            ));
          })() : <p className="adim-estudio-nota">El núcleo no publicó el conjunto de resultados: reinicia el backend con el núcleo actual.</p>}
          <div className="adim-sim-datos">
            <p>{simulacion.metodo?.integrador} · {simulacion.metodo?.nodos} {simulacion.coordenada ? "nodos" : "estado(s)"} · rtol {simulacion.metodo?.rtol} · {simulacion.metodo?.evaluaciones} evaluaciones</p>
            {simulacion.verificacionMalla?.diferenciaRelativa != null && <p>Verificación de malla: con {simulacion.verificacionMalla.nodosRefinados} nodos la diferencia relativa al final es {numero(simulacion.verificacionMalla.diferenciaRelativa)} ({simulacion.verificacionMalla.nota}).</p>}
            {simulacion.avisoMalla && <p className="adim-aviso">{simulacion.avisoMalla}</p>}
            {fis && fis.faltan.length > 0 && <p className="adim-aviso">Unidades físicas incompletas: {fis.faltan.join("; ")}.</p>}
          </div>
          <div className="adim-acciones">
            <button type="button" className="adim-button" onClick={() => descargarArchivo(`simulacion-${slug(nombreModelo)}.csv`, csv(simulacion), "text/csv")}>Descargar datos (CSV)</button>
            {simulacion.codigoPython ? <button type="button" className="adim-button" onClick={() => descargarArchivo(`simulacion-${slug(nombreModelo)}.py`, simulacion.codigoPython!, "text/x-python")}>Descargar script de Python</button>
              : simulacion.codigoMotivo && <span className="adim-estudio-nota">Sin script: {simulacion.codigoMotivo}</span>}
          </div>
          <p className="adim-estudio-metodo">{simulacion.motivo}{simulacion.metodo?.frontera === "periodica" ? ", frontera periódica" : ""}. El script reproduce la misma discretización con numpy y scipy.</p>
          {origen && simulacion.fisico && <ComparacionMotor origen={origen} fisico={simulacion.fisico} />}
        </section>
      )}
    </div>
  );
}

/** Rango fijo de las series en toda la trayectoria: el eje no salta al reproducir. */
function rangoSeries(c: ConjuntoResultados, ids: string[]): [number, number] | undefined {
  const v = c.series.filter(s => ids.includes(s.id)).flatMap(s => [s.valores].flat(2)).filter((x): x is number => typeof x === "number" && Number.isFinite(x));
  return v.length ? [Math.min(...v), Math.max(...v)] : undefined;
}

function slug(t: string) { return t.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "modelo"; }

function csv(s: EstudioSimulacion): string {
  const campos = Object.keys(s.campos ?? {});
  const filas = ["tau," + (s.coordenada ? "xi," : "") + campos.join(",")];
  (s.tiempos ?? []).forEach((t, i) => {
    const n = s.coordenada ? s.xi!.length : 1;
    for (let j = 0; j < n; j++) filas.push([t, ...(s.coordenada ? [s.xi![j]] : []), ...campos.map(c => s.campos![c][i][j])].join(","));
  });
  return filas.join("\n") + "\n";
}
