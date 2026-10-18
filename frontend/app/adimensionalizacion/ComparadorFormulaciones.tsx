"use client";

import { useState } from "react";
import type { Modelo } from "./contrato";
import type { FormulacionNucleo, SolicitudNucleo } from "./contratoNucleo";
import type { EstudioEscalas } from "./contratoEstudio";
import { latexExpresion } from "./exportar";

type CoordenadaCalculada = Extract<NonNullable<EstudioEscalas["coordenadas"]>[number], { estado: "calculado" }>;
import FormulaLatex from "../flowsheet/FormulaLatex";
import { Estado, NOMBRE_TIPO, TerminoLatex, numero } from "./presentacionEstudio";
import { simbolosConValor, useConsulta, valoresParaNucleo, type MapaValores } from "./usoEstudio";

/** Dos formulaciones del mismo modelo, lado a lado, con métricas del núcleo
 * evaluadas con los mismos valores físicos. */
export default function ComparadorFormulaciones({ base, formas, modelo, valores, inicial }: {
  base: SolicitudNucleo; formas: FormulacionNucleo[]; modelo: Modelo; valores: MapaValores; inicial: number;
}) {
  const [a, setA] = useState(inicial), [b, setB] = useState(formas.length > 1 ? (inicial === 0 ? 1 : 0) : 0);
  return (
    <section className="adim-estudio-bloque" aria-label="Comparación de formulaciones">
      <h3>Comparar formulaciones</h3>
      <p className="adim-estudio-nota">Todas son el mismo modelo escrito con escalas distintas. Con los mismos valores físicos se comparan la dispersión de magnitudes de los coeficientes, la malla necesaria y la rigidez.</p>
      <div className="adim-comparador">
        <Columna key={`a${a}`} base={base} formas={formas} indice={a} cambiar={setA} modelo={modelo} valores={valores} />
        <Columna key={`b${b}`} base={base} formas={formas} indice={b} cambiar={setB} modelo={modelo} valores={valores} />
      </div>
    </section>
  );
}

function Columna({ base, formas, indice, cambiar, modelo, valores }: { base: SolicitudNucleo; formas: FormulacionNucleo[]; indice: number; cambiar: (i: number) => void; modelo: Modelo; valores: MapaValores }) {
  const f = formas[indice];
  const { consulta, lanzar } = useConsulta(base, f);
  const ids = simbolosConValor(modelo, f).map(s => s.id);
  const r = consulta.respuesta?.estudio;
  const esc = r?.escalas?.coordenadas?.find((c): c is CoordenadaCalculada => c.estado === "calculado");
  return (
    <div className="adim-comparador-columna">
      <label className="adim-etiqueta">Formulación
        <select value={indice} onChange={e => cambiar(Number(e.target.value))}>{formas.map((_, i) => <option key={i} value={i}>Forma {i + 1}</option>)}</select>
      </label>
      {f.ecuaciones.map(e => <FormulaLatex key={e.igualdad.id} bloque latex={`${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`} lectura={e.igualdad.id} />)}
      <p className="adim-estudio-nota">{f.libres.length ? `Escalas libres: ${f.libres.join(", ")}` : "Todas las escalas determinadas"} · normalización {f.normalizacion.estado}.</p>
      <button type="button" className="adim-button" disabled={consulta.estado === "cargando"} onClick={() => void lanzar(["estructura", "valores", "escalas"], { valores: valoresParaNucleo(valores, ids) })}>{consulta.estado === "cargando" ? "Calculando…" : "Evaluar con los valores"}</button>
      {consulta.estado === "error" && <p className="adim-input-error">{consulta.error}</p>}
      {r && <dl className="adim-metricas">
        {r.estructura?.normalizados?.length ? <><dt>Normaliza</dt><dd>{r.estructura.normalizados.map(n => <span key={n.objetivo} className="adim-par"><TerminoLatex f={f} id={n.terminoId} /> ({NOMBRE_TIPO[n.tipo]})</span>)}</dd></> : null}
        <dt>Dispersión de coeficientes</dt><dd>{r.valores?.dispersionMaxima != null ? `${numero(r.valores.dispersionMaxima, 3)} órdenes de magnitud` : r.valores ? <Estado estado={r.valores.estado} motivo={r.valores.motivo} /> : "—"}</dd>
        <dt>Nodos recomendados</dt><dd>{esc?.malla ? esc.malla.nodosRecomendados : "—"}</dd>
        <dt>Rigidez</dt><dd>{esc?.rigidez ? `${numero(esc.rigidez.cociente)} · ${esc.rigidez.recomendacion}` : "—"}</dd>
      </dl>}
    </div>
  );
}
