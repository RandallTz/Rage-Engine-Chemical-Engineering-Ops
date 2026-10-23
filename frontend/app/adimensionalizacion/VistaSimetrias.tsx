"use client";

import type { ReactNode } from "react";
import type { EstudioSimetrias } from "./contratoEstudio";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../components/FormulaLatex";
import { Estado, Simbolo, racional, racionalLatex } from "./presentacionEstudio";

export default function VistaSimetrias({ simetrias }: { simetrias?: EstudioSimetrias }) {
  if (!simetrias) return <p className="adim-estudio-nota">Calculando las simetrías…</p>;
  if (simetrias.estado !== "calculado") return <Estado estado={simetrias.estado} motivo={simetrias.motivo} />;
  const vars = simetrias.variables ?? [];
  return (
    <div className="adim-estudio-vista">
      <section className="adim-estudio-bloque">
        <h3>Grupos de escala</h3>
        <p className="adim-estudio-nota">Exponentes a tales que cada variable v → λ<sup>a</sup> v deja invariantes todas las ecuaciones con los parámetros fijos.</p>
        {simetrias.generadores?.length ? (
          <div className="adim-tabla-scroll"><table className="adim-tabla adim-tabla-matriz">
            <thead><tr><th>Generador</th>{vars.map(v => <th key={v} className="is-num"><Simbolo id={v} /></th>)}</tr></thead>
            <tbody>{simetrias.generadores.map((g, i) => <tr key={i}><td>{i + 1}</td>{vars.map(v => <td key={v} className="is-num">{g.exponentes[v] ? racional(g.exponentes[v]) : "0"}</td>)}</tr>)}</tbody>
          </table></div>
        ) : <p>No hay dilataciones no triviales: los parámetros fijan todas las escalas.</p>}
        {simetrias.nota && <p className="adim-estudio-nota">{simetrias.nota}.</p>}
        <p>Traslaciones: {simetrias.traslaciones?.length ? simetrias.traslaciones.map(v => <Simbolo key={v} id={v} />).reduce<ReactNode[]>((a, x, i) => i ? [...a, ", ", x] : [x], []) : "ninguna (las variables aparecen explícitamente)"}.</p>
      </section>
      {(simetrias.reducciones ?? []).map((r, i) => (
        <section key={i} className="adim-estudio-bloque">
          <h3>{r.tipo === "semejanza" ? "Reducción de semejanza" : "Onda viajera"}</h3>
          {r.estado !== "calculado" ? <Estado estado="no_soportado" motivo={r.motivo} /> : <>
            {r.variable && <FormulaLatex bloque latex={`${nombreLatex(r.variable.id)} = ${latexExpresion(r.variable.definicion)}`} lectura="Variable de reducción" />}
            {r.perfiles?.map(p => <FormulaLatex key={p.id} bloque lectura={`Ansatz de ${p.campo}`}
              latex={r.tipo === "semejanza" && p.potenciaTau ? `${nombreLatex(p.campo)} = ${p.potenciaTau.n ? `\\tau^{${racionalLatex(p.potenciaTau)}}\\,` : ""}${nombreLatex(p.id)}(${nombreLatex(r.variable!.id)})` : `${nombreLatex(p.campo)} = ${nombreLatex(p.id)}(${nombreLatex(r.variable!.id)})`} />)}
            <p className="adim-etiqueta">Ecuación reducida{(r.ecuaciones?.length ?? 0) > 1 ? "s" : ""}</p>
            {r.ecuaciones?.map(e => <FormulaLatex key={e.id} bloque latex={`${latexExpresion(e.ecuacion.izquierda)} = 0`} lectura={`Ecuación reducida ${e.id}`} />)}
            <p className="adim-estudio-metodo">{r.motivo}.</p>
          </>}
        </section>
      ))}
      {simetrias.notaReduccion && <p className="adim-estudio-nota">{simetrias.notaReduccion}.</p>}
      <p className="adim-estudio-metodo">{simetrias.motivo}.</p>
    </div>
  );
}
