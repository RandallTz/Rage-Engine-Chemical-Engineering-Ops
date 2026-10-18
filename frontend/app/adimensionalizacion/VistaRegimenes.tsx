"use client";

import type { ReactNode } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import type { EstudioAsintotica, EstudioEscalas } from "./contratoEstudio";
import { latexExpresion } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";
import { Estado, Simbolo, TerminoLatex, numero } from "./presentacionEstudio";

const LADO: Record<string, string> = { desde: "en el extremo inicial", hasta: "en el extremo final", ambos: "en ambos extremos (según las condiciones)", ninguno: "no forma capa (balance oscilatorio)" };

export default function VistaRegimenes({ f, asintotica, escalas }: { f: FormulacionNucleo; asintotica?: EstudioAsintotica; escalas?: EstudioEscalas }) {
  return (
    <div className="adim-estudio-vista">
      <section className="adim-estudio-bloque">
        <h3>Balanza dominante</h3>
        {!asintotica && <p className="adim-estudio-nota">Calcula con valores físicos para ver qué términos dominan.</p>}
        {asintotica && asintotica.estado !== "calculado" && <Estado estado={asintotica.estado} motivo={asintotica.motivo} />}
        {asintotica?.ecuaciones?.map(e => (
          <article key={e.id} className="adim-balance">
            <h4>{e.id}</h4>
            <div className="adim-balance-columnas">
              <div><p className="adim-etiqueta">Dominan a escala unidad</p><ul>{e.dominantes.map(t => <li key={t}><TerminoLatex f={f} id={t} /> <span className="is-num">{numero(e.magnitudes[t])}</span></li>)}</ul></div>
              <div><p className="adim-etiqueta">Despreciables (&lt; {numero(asintotica.umbral ?? 0.01)} del mayor)</p>{e.despreciables.length ? <ul>{e.despreciables.map(t => <li key={t}><TerminoLatex f={f} id={t} /> <span className="is-num">{numero(e.magnitudes[t])}</span></li>)}</ul> : <p className="adim-estudio-nota">Ninguno: todos los términos son del mismo orden.</p>}</div>
            </div>
            {e.reducida && (
              <div className="adim-reducida"><p className="adim-etiqueta">Problema reducido (exterior)</p><FormulaLatex bloque latex={`${latexExpresion(e.reducida.izquierda)} = ${latexExpresion(e.reducida.derecha)}`} lectura="Ecuación reducida" /></div>
            )}
            {e.espacial?.capa && (
              <div className={`adim-capa is-${e.espacial.capa.tipo}`}>
                {e.espacial.capa.tipo === "perturbacion_singular" ? <>
                  <p><strong>Perturbación singular.</strong> El término de mayor orden espacial es despreciable a escala unidad: la reducción baja el orden de {e.espacial.ordenMaximo} a {e.espacial.ordenReducido} y pierde {e.espacial.capa.condicionesPerdidas} {e.espacial.capa.condicionesPerdidas === 1 ? "condición" : "condiciones"} de frontera.</p>
                  {e.espacial.capa.espesor != null && <p>Hay una capa de espesor <strong>δ ≈ {numero(e.espacial.capa.espesor)}</strong> (en la coordenada adimensional) donde vuelve a dominar ese término{e.espacial.capa.balanceInterior?.length ? ", con el balance interior:" : "."}</p>}
                  {e.espacial.capa.balanceInterior && <ul className="adim-chips">{e.espacial.capa.balanceInterior.map(t => <li key={t}><TerminoLatex f={f} id={t} /></li>)}</ul>}
                  {e.espacial.capa.ubicacion && <p>Ubicación: <strong>{LADO[e.espacial.capa.ubicacion.lado]}</strong>{e.espacial.capa.ubicacion.en && <> (<Simbolo id={e.espacial.capa.ubicacion.en.variableId} /> = {numero(e.espacial.capa.ubicacion.en.valor)})</>}. <small>{e.espacial.capa.ubicacion.criterio}.</small></p>}
                  {!e.espacial.capa.ubicacion && <p className="adim-estudio-nota">La ubicación solo se publica cuando el balance interior es lineal con coeficientes constantes.</p>}
                </> : <p>{e.espacial.capa.nota}</p>}
              </div>
            )}
            {e.espacial && e.espacial.balances.length > 0 && (
              <details className="adim-detalle"><summary>Balances distinguidos a escalas menores</summary>
                <ul>{e.espacial.balances.map((b, i) => <li key={i}>δ ≈ {numero(b.delta)}: {b.terminos.map(t => <TerminoLatex key={t} f={f} id={t} />).reduce<ReactNode[]>((a, x, j) => j ? [...a, " ~ ", x] : [x], [])}</li>)}</ul>
              </details>
            )}
            {e.temporal?.capaInicial && <div className="adim-capa"><p><strong>Capa inicial.</strong> La acumulación es despreciable a escala unidad: tras un transitorio de duración ≈ {numero(e.temporal.capaInicial.duracion)} el campo sigue el balance cuasiestacionario.</p></div>}
          </article>
        ))}
        {asintotica?.estado === "calculado" && <p className="adim-estudio-metodo">{asintotica.motivo}. Identifica escalas y balances; no resuelve la ecuación.</p>}
      </section>

      <section className="adim-estudio-bloque">
        <h3>Escalas, malla y rigidez</h3>
        {!escalas && <p className="adim-estudio-nota">Calcula con valores físicos para ver tiempos característicos y requisitos de malla.</p>}
        {escalas && escalas.estado !== "calculado" && <Estado estado={escalas.estado} motivo={escalas.motivo} />}
        {escalas?.estado === "calculado" && <>
          <p className="adim-estudio-nota">Linealización en el {escalas.referencia?.origen}{escalas.referencia && <>: {Object.entries(escalas.referencia.u).map(([c, v]) => `${c} = ${numero(v)}`).join(", ")}</>}. Tiempo de reacción: {numero(escalas.tiempos?.reaccion)}.</p>
          {escalas.coordenadas?.map(c => c.estado === "calculado" ? (
            <div key={c.coordenada} className="adim-tabla-scroll">
              <table className="adim-tabla">
                <caption>Coordenada <Simbolo id={c.coordenada} /></caption>
                <tbody>
                  <tr><th>Difusividad efectiva</th><td className="is-num">{numero(c.difusividad)}</td><th>Velocidad efectiva</th><td className="is-num">{numero(c.velocidad)}</td></tr>
                  <tr><th>Tiempo de difusión</th><td className="is-num">{numero(c.tiempoDifusion)}</td><th>Tiempo de convección</th><td className="is-num">{numero(c.tiempoConveccion)}</td></tr>
                  {c.longitudesInternas.map(l => <tr key={l.balance}><th>Longitud interna ({l.balance})</th><td className="is-num" colSpan={3}>{numero(l.longitud)}</td></tr>)}
                  {c.malla && <tr><th>Nodos recomendados</th><td className="is-num"><strong>{c.malla.nodosRecomendados}</strong></td><th>Péclet de celda</th><td className="is-num">{numero(c.malla.pecletCelda)}</td></tr>}
                  {c.pasoExplicitoMaximo && <tr><th>Paso explícito máximo</th><td className="is-num">{numero(c.pasoExplicitoMaximo.eulerExplicito)}</td><th>Limitado por</th><td>{Object.entries(c.pasoExplicitoMaximo.porMecanismo).sort((a, b) => a[1] - b[1])[0][0]}</td></tr>}
                  {c.rigidez && <tr><th>Rigidez (cociente de autovalores)</th><td className="is-num">{numero(c.rigidez.cociente)}</td><th>Integrador</th><td>{c.rigidez.recomendacion}</td></tr>}
                </tbody>
              </table>
              {c.malla && <p className="adim-estudio-nota">{c.malla.criterio}.</p>}
              {c.rigidez && <p className="adim-estudio-nota">{c.rigidez.nota} ({c.rigidez.nodos} nodos).</p>}
            </div>
          ) : <Estado key={c.coordenada} estado="no_soportado" motivo={`${c.coordenada}: ${c.motivo}`} />)}
          <p className="adim-estudio-metodo">{escalas.motivo}.</p>
        </>}
      </section>
    </div>
  );
}
