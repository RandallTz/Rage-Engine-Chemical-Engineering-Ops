"use client";

import { useEffect, useReducer, useState } from "react";
import type { ReactNode } from "react";
import type { ConfigExploracion, Documento, Escala } from "./contrato";
import { CLAVE_ALMACEN, LIMITE_BYTES, crearDocumento, duplicarForma, editarModelo, expresar, leerDocumento, migrarDocumentoV2 } from "./documento";
import { dimensionLatex, escalaLatex, exportarLatex, latexExpresion, nombreLatex } from "./exportar";
import { CONFIG_EXPLORACION, validarConfigExploracion } from "./exploracion";
import FormulaLatex from "../flowsheet/FormulaLatex";
import EntradaSimple from "./EntradaSimple";
import { igualdadProfunda } from "./lecturaNucleo";
import styles from "../motor/trabajoMotor.module.css";

type Historia = { contador: number; actual: Documento | null; antes: Documento[]; despues: Documento[] };
type Accion = { tipo: "abrir" | "editar"; documento: Documento } | { tipo: "deshacer" | "rehacer" };
function historial(h: Historia, a: Accion): Historia {
  if (a.tipo === "abrir") return { contador: h.contador + 1, actual: a.documento, antes: [], despues: [] };
  if (a.tipo === "editar") return { contador: h.contador + 1, actual: a.documento, antes: h.actual ? [...h.antes.slice(-49), h.actual] : [], despues: [] };
  if (a.tipo === "deshacer" && h.actual && h.antes.length) return { contador: h.contador + 1, actual: h.antes.at(-1)!, antes: h.antes.slice(0, -1), despues: [h.actual, ...h.despues] };
  if (a.tipo === "rehacer" && h.actual && h.despues.length) return { contador: h.contador + 1, actual: h.despues[0], antes: [...h.antes, h.actual], despues: h.despues.slice(1) };
  return h;
}
function descargar(nombre: string, texto: string, tipo = "application/json") {
  const url = URL.createObjectURL(new Blob([texto], { type: tipo }));
  const a = document.createElement("a"); a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function dimensionTexto(d: Escala["dimension"]) {
  if (d === null) return "Pendiente";
  return Object.entries(d).filter(([, r]) => r.n !== 0).map(([k, r]) => r.d === 1 ? (r.n === 1 ? k : `${k}^${r.n}`) : `${k}^(${r.n}/${r.d})`).join(" ") || "1";
}
function escalaTexto(e: Escala) {
  if (!e.transformar) return "Conservar dimensional";
  return e.valor.tipo === "libre" ? "Libre" : e.valor.tipo === "cantidad" ? `${e.valor.valor} ${e.valor.unidad}` : expresar(e.valor.expresion);
}

/** Una fila por variable: transformar o no, y fijar su escala o dejarla libre. */
function EntradaEscala({ escala, cambiar }: { escala: Escala; cambiar: (e: Escala) => void }) {
  const [texto, setTexto] = useState(escala.valor.tipo === "cantidad" ? String(escala.valor.valor) : "");
  const [unidad, setUnidad] = useState(escala.valor.tipo === "cantidad" ? escala.valor.unidad : "");
  const [error, setError] = useState("");
  const aplicar = () => {
    const valor = Number(texto);
    if (!texto || !Number.isFinite(valor) || valor <= 0 || !unidad.trim()) { setError("Indica un valor finito positivo y su unidad."); return; }
    if (["°C", "degC", "°F", "degF"].includes(unidad.trim())) { setError("Usa una diferencia de temperatura o una escala absoluta; °C y °F son afines."); return; }
    setError(""); cambiar({ ...escala, valor: { tipo: "cantidad", valor, unidad: unidad.trim() } });
  };
  return <div className={styles.field}>
    <FormulaLatex latex={nombreLatex(escala.simboloId)} lectura={escala.simboloId} />
    <label><input type="checkbox" checked={escala.transformar} onChange={e => cambiar({ ...escala, transformar: e.target.checked })} /> Transformar<small className={styles.fieldRole}><FormulaLatex latex={escalaLatex(escala)} lectura={escalaTexto(escala)} /></small></label>
    <span className="adim-valor-campos">
      <input aria-label={`Escala de ${escala.simboloId}`} inputMode="decimal" placeholder="libre" value={texto} disabled={!escala.transformar} onChange={e => setTexto(e.target.value)} onBlur={() => { if (texto.trim()) aplicar(); else if (escala.valor.tipo !== "libre") cambiar({ ...escala, valor: { tipo: "libre" } }); }} />
      <input aria-label={`Unidad de la escala de ${escala.simboloId}`} placeholder={dimensionTexto(escala.dimension)} value={unidad} disabled={!escala.transformar} onChange={e => setUnidad(e.target.value)} onBlur={() => { if (texto.trim()) aplicar(); }} />
    </span>
    {error && <span className={styles.fieldError} role="alert">{error}</span>}
  </div>;
}

export default function Editor({ inicial, guardar, textoInicial, guardarTexto, volver, barra, derivadaDe }: {
  inicial?: Documento; guardar?: (doc: Documento) => void; textoInicial?: string | null; guardarTexto?: (texto: string) => void; volver?: () => void; barra?: ReactNode;
  /** Hoja del Engine de la que se derivaron las ecuaciones: el modelo no se edita aquí (principio 10). */
  derivadaDe?: { hojaId: string; nombre: string };
}) {
  const [h, dispatch] = useReducer(historial, { contador: 0, actual: inicial ?? null, antes: [], despues: [] });
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<string | null>(null);
  useEffect(() => {
    if (inicial) return;
    const apertura = setTimeout(() => {
      try { const texto = localStorage.getItem(CLAVE_ALMACEN); dispatch({ tipo: "abrir", documento: texto ? migrarDocumentoV2(leerDocumento(texto)) : crearDocumento() }); }
      catch (e) { setError(`No se pudo abrir el documento guardado: ${e instanceof Error ? e.message : String(e)}`); dispatch({ tipo: "abrir", documento: crearDocumento() }); }
    }, 0);
    return () => clearTimeout(apertura);
  }, [inicial]);
  useEffect(() => {
    if (!h.actual || h.contador === 0) return;
    if (guardar) { guardar(h.actual); return; }
    const t = setTimeout(() => { try { localStorage.setItem(CLAVE_ALMACEN, JSON.stringify(h.actual)); } catch { setError("No se pudo guardar. Exporta el documento para conservarlo."); } }, 200);
    return () => clearTimeout(t);
  }, [h.actual, h.contador, guardar]);
  const doc = h.actual;
  function ejecutar(fn: () => Documento) {
    try { dispatch({ tipo: "editar", documento: leerDocumento(JSON.stringify(fn())) }); setError(""); return true; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return false; }
  }
  const forma = doc?.formas.find(f => f.id === doc.activaId);
  const config = doc?.exploracion ?? CONFIG_EXPLORACION;
  function cambiarBusqueda(campo: keyof ConfigExploracion, valor: number | boolean) {
    if (!doc) return;
    const siguiente = { ...config, [campo]: valor };
    try { validarConfigExploracion(siguiente); ejecutar(() => ({ ...doc, exploracion: siguiente })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  const cambiarForma = (cambios: Partial<NonNullable<typeof forma>>) => doc && forma && ejecutar(() => ({ ...doc, formas: doc.formas.map(f => f.id === forma.id ? { ...f, ...cambios } : f) }));

  const avanzado = doc && forma && <details className={styles.settings}>
    <summary>Opciones avanzadas</summary>
    <div className="adim-avanzado">
      <div className="adim-avanzado-acciones">
        <button type="button" disabled={!h.antes.length || editor !== null} onClick={() => dispatch({ tipo: "deshacer" })}>Deshacer</button>
        <button type="button" disabled={!h.despues.length || editor !== null} onClick={() => dispatch({ tipo: "rehacer" })}>Rehacer</button>
        <button type="button" onClick={() => descargar("adimensionalizacion.json", JSON.stringify(doc, null, 2))}>Exportar documento</button>
        <label>Importar documento<input className="sr-only" type="file" accept=".json,application/json" onChange={async e => { const f = e.target.files?.[0]; e.target.value = ""; if (!f) return; try { if (f.size > LIMITE_BYTES) throw new Error("El documento supera 1 MB."); const d = migrarDocumentoV2(leerDocumento(await f.text())); ejecutar(() => ({ ...d, id: doc.id })); } catch (err) { setError(err instanceof Error ? err.message : String(err)); } }} /></label>
        <button type="button" disabled={!doc.modelo.ecuaciones.length} onClick={() => descargar("modelo-original.tex", exportarLatex(doc), "text/plain")}>Modelo en LaTeX</button>
      </div>

      <details><summary>Búsqueda de formulaciones</summary>
        <label>Presupuesto de propuestas<select value={config.presupuesto} onChange={e => cambiarBusqueda("presupuesto", Number(e.target.value))}>{[...new Set([20, 40, 100, 200, config.presupuesto])].sort((a, b) => a - b).map(n => <option key={n} value={n}>{n}</option>)}</select></label>
        <label className="adim-casilla"><input type="checkbox" checked={config.incluirGruposPi} onChange={e => cambiarBusqueda("incluirGruposPi", e.target.checked)} /> Calcular los grupos Π del sistema y bases alternativas</label>
        {config.incluirGruposPi && <label>Exponente máximo de los grupos Π<select value={config.maxExponentePi} onChange={e => cambiarBusqueda("maxExponentePi", Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}</select></label>}
      </details>

      <details><summary>Escalas fijadas por ti ({forma.escalas.filter(e => e.valor.tipo !== "libre" || !e.transformar).length})</summary>
        <p>Opcional. Una escala vacía queda libre y la elige la búsqueda; desmarcar «Transformar» conserva la variable con sus unidades.</p>
        <div className={styles.variables}>{forma.escalas.map(escala => <EntradaEscala key={`${doc.id}:${forma.id}:${escala.simboloId}:${JSON.stringify(escala.valor)}:${escala.transformar}`} escala={escala}
          cambiar={nuevo => cambiarForma({ escalas: forma.escalas.map(e => e.simboloId === nuevo.simboloId ? nuevo : e) })} />)}</div>
        <label>Prioridad al despejar escalas<input placeholder="p. ej. x, t" defaultValue={(forma.prioridadEscalas ?? []).join(", ")} onBlur={e => { const vals = e.target.value.split(",").map(s => s.trim()).filter(Boolean); cambiarForma({ prioridadEscalas: vals.length ? vals : undefined }); }} /></label>
        <label>Términos por los que se divide cada ecuación<input placeholder="p. ej. balance:derecha#2" defaultValue={(forma.referencias ?? []).map(r => r.terminoId).join(", ")} onBlur={e => { const vals = e.target.value.split(",").map(s => s.trim()).filter(Boolean); cambiarForma({ referencias: vals.length ? vals.map(tid => ({ ecuacionId: tid.includes(":") ? tid.split(":")[0] : tid, terminoId: tid })) : undefined }); }} /></label>
        <div className="adim-avanzado-acciones">
          {doc.formas.length > 1 && <select aria-label="Forma activa" value={forma.id} onChange={e => ejecutar(() => ({ ...doc, activaId: e.target.value }))}>{doc.formas.map(f => <option key={f.id} value={f.id}>{f.nombre}{f.modeloRevision !== doc.modelo.revision ? " · desactualizada" : ""}</option>)}</select>}
          <button type="button" onClick={() => ejecutar(() => duplicarForma(doc))}>Guardar como alternativa</button>
          {forma.modeloRevision !== doc.modelo.revision && <button type="button" onClick={() => cambiarForma({ modeloRevision: doc.modelo.revision })}>Confirmar revisión de esta forma</button>}
        </div>
      </details>

      <details><summary>Signos de los parámetros</summary>
        <p>Si se desconoce el signo de un parámetro, la búsqueda no normaliza con él. Nada se supone positivo.</p>
        <div className={styles.variables}>{doc.modelo.simbolos.filter(s => s.rol === "parametro" || s.rol === "constante").map(s => <div key={s.id} className={styles.field}>
          <FormulaLatex latex={nombreLatex(s.nombre)} lectura={s.nombre} />
          <label htmlFor={`signo-${s.id}`}>{s.unidad ?? "sin unidad"}<small className={styles.fieldRole}><FormulaLatex latex={dimensionLatex(s.dimension)} lectura={dimensionTexto(s.dimension)} /></small></label>
          <select id={`signo-${s.id}`} value={s.signo} onChange={e => ejecutar(() => editarModelo(doc, { ...doc.modelo, simbolos: doc.modelo.simbolos.map(v => v.id === s.id ? { ...v, signo: e.target.value as typeof s.signo } : v) }))}><option value="desconocido">Signo desconocido</option><option value="positivo">Positivo</option><option value="negativo">Negativo</option><option value="cero">Cero</option></select>
        </div>)}</div>
      </details>

      <details><summary>Dominios y condiciones ({doc.modelo.dominios.length + doc.modelo.condiciones.length})</summary>
        {!doc.modelo.dominios.length && !doc.modelo.condiciones.length && <p>Sin dominios ni condiciones. Se declaran en la edición estructurada.</p>}
        {doc.modelo.dominios.map(d => <FormulaLatex key={d.id} bloque latex={`${latexExpresion(d.desde)} \\le ${nombreLatex(d.variableId)} \\le ${latexExpresion(d.hasta)}`} lectura={`${expresar(d.desde)} ≤ ${d.variableId} ≤ ${expresar(d.hasta)}`} />)}
        {doc.modelo.condiciones.map(c => {
          const dom = doc.modelo.dominios.find(d => d.id === c.dominioId);
          return <div key={c.id} className="adim-condicion">
            <p className="adim-etiqueta">{c.tipo}{dom && c.tipo !== "inicial" && <> · <select aria-label={`Extremo de ${c.id}`} disabled={!!derivadaDe} value={c.ubicacion?.extremo ?? ""} onChange={e => {
              const ext = e.target.value as "desde" | "hasta" | "";
              ejecutar(() => editarModelo(doc, { ...doc.modelo, condiciones: doc.modelo.condiciones.map(item => item.id === c.id ? { ...item, ubicacion: ext ? { variableId: dom.variableId, extremo: ext } : undefined } : item) }));
            }}><option value="">extremo sin indicar</option><option value="desde">en {expresar(dom.desde)}</option><option value="hasta">en {expresar(dom.hasta)}</option></select></>}</p>
            <FormulaLatex bloque latex={`${latexExpresion(c.ecuacion.izquierda)} = ${latexExpresion(c.ecuacion.derecha)}`} lectura={`${expresar(c.ecuacion.izquierda)} = ${expresar(c.ecuacion.derecha)}`} />
          </div>;
        })}
      </details>

      <details><summary>Edición estructurada (JSON)</summary>
        <p>Para declarar dominios, condiciones, objetivos o cambios de variable no lineales. Guardar el modelo incrementa su revisión.</p>
        <div className="adim-avanzado-acciones">
          {!derivadaDe && <button type="button" onClick={() => setEditor(JSON.stringify(doc.modelo, null, 2))}>Editar el modelo</button>}
          <button type="button" onClick={() => setEditor(JSON.stringify({ ...forma, transformaciones: forma.transformaciones ?? [] }, null, 2))}>Editar objetivos y mapas</button>
        </div>
        {editor !== null && <>
          <textarea spellCheck={false} className="adim-json" aria-label="JSON del modelo o de la forma" value={editor} onChange={e => setEditor(e.target.value)} />
          <div className="adim-avanzado-acciones">
            <button type="button" onClick={() => { try { const valor = JSON.parse(editor); let siguiente: Documento; if (Object.hasOwn(valor, "ecuaciones")) siguiente = editarModelo(doc, valor); else { if (valor.id !== forma.id || valor.padreId !== forma.padreId || valor.modeloRevision !== forma.modeloRevision) throw new Error("No cambies identidad, ascendencia ni revisión desde el editor de forma."); siguiente = leerDocumento(JSON.stringify({ ...doc, formas: doc.formas.map(f => f.id === forma.id ? valor : f) })); } if (ejecutar(() => siguiente)) setEditor(null); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } }}>Validar y guardar</button>
            <button type="button" onClick={() => setEditor(null)}>Cancelar</button>
          </div>
        </>}
      </details>
    </div>
  </details>;

  return <div className="adim adim-hoja">
    {error && <div role="alert" className={styles.error}>{error}<button aria-label="Cerrar aviso" onClick={() => setError("")}>×</button></div>}
    {doc && <EntradaSimple key={`${doc.id}:${doc.modelo.id}`} documento={doc} revisionVista={h.contador} textoInicial={textoInicial} guardarTexto={guardarTexto} volver={volver} barra={barra} avanzado={avanzado} derivadaDe={derivadaDe}
      procesar={modelo => {
        try {
          if (igualdadProfunda(modelo, doc.modelo)) return doc;
          const siguiente = editarModelo({ ...doc, formas: doc.formas.map(f => ({ ...f, objetivos: [] })) }, modelo);
          return ejecutar(() => siguiente) ? siguiente : null;
        } catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; }
      }} />}
  </div>;
}
