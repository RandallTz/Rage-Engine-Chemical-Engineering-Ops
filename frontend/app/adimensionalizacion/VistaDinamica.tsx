"use client";

import { useState } from "react";
import type { EstudioContinuacion, EstudioEstabilidad } from "./contratoEstudio";
import Grafica, { PALETA, type CurvaGrafica as Serie } from "../../componentes/graficas/Grafica";
import { Estado, Simbolo, numero } from "./presentacionEstudio";
import { numeroDe } from "./usoEstudio";

const CLASE: Record<string, string> = {
  estable: "Estable frente a perturbaciones de cualquier longitud de onda.",
  turing: "Inestabilidad de Turing: estable homogéneamente, pero una banda de longitudes de onda crece (patrones estacionarios).",
  onda: "Inestabilidad de onda: crece una banda de longitudes de onda con oscilación.",
  inestable_homogenea: "Inestable ya frente a perturbaciones uniformes (k = 0).",
  oscilatoria_homogenea: "Inestabilidad oscilatoria uniforme (par complejo con parte real positiva en k = 0): Hopf.",
};

export default function VistaDinamica({ estabilidad, continuacion, cargandoContinuacion, parametros, continuar }: {
  estabilidad?: EstudioEstabilidad; continuacion?: EstudioContinuacion; cargandoContinuacion: boolean;
  parametros: { id: string; unidad: string }[];
  continuar: (parametroId: string, desde: number, hasta: number, unidad: string) => void;
}) {
  const [pid, setPid] = useState(parametros[0]?.id ?? "");
  const [desde, setDesde] = useState(""), [hasta, setHasta] = useState(""), [unidad, setUnidad] = useState(parametros[0]?.unidad ?? "");
  const [error, setError] = useState("");
  return (
    <div className="adim-estudio-vista">
      <section className="adim-estudio-bloque">
        <h3>Estados homogéneos y estabilidad lineal</h3>
        {!estabilidad && <p className="adim-estudio-nota">Calcula con valores físicos para buscar estados homogéneos.</p>}
        {estabilidad && estabilidad.estado !== "calculado" && <Estado estado={estabilidad.estado} motivo={estabilidad.motivo} />}
        {estabilidad?.notaContinuo && <p className="adim-capa">{estabilidad.notaContinuo}.</p>}
        {estabilidad?.estado === "calculado" && (estabilidad.estados?.length ? estabilidad.estados.map((s, i) => (
          <article key={i} className="adim-estado-homogeneo">
            <h4>Estado {i + 1}: {Object.entries(s.u).map(([c, v]) => <span key={c} className="adim-par"><Simbolo id={c} /> = {numero(v, 6)}</span>)}</h4>
            <p><strong className={`adim-sello is-${s.homogeneo}`}>{s.homogeneo === "estable" ? "Estable" : s.homogeneo === "marginal" ? "Marginal" : "Inestable"}</strong> frente a perturbaciones uniformes. Autovalores del jacobiano: {s.autovalores.map(a => `${numero(a.re)}${a.im ? ` ${a.im > 0 ? "+" : "−"} ${numero(Math.abs(a.im))}i` : ""}`).join(", ")}.</p>
            {s.espacial.map(c => c.estado === "calculado" ? (
              <div key={c.coordenada} className="adim-dispersion">
                <p><strong>Respecto de <Simbolo id={c.coordenada} />:</strong> {CLASE[c.clase]}{c.kCritico !== null && <> Número de onda crítico k ≈ {numero(c.kCritico)}{c.banda && <>, banda inestable [{numero(c.banda.desde)}, {numero(c.banda.hasta)}]</>}.</>}</p>
                <Grafica titulo="Relación de dispersión" ejeX="número de onda k" ejeY="σ(k)" cero
                  curvas={[{ nombre: "Re σ máx.", x: c.k, y: c.reSigma }, { nombre: "Im σ", x: c.k, y: c.imSigma, estilo: "discontinua", color: PALETA[2] }]} />
                {c.dominio && <p className="adim-estudio-nota">Dominio de longitud {numero(c.dominio.longitud)}: {c.dominio.modosInestablesNeumann.length ? `modos inestables n = ${c.dominio.modosInestablesNeumann.map(m => m.n).join(", ")}` : "ningún modo admisible es inestable"} ({c.dominio.nota}).</p>}
              </div>
            ) : <Estado key={c.coordenada} estado="no_soportado" motivo={c.motivo} />)}
          </article>
        )) : <p className="adim-estudio-nota">{estabilidad.motivo}</p>)}
        {estabilidad?.estado === "calculado" && estabilidad.caja && <p className="adim-estudio-metodo">{estabilidad.motivo}. Caja de búsqueda: {estabilidad.caja.map(([a, b], i) => `${estabilidad.campos?.[i]} ∈ [${numero(a)}, ${numero(b)}]`).join(", ")}; puede haber estados fuera de ella.</p>}
      </section>

      <section className="adim-estudio-bloque">
        <h3>Continuación en un parámetro</h3>
        <p className="adim-estudio-nota">Sigue las ramas de estados homogeneos al variar un parámetro físico y localiza pliegues (puntos límite) y bifurcaciones de Hopf.</p>
        {parametros.length === 0 ? <p className="adim-estudio-nota">Da antes el valor de algún parámetro.</p> : (
          <form className="adim-form-linea" onSubmit={e => {
            e.preventDefault();
            const a = numeroDe(desde), b = numeroDe(hasta);
            if (a === null || b === null || !(a < b)) { setError("Indica un intervalo creciente."); return; }
            setError(""); continuar(pid, a, b, unidad);
          }}>
            <label>Parámetro<select value={pid} onChange={e => { setPid(e.target.value); setUnidad(parametros.find(p => p.id === e.target.value)?.unidad ?? ""); }}>{parametros.map(p => <option key={p.id} value={p.id}>{p.id}</option>)}</select></label>
            <label>Desde<input inputMode="decimal" value={desde} onChange={e => setDesde(e.target.value)} placeholder="p. ej. 0.5" /></label>
            <label>Hasta<input inputMode="decimal" value={hasta} onChange={e => setHasta(e.target.value)} placeholder="p. ej. 8" /></label>
            <label>Unidad<input value={unidad} onChange={e => setUnidad(e.target.value)} placeholder="la del parámetro" /></label>
            <button className="adim-button is-primary" type="submit" disabled={cargandoContinuacion}>{cargandoContinuacion ? "Continuando…" : "Continuar ramas"}</button>
          </form>
        )}
        {error && <p className="adim-input-error">{error}</p>}
        {continuacion && continuacion.estado !== "calculado" && <Estado estado={continuacion.estado} motivo={continuacion.motivo} />}
        {continuacion?.estado === "calculado" && <GraficoContinuacion c={continuacion} />}
      </section>
    </div>
  );
}

