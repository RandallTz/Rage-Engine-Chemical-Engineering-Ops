"use client";

import { useEffect, useMemo, useState } from "react";
import type { Modelo } from "./contrato";
import type { FormulacionNucleo, SolicitudNucleo } from "./contratoNucleo";
import type { ResultadosEstudio } from "./contratoEstudio";
import { Estado, Simbolo } from "./presentacionEstudio";
import { simbolosConValor, useConsulta, valoresParaNucleo, type MapaValores } from "./usoEstudio";
import VistaGrupos from "./VistaGrupos";
import VistaRegimenes from "./VistaRegimenes";
import VistaDinamica from "./VistaDinamica";
import VistaSimetrias from "./VistaSimetrias";
import VistaSimulacion from "./VistaSimulacion";
import styles from "../motor/trabajoMotor.module.css";
import { leerOrigen } from "./origenMotor";

type Pestana = "grupos" | "regimenes" | "dinamica" | "simetrias" | "simulacion";
const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: "grupos", nombre: "Grupos y valores" }, { id: "regimenes", nombre: "Regímenes y malla" },
  { id: "dinamica", nombre: "Estabilidad" }, { id: "simetrias", nombre: "Simetrías" }, { id: "simulacion", nombre: "Simulación" },
];

export default function EstudioFormulacion({ base, f, modelo, nombreModelo, valores, setValores, alCalcular }: {
  base: SolicitudNucleo; f: FormulacionNucleo; modelo: Modelo; nombreModelo: string;
  valores: MapaValores; setValores: (m: MapaValores) => void; alCalcular?: (r: ResultadosEstudio) => void;
}) {
  const [pestana, setPestana] = useState<Pestana>("grupos");
  const estructural = useConsulta(base, f), numerica = useConsulta(base, f), continuacion = useConsulta(base, f), simulacion = useConsulta(base, f);
  const simbolos = useMemo(() => simbolosConValor(modelo, f), [modelo, f]);
  const origen = useMemo(() => leerOrigen(base.documento.id), [base.documento.id]);
  const ids = simbolos.map(s => s.id);
  const lanzarEstructural = estructural.lanzar;
  useEffect(() => {
    const id = setTimeout(() => void lanzarEstructural(["estructura", "sensibilidad", "simetrias"], {}), 0);
    return () => clearTimeout(id);
  }, [lanzarEstructural]);
  const enviados = valoresParaNucleo(valores, ids);
  const resultados: ResultadosEstudio = {
    ...(estructural.consulta.respuesta?.estudio ?? {}),
    ...(numerica.consulta.respuesta?.estudio ?? {}),
    ...(continuacion.consulta.respuesta?.estudio?.continuacion ? { continuacion: continuacion.consulta.respuesta.estudio.continuacion } : {}),
    ...(simulacion.consulta.respuesta?.estudio?.simulacion ? { simulacion: simulacion.consulta.respuesta.estudio.simulacion } : {}),
  };
  const errorDe = (c: typeof estructural.consulta) => c.estado === "error" ? c.error : c.respuesta && c.respuesta.estado !== "correcto" ? c.respuesta.diagnosticos.filter(d => d.severidad === "error").map(d => d.mensaje).join("; ") || `estado ${c.respuesta.estado}` : "";
  const notificar = alCalcular;
  const respuestaNumerica = numerica.consulta.respuesta;
  useEffect(() => { if (notificar && respuestaNumerica?.estudio) notificar(respuestaNumerica.estudio); }, [notificar, respuestaNumerica]);
  const calcular = () => void numerica.lanzar(["estructura", "valores", "asintotica", "escalas", "estabilidad"], { valores: enviados });
  const parametrosConValor = enviados.filter(v => simbolos.find(s => s.id === v.simboloId)?.tipo === "parametro").map(v => ({ id: v.simboloId, unidad: v.unidad ?? "" }));
  const faltan = simbolos.length - enviados.length;
  const libresSinValor = simbolos.filter(s => s.tipo === "escala" && !enviados.some(v => v.simboloId === s.id));
  return (
    <div className={styles.solveLayout}>
      <section className="adim-estudio" aria-label="Estudio de la formulación">
        <details className="adim-valores" open={faltan > 0}>
          <summary>Valores físicos <small>{enviados.length} de {simbolos.length}</small></summary>
          <form id="adim-form-valores" className={styles.variables} onSubmit={e => { e.preventDefault(); calcular(); }}>
            {simbolos.map(s => (
              <div key={s.id} className={styles.field}>
                <Simbolo id={s.id} />
                <label htmlFor={`valor-${s.id}`}>{origen?.descripciones[s.id] ?? (s.tipo === "escala" ? "Escala de referencia" : "Parámetro")}<small className={styles.fieldRole}>{s.tipo === "escala" ? "escala libre: no cambia el resultado físico" : "dato del modelo"}</small></label>
                <span className="adim-valor-campos">
                  <input id={`valor-${s.id}`} inputMode="decimal" aria-label={`Valor de ${s.id}`} placeholder="valor" value={valores[s.id]?.valor ?? ""}
                    onChange={e => setValores({ ...valores, [s.id]: { valor: e.target.value, unidad: valores[s.id]?.unidad ?? s.unidad } })} />
                  <input aria-label={`Unidad de ${s.id}`} placeholder={s.unidad || "unidad SI"} value={valores[s.id]?.unidad ?? s.unidad}
                    onChange={e => setValores({ ...valores, [s.id]: { valor: valores[s.id]?.valor ?? "", unidad: e.target.value } })} />
                </span>
              </div>
            ))}
          </form>
        </details>

        <nav className={styles.tabs} aria-label="Análisis de la formulación">
          {PESTANAS.map(p => <button key={p.id} type="button" aria-pressed={pestana === p.id} onClick={() => setPestana(p.id)}>{p.nombre}</button>)}
        </nav>
        {estructural.consulta.estado === "cargando" && <Estado estado="cargando" />}
        {errorDe(estructural.consulta) && <p className="adim-input-error" role="alert">{errorDe(estructural.consulta)}</p>}

        {pestana === "grupos" && <VistaGrupos f={f} estructura={resultados.estructura} sensibilidad={resultados.sensibilidad} valores={resultados.valores} />}
        {pestana === "regimenes" && <VistaRegimenes f={f} asintotica={resultados.asintotica} escalas={resultados.escalas} />}
        {pestana === "dinamica" && <VistaDinamica estabilidad={resultados.estabilidad} continuacion={resultados.continuacion} cargandoContinuacion={continuacion.consulta.estado === "cargando"}
          parametros={parametrosConValor}
          continuar={(pid, desde, hasta, unidad) => void continuacion.lanzar(["continuacion"], { valores: enviados, continuacion: { parametroId: pid, desde, hasta, ...(unidad.trim() ? { unidad: unidad.trim() } : {}) } })} />}
        {pestana === "dinamica" && errorDe(continuacion.consulta) && <p className="adim-input-error" role="alert">{errorDe(continuacion.consulta)}</p>}
        {pestana === "simetrias" && <VistaSimetrias simetrias={resultados.simetrias} />}
        {pestana === "simulacion" && <VistaSimulacion f={f} simulacion={resultados.simulacion} cargando={simulacion.consulta.estado === "cargando"} nombreModelo={nombreModelo} origen={origen}
          simular={op => void simulacion.lanzar(["simulacion"], { valores: enviados, simulacion: op })} />}
        {pestana === "simulacion" && errorDe(simulacion.consulta) && <p className="adim-input-error" role="alert">{errorDe(simulacion.consulta)}</p>}
      </section>
      <aside className={styles.solveAside}>
        <div className={styles.counts}>
          <div><span>Valores dados</span><strong>{enviados.length} / {simbolos.length}</strong></div>
          <div><span>Grupos</span><strong>{f.grupos.length}</strong></div>
        </div>
        {libresSinValor.length > 0 && <button type="button" className="adim-enlace" onClick={() => setValores({ ...valores, ...Object.fromEntries(libresSinValor.map(s => [s.id, { valor: "1", unidad: "" }])) })}>Dar 1 (SI) a las escalas libres</button>}
        <button type="submit" form="adim-form-valores" className={styles.primary} disabled={numerica.consulta.estado === "cargando"}>{numerica.consulta.estado === "cargando" ? "Calculando…" : "Calcular con estos valores"}</button>
        {numerica.consulta.estado === "cargando" && <button type="button" className="adim-enlace adim-aside-enlace" onClick={numerica.cancelar}>Cancelar cálculo</button>}
        {errorDe(numerica.consulta) && <p className="adim-input-error" role="alert">{errorDe(numerica.consulta)}</p>}
        <p className="adim-aside-nota">Los valores se guardan en este navegador para esta hoja. Con ellos se evalúan grupos, régimen dominante, malla, estabilidad y simulación.</p>
      </aside>
    </div>
  );
}
