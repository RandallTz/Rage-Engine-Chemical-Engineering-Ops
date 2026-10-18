"use client";

import { useState } from "react";
import type { ConfigExploracion, Documento } from "./contrato";
import { CONFIG_EXPLORACION, prepararExploracion, terminosExplorables, validarConfigExploracion } from "./exploracion";
import { latexExpresion } from "./exportar";
import { expresar } from "./documento";
import FormulaLatex from "../flowsheet/FormulaLatex";

type Props = {
  documento: Documento;
  guardar: (config: ConfigExploracion) => void;
  exportar: (nombre: string, texto: string) => void;
};
export default function ExploracionAutomatica({ documento, guardar, exportar }: Props) {
  const config = documento.exploracion ?? CONFIG_EXPLORACION;
  const [verPropuestas, setVerPropuestas] = useState(false);
  const [error, setError] = useState("");
  const terminos = terminosExplorables(documento.modelo);
  let solicitud: ReturnType<typeof prepararExploracion> | null = null;
  let pendiente = "";
  try { solicitud = prepararExploracion(documento, config); }
  catch (e) { pendiente = e instanceof Error ? e.message : String(e); }
  function cambiar(campo: keyof ConfigExploracion, valor: number | boolean) {
    const siguiente = { ...config, [campo]: valor };
    try { validarConfigExploracion(siguiente); guardar(siguiente); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  return <section className="adim-auto mb-8" aria-labelledby="adim-auto-titulo">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="mb-1 text-xs uppercase tracking-widest text-zinc-500">Exploración automática · preparación</p><h2 id="adim-auto-titulo" className="text-lg font-medium">Busca varias formulaciones</h2><p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-zinc-400">Incluye todos los términos aditivos explícitos y combina objetivos sin elegir una cinética o especie de referencia. El núcleo deberá resolver cada combinación y conservar las familias de escalas libres.</p></div>
      <span className="text-xs text-zinc-500">{terminos.length} términos detectados</span>
    </div>
    <div className="adim-auto-controls mt-5">
      <label>Presupuesto de propuestas<select value={config.presupuesto} onChange={e => cambiar("presupuesto", Number(e.target.value))}>{[20, 40, 100, 200].map(n => <option key={n} value={n}>{n} propuestas</option>)}{![20, 40, 100, 200].includes(config.presupuesto) && <option value={config.presupuesto}>{config.presupuesto} propuestas</option>}</select></label>
      <label>Objetivos simultáneos por propuesta<select value={config.maxObjetivos} onChange={e => cambiar("maxObjetivos", Number(e.target.value))}>{Array.from({ length: 8 }, (_, i) => i + 1).map(n => <option key={n} value={n}>Hasta {n}</option>)}</select></label>
      <label className="adim-auto-checkbox"><input type="checkbox" checked={config.respetarEscalasFijadas} onChange={e => cambiar("respetarEscalasFijadas", e.target.checked)} />Respetar mis escalas fijadas</label>
      <label className="adim-auto-checkbox"><input type="checkbox" checked={config.incluirGruposPi} onChange={e => cambiar("incluirGruposPi", e.target.checked)} />Pedir grupos Π y bases alternativas</label>
    </div>
    {!config.respetarEscalasFijadas && <p className="mt-3 text-xs text-amber-200">En esta solicitud se liberan las escalas activas fijadas; tus formas guardadas conservan sus valores. Las variables que decidiste mantener dimensionales se respetan.</p>}
    <details className="mt-4 text-xs text-zinc-400"><summary className="cursor-pointer">Alcance de los grupos y orden de exploración</summary><div className="mt-3 flex flex-wrap gap-4">
      <label className="grid gap-2">Cota absoluta de exponentes Π<select className="adim-auto-select" disabled={!config.incluirGruposPi} value={config.maxExponentePi} onChange={e => cambiar("maxExponentePi", Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}</select></label>
      <label className="grid gap-2">Denominador máximo de exponentes Π<select className="adim-auto-select" disabled={!config.incluirGruposPi} value={config.maxDenominadorPi} onChange={e => cambiar("maxDenominadorPi", Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}</select></label>
    </div><p className="mt-3 leading-relaxed">Primero se propone la forma sin nuevos objetivos; después, combinaciones por número de objetivos y orden del modelo. Si el presupuesto se agota, no se cubren las combinaciones restantes. Este orden es de presentación, sin prioridad física. Los productos con sumas internas no se desarrollan. Se conserva tu selección de variables a transformar, sin recorrer otros subconjuntos. Los objetivos manuales de la forma base también se conservan; el límite cuenta los objetivos nuevos.</p></details>
    {solicitud ? <p className="mt-4 text-sm"><strong className="font-medium">{solicitud.propuestas.length} propuestas sin evaluar</strong><span className="text-zinc-400"> de {solicitud.cobertura.combinacionesEnAlcance} combinaciones dentro de este alcance{solicitud.cobertura.limitadoPorPresupuesto ? " · presupuesto alcanzado" : " · inventario combinatorio cubierto"}.</span></p> : <p className="mt-4 text-sm text-zinc-400">{pendiente}</p>}
    <p className="mt-2 text-xs leading-relaxed text-zinc-400">Puede haber infinitas representaciones equivalentes. La búsqueda debe informar restricciones, duplicados y cobertura, sin presentar una lista finita como «todas las formas posibles».</p>
    <div className="mt-4 flex flex-wrap gap-2">
      <button className="adim-button" disabled={!solicitud} aria-expanded={verPropuestas} onClick={() => setVerPropuestas(!verPropuestas)}>{verPropuestas ? "Ocultar propuestas" : "Revisar propuestas automáticamente"}</button>
      <button className="adim-button" disabled={!solicitud} onClick={() => { if (solicitud) exportar("solicitud-exploracion-adimensional.json", JSON.stringify(solicitud, null, 2)); }}>Exportar solicitud al núcleo</button>
    </div>
    <p className="mt-3 text-xs text-zinc-500">Este preparador exporta propuestas sintácticas. Para calcular formulaciones usa «Adimensionalizar» en la vista principal: el núcleo recorre subconjuntos independientes y elimina duplicados. Los recuentos de propuestas y de formulaciones calculadas son distintos.</p>
    {error && <p role="alert" className="mt-3 text-sm text-amber-200">{error}</p>}
    {verPropuestas && solicitud && <div className="mt-5 grid gap-4">
      <details open><summary className="cursor-pointer text-sm">Términos incluidos ({terminos.length})</summary><div className="mt-3 grid gap-3">{terminos.map((t, i) => <div key={t.id} className="adim-auto-term"><span className="text-xs text-zinc-500">T{i + 1} · {t.ecuacionId} · {t.lado}</span><FormulaLatex latex={latexExpresion(t.expresion)} lectura={expresar(t.expresion)} /></div>)}</div></details>
      <div className="max-h-64 overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th className="pb-2">Propuesta</th><th className="pb-2">Coeficientes que se proponen unitarios en magnitud</th><th className="pb-2">Estado</th></tr></thead><tbody>{solicitud.propuestas.map((p, i) => <tr key={p.id} className="border-t border-zinc-700"><td className="py-2 pr-3">{i + 1}</td><td className="py-2 pr-3">{p.objetivos.map(o => `T${terminos.findIndex(t => t.id === o.terminoId) + 1}`).join(", ") || "Sin objetivos nuevos · escalas libres restantes"}</td><td className="py-2 text-zinc-500">Sin evaluar</td></tr>)}</tbody></table></div>
    </div>}
  </section>;
}