function GraficoContinuacion({ c }: { c: EstudioContinuacion }) {
  const campos = c.campos ?? [];
  const [campo, setCampo] = useState(campos[0]);
  const series: Serie[] = [];
  (c.ramas ?? []).forEach((rama, i) => {
    let tramo: typeof rama.puntos = [];
    const cerrar = () => {
      if (tramo.length > 1) series.push({ nombre: `rama ${i + 1} ${tramo[0].estable ? "estable" : "inestable"} ${series.length}`, x: tramo.map(p => p.p), y: tramo.map(p => p.u[campo]), color: PALETA[0], estilo: tramo[0].estable ? "linea" : "discontinua" });
    };
    for (const p of rama.puntos) {
      if (tramo.length && tramo[tramo.length - 1].estable !== p.estable) { tramo.push(p); cerrar(); tramo = [p]; } else tramo.push(p);
    }
    cerrar();
  });
  const marcas = (c.especiales ?? []).map(e => ({ x: e.p, y: e.u[campo], etiqueta: e.tipo === "pliegue" ? "pliegue" : "Hopf", color: e.tipo === "hopf" ? PALETA[1] : "#2d3928" }));
  return (
    <div>
      {campos.length > 1 && <div className="adim-pestanas-mini">{campos.map(x => <button key={x} type="button" aria-pressed={x === campo} onClick={() => setCampo(x)}><Simbolo id={x} /></button>)}</div>}
      <Grafica titulo="Diagrama de bifurcación" ejeX={`${c.parametroId} (SI)`} ejeY={campo} curvas={series} marcas={marcas} />
      <p className="adim-estudio-nota">Línea continua: estable; discontinua: inestable.</p>
      {(c.especiales ?? []).length > 0 && <ul className="adim-lista-especiales">{c.especiales!.map((e, i) => <li key={i}><strong>{e.tipo === "pliegue" ? "Pliegue" : "Hopf"}</strong> en {c.parametroId} = {numero(e.p, 6)} ({Object.entries(e.u).map(([k, v]) => `${k} = ${numero(v, 5)}`).join(", ")}){e.frecuencia ? `, frecuencia ${numero(e.frecuencia)}` : ""}</li>)}</ul>}
      <p className="adim-estudio-metodo">{c.motivo}.</p>
    </div>
  );
}
