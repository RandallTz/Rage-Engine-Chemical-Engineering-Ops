import type { ExpresionDePaso, ResultadoNucleo } from "./contrato";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";

function latexPaso(e: ExpresionDePaso): string {
  return e.tipo === "expresion" ? latexExpresion(e.expresion) : `${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`;
}
/** Presenta la traza en el orden recibido. No inventa pasos ni certifica álgebra. */
export default function DesgloseMatematico({ resultado }: { resultado: ResultadoNucleo | null }) {
  const pasos = resultado?.desarrollo ?? [];
  return <section className="adim-development" aria-label="Desarrollo matemático y algebraico">
    {!resultado ? <p className="adim-development-pending">Pendiente del núcleo matemático. Aquí se mostrará la derivación completa de cada formulación, desde el modelo original hasta sus grupos y la comprobación inversa.</p> : <>
      {!resultado.desarrollo && <p className="adim-development-pending">Traza básica recibida; el desglose detallado no está incluido en esta respuesta.</p>}
      <ol className="adim-development-steps">{pasos.map((p, i) => {
        const antesTex = latexPaso(p.antes);
        const despuesTex = latexPaso(p.despues);
        const esTransicion = antesTex !== despuesTex;
        return (
          <li key={p.id}>
            <div className="adim-step-heading"><span>{String(i + 1).padStart(2, "0")}</span><h3>{p.regla}</h3></div>
            <div className="adim-step-equations">
              {esTransicion ? (
                <>
                  <FormulaLatex bloque latex={antesTex} lectura="Expresión anterior" />
                  <span className="adim-step-arrow" aria-label="Se transforma en">↓</span>
                  <FormulaLatex bloque latex={despuesTex} lectura="Expresión posterior" />
                </>
              ) : (
                <FormulaLatex bloque latex={despuesTex} lectura="Expresión verificada" />
              )}
            </div>
            {p.justificacion && <p className="adim-step-reason">{p.justificacion}</p>}
            {p.supuestos.length > 0 && <p className="adim-step-assumptions">Requiere: {p.supuestos.join("; ")}</p>}
            {p.operacion === "hipotesis_fisica" && <p className="adim-step-assumptions">Este paso incorpora una hipótesis física; no es una identidad algebraica.</p>}
          </li>
        );
      })}</ol>
      {!pasos.length && <p className="adim-development-pending">El resultado no contiene pasos. El desglose está incompleto.</p>}
      <h3 className="adim-development-result">Formulación obtenida</h3>
      {resultado.ecuaciones.map(e => <FormulaLatex key={e.igualdad.id} bloque latex={`${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`} lectura="Ecuación transformada" />)}
      {resultado.funcionesAdimensionales && resultado.funcionesAdimensionales.length > 0 && <>
        <h3 className="adim-development-result">Definiciones de funciones escaladas</h3>
        {resultado.funcionesAdimensionales.map(fn => <div key={fn.id} className="adim-step-reason">
          <p className="adim-preview-label">{fn.id} · función adimensional de {fn.funcionId}</p>
          <FormulaLatex bloque latex={`${nombreLatex(fn.nombre)}\\left(${fn.argumentos.map((_, i) => `w_{${i + 1}}`).join(", ")}\\right) = \\frac{${nombreLatex(fn.funcionId)}\\left(${fn.argumentos.map((a, i) => a.extraida ? `${latexExpresion(a.escala)}\\,w_{${i + 1}}` : `w_{${i + 1}}`).join(", ")}\\right)}{${nombreLatex(fn.escalaId)}}`} lectura={fn.definicion} />
          <small>Escala dimensional extraída: {fn.escalaId} · Definición: <code>{fn.definicion}</code></small>
        </div>)}
      </>}
      {resultado.grupos.length > 0 && <><h3 className="adim-development-result">Definiciones de los grupos</h3>{resultado.grupos.map(g => <div key={g.id}><p className="adim-preview-label">{g.id}</p><FormulaLatex bloque latex={latexExpresion(g.definicion)} lectura={`Definición de ${g.id}`} /></div>)}</>}
      <p className="adim-step-reason">Equivalencia reportada por el núcleo: {resultado.equivalencia.estado === "demostrada" ? "demostrada" : "no demostrada"}. Alcance: {resultado.equivalencia.alcance}</p>
    </>}
  </section>;
}
