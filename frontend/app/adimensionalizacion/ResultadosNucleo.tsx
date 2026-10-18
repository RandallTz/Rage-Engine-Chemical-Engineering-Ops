"use client";

import { useCallback, useEffect, useState } from "react";
import type { Modelo } from "./contrato";
import type { FormulacionNucleo, RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";
import type { ResultadosEstudio } from "./contratoEstudio";
import { formulacionesDe } from "./lecturaNucleo";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";
import DesgloseMatematico from "./DesgloseMatematico";
import EstudioFormulacion from "./EstudioFormulacion";
import ComparadorFormulaciones from "./ComparadorFormulaciones";
import { abrirInforme, generarInforme } from "./informe";
import { useValores } from "./usoEstudio";
import styles from "../motor/trabajoMotor.module.css";

export type VistaResultado = "resultado" | "estudio" | "desarrollo" | "comparar";

function latexDefinicionFuncion(fn: NonNullable<FormulacionNucleo["funcionesAdimensionales"]>[number]): string {
  const argsTex = fn.argumentos.map((a, i) => a.extraida ? `${latexExpresion(a.escala)}\\,w_{${i + 1}}` : `w_{${i + 1}}`).join(", ");
  const wArgs = fn.argumentos.map((_, i) => `w_{${i + 1}}`).join(", ");
  return `${nombreLatex(fn.nombre)}\\left(${wArgs}\\right) = \\frac{${nombreLatex(fn.funcionId)}\\left(${argsTex}\\right)}{${nombreLatex(fn.escalaId)}}`;
}

function relacion(r: FormulacionNucleo["restricciones"][number]): string {
  const e = latexExpresion(r.expresion);
  if (r.tipo === "positivo") return `${e} > 0`;
  if (r.tipo === "negativo") return `${e} < 0`;
  if (r.tipo === "no_nulo") return `${e} \\ne 0`;
  if (r.tipo === "igualdad" && r.valor) return `${e} = ${latexExpresion(r.valor)}`;
  return e;
}

const TITULOS: Record<VistaResultado, string> = { resultado: "Formulaciones", estudio: "Estudio", desarrollo: "Desarrollo", comparar: "Comparar formulaciones" };

export default function ResultadosNucleo({ respuesta, solicitud, modelo, documentoId, continuar, exportar, nombreModelo = "Modelo", vista, ir }: {
  respuesta: RespuestaNucleo; solicitud: SolicitudNucleo; modelo: Modelo; documentoId: string;
  continuar: () => void; exportar: (indice: number, tipo: "json" | "latex") => void; nombreModelo?: string;
  vista: VistaResultado; ir: (v: VistaResultado) => void;
}) {
  const formas = formulacionesDe(respuesta);
  const [indice, setIndice] = useState(() => formas.reduce((mejor, f, i) => f.libres.length < formas[mejor].libres.length ? i : mejor, 0));
  const [copiado, setCopiado] = useState<number | null>(null);
  const [valores, setValores] = useValores(documentoId);
  const [estudios, setEstudios] = useState<Record<number, ResultadosEstudio>>({});
  const seleccion = Math.min(indice, formas.length - 1), f = formas[seleccion];
  const cobertura = respuesta.cobertura;
  const guardarEstudio = useCallback((r: ResultadosEstudio) => setEstudios(e => ({ ...e, [seleccion]: r })), [seleccion]);

  useEffect(() => { window.scrollTo({ top: 0, behavior: "smooth" }); }, [vista]);

  function copiar(i: number, latex: string) {
    navigator.clipboard?.writeText(latex).then(() => { setCopiado(i); setTimeout(() => setCopiado(null), 1800); });
  }

  const selector = formas.length > 1 && vista !== "comparar" && (
    <nav className={`${styles.tabs} adim-formas-tabs`} aria-label="Formulaciones calculadas">
      {formas.map((forma, i) => (
        <button key={`${i}:${forma.id}`} type="button" aria-pressed={seleccion === i} onClick={() => setIndice(i)}>
          Forma {i + 1} <small>{forma.libres.length ? `${forma.libres.length} libre${forma.libres.length > 1 ? "s" : ""}` : "determinada"}{forma.equivalencia.estado !== "demostrada" ? " · sin certificado" : ""}</small>
        </button>
      ))}
    </nav>
  );

  return <section aria-label="Resultados calculados">
    <header className={styles.heading}>
      <div><span className={styles.eyebrow}>{nombreModelo}</span><h1>{TITULOS[vista]}</h1></div>
      {f && vista !== "comparar" && <details className="adim-menu">
        <summary className={styles.secondary}>Exportar</summary>
        <div className="adim-menu-lista">
          <button type="button" onClick={() => abrirInforme(generarInforme({ nombre: nombreModelo, modelo, f, indice: seleccion, respuesta, estudio: estudios[seleccion] }), `informe-forma-${seleccion + 1}.html`)}>Informe imprimible (HTML / PDF)</button>
          <button type="button" onClick={() => exportar(seleccion, "latex")}>Desarrollo en LaTeX (.tex)</button>
          <button type="button" onClick={() => exportar(seleccion, "json")}>Solicitud y respuesta (JSON)</button>
        </div>
      </details>}
    </header>
    {respuesta.diagnosticos.length > 0 && <div className={styles.notice} role="status"><span>{respuesta.diagnosticos.map(d => d.mensaje).join(" · ")}</span></div>}
    {!f && <div className={styles.empty}><h2>Sin formulaciones</h2><span>El núcleo no devolvió ninguna formulación para este modelo.</span></div>}
    {f && selector}

    {f && vista === "resultado" && (
      <div className={styles.solveLayout}>
        <section className="adim-pagina">
          <div className="adim-ecuaciones-finales">
            <h2>{f.normalizacion.estado === "completa" ? (f.ecuaciones.length > 1 ? "Sistema adimensional" : "Ecuación adimensional") : (f.ecuaciones.length > 1 ? "Sistema transformado" : "Ecuación transformada")}</h2>
            {f.ecuaciones.map((e, i) => {
              const latex = `${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`;
              return (
                <div className="adim-final-equation" key={e.igualdad.id}>
                  <div className="adim-equation-header-bar">
                    <span className="adim-equation-num">({i + 1})</span>
                    <button type="button" className={`adim-copy-btn ${copiado === i ? "is-copied" : ""}`} onClick={() => copiar(i, latex)}>{copiado === i ? "Copiado" : "Copiar LaTeX"}</button>
                  </div>
                  <div className="adim-equation-body">
                    <FormulaLatex bloque latex={latex} lectura={`Ecuación transformada ${i + 1}`} />
                    {e.factorGlobal && (e.factorGlobal.tipo !== "numero" || e.factorGlobal.valor !== 1) && (
                      <div className="adim-equation-factor-badge"><span>Dividida por el factor global</span><FormulaLatex latex={latexExpresion(e.factorGlobal)} lectura="Factor global" /></div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {f.grupos.length > 0 && (
            <div className={styles.variables}>
              <h2>Grupos</h2>
              {f.grupos.map(g => (
                <div className="adim-fila" key={g.id}>
                  <FormulaLatex latex={nombreLatex(g.id)} lectura={g.id} />
                  <FormulaLatex latex={latexExpresion(g.definicion)} lectura={`Grupo ${g.id}`} />
                  <small>{g.adimensional ? "adimensional" : "con dimensión"}{g.interno ? " · interno" : ""}{g.contieneEscalasLibres ? " · usa escalas libres" : ""}</small>
                </div>
              ))}
            </div>
          )}

          <details className={styles.settings}>
            <summary>Detalles técnicos</summary>
            <div className="adim-detalles">
              <h3>Cambios de variable</h3>
              {[...f.directa, ...f.inversa].map((m, i) => <FormulaLatex key={i} bloque latex={`${nombreLatex(m.simboloId)} = ${latexExpresion(m.expresion)}`} lectura={`Mapa de ${m.simboloId}`} />)}
              {f.funcionesAdimensionales && f.funcionesAdimensionales.length > 0 && <>
                <h3>Funciones con escala declarada</h3>
                {f.funcionesAdimensionales.map(fn => <FormulaLatex key={fn.id} bloque latex={latexDefinicionFuncion(fn)} lectura={fn.definicion} />)}
              </>}
              {f.objetivos.length > 0 && <>
                <h3>Objetivos de normalización</h3>
                <ul className="adim-lista-simple">{f.objetivos.map(o => <li key={o.id}><strong>{o.estado}</strong> · {o.motivo}</li>)}</ul>
              </>}
              {f.restricciones.length > 0 && <>
                <h3>Restricciones de validez</h3>
                <ul className="adim-lista-simple">{f.restricciones.map(r => <li key={r.id}><FormulaLatex latex={relacion(r)} lectura={r.motivo} /> <small>{r.motivo}</small></li>)}</ul>
              </>}
              {f.dominios.length > 0 && <>
                <h3>Dominios</h3>
                {f.dominios.map(d => <FormulaLatex key={d.id} bloque latex={`${latexExpresion(d.desde)} \\le ${nombreLatex(d.variableId)} \\le ${latexExpresion(d.hasta)}`} lectura={d.id} />)}
              </>}
              {f.condiciones.length > 0 && <>
                <h3>Condiciones</h3>
                {f.condiciones.map(c => (
                  <div key={c.id} className="adim-condicion">
                    <p className="adim-etiqueta">{c.tipo} · {c.lugar ? <FormulaLatex latex={`${nombreLatex(c.lugar.variableId)} = ${latexExpresion(c.lugar.valor)}`} lectura={`Ubicación de ${c.id}`} /> : c.ubicacion}</p>
                    <FormulaLatex bloque latex={`${latexExpresion(c.ecuacion.izquierda)} = ${latexExpresion(c.ecuacion.derecha)}`} lectura={c.id} />
                  </div>
                ))}
              </>}
              {respuesta.gruposPi && <>
                <h3>Teorema Π del sistema</h3>
                <p>Rango dimensional {respuesta.gruposPi.rango} · {respuesta.gruposPi.numeroGrupos} {respuesta.gruposPi.numeroGrupos === 1 ? "grupo independiente" : "grupos independientes"}. {String(respuesta.gruposPi.cobertura.nota ?? "")}</p>
                {respuesta.gruposPi.bases.map(b => (
                  <div key={b.id}><p className="adim-etiqueta">Base {b.id}</p>{b.grupos.map(g => <FormulaLatex key={g.id} bloque latex={`${nombreLatex(g.id)} = ${latexExpresion(g.definicion)}`} lectura={`Grupo ${g.id}`} />)}</div>
                ))}
              </>}
              {cobertura && <>
                <h3>Cobertura de la búsqueda</h3>
                <p>{cobertura.familia}. Evaluadas {cobertura.evaluados ?? 0} · distintas {cobertura.formulacionesDistintas} · {cobertura.completa ? "completa para esta familia" : `limitada${cobertura.agotado ? ` por ${cobertura.agotado}` : ""}`}.</p>
                {cobertura.excluidos?.map((x, i) => <p key={i}>{x.terminoId}: {x.motivo}</p>)}
              </>}
              <h3>¿Por qué hay varias formulaciones?</h3>
              <p>Son el mismo modelo con escalas distintas: cada una deja en 1 un conjunto independiente de coeficientes. Ninguna es «la correcta»; conviene la que deja en 1 los términos que dominan en tu régimen, y eso lo evalúa el Estudio con tus valores.</p>
            </div>
          </details>
        </section>
        <aside className={styles.solveAside}>
          <div className={styles.counts}>
            <div><span>Formulaciones</span><strong>{formas.length}</strong></div>
            <div><span>Grupos</span><strong>{f.grupos.length}</strong></div>
            <div><span>Escalas libres</span><strong>{f.libres.length}</strong></div>
            <div><span>Equivalencia</span><strong className="adim-cifra-texto">{f.equivalencia.estado === "demostrada" ? "Demostrada" : "Sin demostrar"}</strong></div>
          </div>
          <p className="adim-aside-nota">{f.libres.length ? `Escalas que eliges tú: ${f.libres.join(", ")}.` : "Todas las escalas están determinadas."}{f.normalizacion.estado !== "completa" ? " Normalización parcial." : ""}</p>
          {cobertura?.excluidos?.some(x => x.motivo.includes("signo")) && <p className="adim-aside-nota">Hay normalizaciones pendientes porque falta el signo de algunos parámetros (Ecuaciones → Opciones avanzadas).</p>}
          <button type="button" className={styles.primary} onClick={() => ir("estudio")}>Estudiar esta forma</button>
          {cobertura?.siguiente !== null && cobertura?.siguiente !== undefined && <button type="button" className="adim-enlace adim-aside-enlace" onClick={continuar}>Buscar más formulaciones →</button>}
        </aside>
      </div>
    )}
    {f && vista === "estudio" && <EstudioFormulacion key={seleccion} base={solicitud} f={f} modelo={modelo} nombreModelo={nombreModelo} valores={valores} setValores={setValores} alCalcular={guardarEstudio} />}
    {f && vista === "desarrollo" && <DesgloseMatematico resultado={f} />}
    {f && vista === "comparar" && <ComparadorFormulaciones base={solicitud} formas={formas} modelo={modelo} valores={valores} inicial={seleccion} />}
  </section>;
}
