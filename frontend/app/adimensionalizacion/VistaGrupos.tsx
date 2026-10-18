"use client";

import type { FormulacionNucleo } from "./contratoNucleo";
import type { EstudioEstructura, EstudioSensibilidad, EstudioValores } from "./contratoEstudio";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";
import { Estado, NOMBRE_TIPO, Simbolo, TerminoLatex, numero, racional } from "./presentacionEstudio";

export default function VistaGrupos({ f, estructura, sensibilidad, valores }: {
  f: FormulacionNucleo; estructura?: EstudioEstructura; sensibilidad?: EstudioSensibilidad; valores?: EstudioValores;
}) {
  const valorDe = new Map((valores?.grupos ?? []).map(g => [g.grupoId, g]));
  const lecturaDe = new Map((estructura?.grupos ?? []).map(g => [g.grupoId, g]));
  return (
    <div className="adim-estudio-vista">
      {estructura && estructura.estado === "calculado" && estructura.normalizados.length > 0 && (
        <section className="adim-estudio-bloque">
          <h3>Qué fija esta formulación</h3>
          <p className="adim-estudio-nota">Términos cuyo coeficiente quedó en ±1 por un objetivo: sus escalas definen la forma.</p>
          <ul className="adim-chips">
            {estructura.normalizados.map(n => <li key={n.objetivo}><TerminoLatex f={f} id={n.terminoId} /> <span>{NOMBRE_TIPO[n.tipo]}{n.estado === "dependiente" ? " (consecuencia de otro objetivo)" : ""}</span></li>)}
          </ul>
        </section>
      )}
      <section className="adim-estudio-bloque">
        <h3>Grupos de la formulación</h3>
        {estructura && estructura.estado !== "calculado" && <Estado estado={estructura.estado} motivo={estructura.motivo} />}
        {f.grupos.length === 0 ? <p className="adim-estudio-nota">Esta formulación no tiene grupos: todos los coeficientes son numéricos.</p> : (
          <div className="adim-tabla-scroll">
            <table className="adim-tabla">
              <thead><tr><th>Grupo</th><th>Definición</th><th>Lectura</th><th className="is-num">Valor</th></tr></thead>
              <tbody>
                {f.grupos.map(g => {
                  const l = lecturaDe.get(g.id), v = valorDe.get(g.id);
                  const principal = l?.lecturas[0];
                  return (
                    <tr key={g.id}>
                      <td><Simbolo id={g.id} />{!g.adimensional && <span className="adim-marca-aviso" title="El grupo conserva dimensiones">dimensional</span>}</td>
                      <td><FormulaLatex latex={latexExpresion(g.definicion)} lectura={`Definición de ${g.id}`} /></td>
                      <td>
                        {l?.nombreClasico && <strong className="adim-nombre-clasico">{l.nombreClasico}</strong>}
                        {principal && <span className="adim-lectura">{principal.lectura}</span>}
                        {l && l.nombresClasicos.filter(n => n !== l.nombreClasico).length > 0 && (
                          <span className="adim-lectura is-secundaria">También: {l.nombresClasicos.filter(n => n !== l.nombreClasico).join("; ")} (frente a otros términos de coeficiente 1)</span>
                        )}
                        {l?.nota && <span className="adim-lectura is-secundaria">{l.nota}</span>}
                        {g.contieneEscalasLibres && <span className="adim-lectura is-secundaria">Depende de escalas libres.</span>}
                      </td>
                      <td className="is-num">{v ? (v.valor !== null ? numero(v.valor) : <span className="adim-falta" title={v.faltan.join(", ")}>faltan datos</span>) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {estructura?.estado === "calculado" && <p className="adim-estudio-metodo">{estructura.motivo}.</p>}
      </section>

      {valores && (
        <section className="adim-estudio-bloque">
          <h3>Escalas y magnitudes</h3>
          {valores.estado !== "calculado" && <Estado estado={valores.estado} motivo={valores.motivo} />}
          <div className="adim-tabla-scroll">
            <table className="adim-tabla">
              <thead><tr><th>Escala</th><th>Estado</th><th className="is-num">Valor (SI)</th></tr></thead>
              <tbody>{valores.escalas.map(e => <tr key={e.escalaId}><td><Simbolo id={e.escalaId} /></td><td>{e.estado.replace(/_/g, " ")}</td><td className="is-num">{e.valorSI !== null ? `${numero(e.valorSI)} ${e.unidadSI ?? ""}` : "—"}</td></tr>)}</tbody>
            </table>
          </div>
          {valores.ecuaciones.map(ec => (
            <div key={ec.id} className="adim-magnitudes">
              <h4>Magnitud de los coeficientes · {ec.id}</h4>
              <ul>{ec.coeficientes.map(c => <li key={c.terminoId}><TerminoLatex f={f} id={c.terminoId} /><span className="is-num">{numero(c.valor)}</span></li>)}</ul>
              {ec.dispersionLog10 !== null && <p className="adim-estudio-nota">Dispersión: {numero(ec.dispersionLog10, 3)} órdenes de magnitud entre el mayor y el menor coeficiente.</p>}
            </div>
          ))}
        </section>
      )}

      {sensibilidad && sensibilidad.estado === "calculado" && sensibilidad.grupos.length > 0 && (
        <section className="adim-estudio-bloque">
          <h3>Sensibilidad exacta</h3>
          <p className="adim-estudio-nota">Cada entrada es d ln G / d ln p: el exponente racional de p en el grupo. Un 1 % de cambio en p cambia G en ese múltiplo de 1 %.</p>
          <div className="adim-tabla-scroll">
            <table className="adim-tabla adim-tabla-matriz">
              <thead><tr><th>Grupo</th>{sensibilidad.parametros.map(p => <th key={p} className="is-num"><FormulaLatex latex={nombreLatex(p)} lectura={p} />{sensibilidad.escalasLibres.includes(p) ? "*" : ""}</th>)}</tr></thead>
              <tbody>{sensibilidad.grupos.map(g => <tr key={g.grupoId}><td><Simbolo id={g.grupoId} /></td>{sensibilidad.parametros.map(p => <td key={p} className={`is-num${g.exponentes[p] ? "" : " is-cero"}`}>{g.exponentes[p] ? racional(g.exponentes[p]) : "0"}</td>)}</tr>)}</tbody>
            </table>
          </div>
          {sensibilidad.escalasLibres.length > 0 && <p className="adim-estudio-nota">* escala libre de la formulación.</p>}
          {sensibilidad.omitidos.map(o => <p key={o.grupoId} className="adim-estudio-nota">{o.grupoId}: {o.motivo}</p>)}
        </section>
      )}
    </div>
  );
}
