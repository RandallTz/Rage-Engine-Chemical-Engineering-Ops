"use client";

import { useEffect, useState } from "react";
import type { Documento, Modelo } from "./contrato";
import type { AuditoriaDimensional } from "./dimensiones";
import { consultarDimensiones } from "./clienteNucleo";
import { prepararSolicitud } from "./lecturaNucleo";
import { dimensionLatex, latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";

const roles = { tiempo: "Tiempo independiente", coordenada: "Variable independiente", campo: "Campo / variable dependiente", parametro: "Parámetro constante", constante: "Constante" };
const etiquetas = { compatible: "Compatible", incompatible: "Incompatible", pendiente: "Sin determinar", cero: "Cero compatible" };
export default function DimensionesModelo({ documento, cambiar }: { documento: Documento; cambiar: (m: Modelo) => void }) {
  const clave = JSON.stringify(documento.modelo);
  const [lectura, setLectura] = useState<{ clave: string; dato?: AuditoriaDimensional; error?: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => { controller.abort(); setLectura({ clave, error: "Se agotó el tiempo de comprobación. Edita una unidad para reintentar o revisa el servicio." }); }, 20000);
    const timer = setTimeout(() => {
      const solicitud = prepararSolicitud(documento);
      solicitud.operacion = "analizar"; delete solicitud.opciones; delete solicitud.transformaciones; delete solicitud.formaId;
      void consultarDimensiones(solicitud, controller.signal).then(dato => {
        clearTimeout(timeout);
        if (!controller.signal.aborted) setLectura({ clave, dato });
      }).catch(e => { clearTimeout(timeout); if (!controller.signal.aborted) setLectura({ clave, error: e instanceof Error ? e.message : String(e) }); });
    }, 450);
    return () => { clearTimeout(timer); clearTimeout(timeout); controller.abort(); };
  }, [clave, documento]);
  const actual = lectura?.clave === clave ? lectura : null, dato = actual?.dato;
  const dimensional = dato?.analisis.dimensional;
  const errores = dato?.analisis.diagnosticos.filter(d => d.severidad === "error") ?? [];
  const seguro = dimensional?.estado === "compatible" && !errores.length;
  function unidad(id: string, texto: string) {
    cambiar({ ...documento.modelo, simbolos: documento.modelo.simbolos.map(s => s.id === id ? { ...s, unidad: texto.trim() || null, dimension: null } : s) });
  }
  function rol(id: string, nuevo: Modelo["simbolos"][number]["rol"]) {
    const independientes = documento.modelo.simbolos.filter(s => ["tiempo", "coordenada"].includes(s.rol) && s.id !== id).map(s => s.id);
    cambiar({ ...documento.modelo, simbolos: documento.modelo.simbolos.map(s => s.id === id ? { ...s, rol: nuevo,
      constante: nuevo === "parametro" || nuevo === "constante", dependeDe: nuevo === "campo" ? independientes : [] } : s) });
  }
  return <section className="adim-dimensions" aria-labelledby="adim-dimensiones-titulo">
    <header><div><p className="adim-eyebrow">Comprobación dimensional</p><h2 id="adim-dimensiones-titulo">Cada término debe encajar</h2></div><p role="status" className={`adim-dimension-status ${errores.length ? "is-error" : seguro ? "is-valid" : ""}`}>{!actual ? "Comprobando…" : actual.error ? "Sin conexión" : seguro ? "Dimensiones compatibles" : errores.length ? "Revisa las incompatibilidades" : "Faltan dimensiones"}</p></header>
    <p className="adim-dimensions-intro">Cada sumando debe tener la dimensión de su ecuación. En un sistema, los símbolos compartidos se analizan juntos. Escribe las unidades que conoces; las demás dimensiones se infieren.</p>
    {actual?.error && <p className="adim-input-error" role="alert">{actual.error}</p>}
    {errores.map((d, i) => <p className="adim-input-error" role="alert" key={i}>{d.mensaje} <small>({d.ruta})</small></p>)}
    <div className="adim-dimension-table"><table><thead><tr><th>Símbolo y función</th><th>Unidad conocida</th><th>Dimensión</th><th>Magnitud compatible</th></tr></thead><tbody>{documento.modelo.simbolos.map(s => {
      const d = dimensional?.simbolos.find(x => x.id === s.id), cantidad = dato?.cantidades.find(x => x.id === s.id);
      return <tr key={s.id}><th scope="row"><FormulaLatex latex={nombreLatex(s.nombre)} lectura={s.nombre} /><small>{s.rol === "coordenada" && cantidad?.magnitudes.includes("tiempo") ? "Tiempo independiente (por unidad)" : roles[s.rol]}</small><details className="adim-role"><summary>Cambiar función</summary><select aria-label={`Rol de ${s.id}`} value={s.rol} onChange={e => rol(s.id, e.target.value as typeof s.rol)}>{Object.entries(roles).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</select></details></th><td><input aria-label={`Unidad de ${s.id}`} value={s.unidad ?? ""} placeholder="Por inferir" list="adim-unidades" autoComplete="off" spellCheck={false} onChange={e => unidad(s.id, e.target.value)} />{cantidad?.unidadNormalizada && cantidad.unidadNormalizada !== s.unidad && <small>Se interpreta como {cantidad.unidadNormalizada}</small>}</td><td><FormulaLatex latex={dimensionLatex(d?.dimension ?? s.dimension)} lectura="Dimensión del símbolo" /><small>{d?.origen === "inferida" ? "Inferida por las ecuaciones" : d?.origen === "unidad" ? "Detectada de la unidad" : d?.origen === "declarada" ? "Declarada" : "Pendiente"}</small></td><td><select aria-label={`Magnitud de ${s.id}`} value="" onChange={e => { const tipo = dato?.catalogo.find(t => t.id === e.target.value); if (tipo) unidad(s.id, tipo.unidad); }}><option value="">{cantidad?.magnitudes.length ? cantidad.magnitudes.map(id => dato?.catalogo.find(c => c.id === id)?.nombre).join(" / ") : "Elegir magnitud…"}</option>{dato?.catalogo.map(c => <option key={c.id} value={c.id}>{c.nombre} · {c.unidad}</option>)}</select><small>Elegir una magnitud declara su unidad.</small></td></tr>;
    })}</tbody></table></div>
    {documento.modelo.funciones.length > 0 && <details className="adim-term-audit mt-4" open>
      <summary>Funciones declaradas y escala dimensional ({documento.modelo.funciones.length})</summary>
      <div className="adim-dimension-table">
        <p className="adim-dimensions-intro text-xs">
          Extrae el factor de escala dimensional de una función dependiente: <FormulaLatex latex="f(z) = S\,\hat{f}(w)" lectura="f(z) = S fhat(w)" />, permitiendo normalizar su salida y sus argumentos en las ecuaciones y condiciones.
        </p>
        <table>
          <thead>
            <tr>
              <th>Función</th>
              <th>Escala dimensional (S)</th>
              <th>Función adimensional (<FormulaLatex latex="\hat{f}" lectura="f sombrero" />)</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {documento.modelo.funciones.map(fn => {
              const tieneEscala = Boolean(fn.escala);
              return <tr key={fn.id}>
                <td>
                  <strong>{fn.nombre}</strong> <small className="font-mono text-zinc-500">({fn.id})</small>
                </td>
                <td>
                  <input
                    aria-label={`Escala dimensional de ${fn.nombre}`}
                    value={fn.escala?.simboloId ?? ""}
                    placeholder="p. ej. Dstar"
                    onChange={e => {
                      const val = e.target.value.trim();
                      const funcionAdim = fn.escala?.funcionAdimensional || `${fn.nombre}h`;
                      let simbolos = documento.modelo.simbolos;
                      if (val && !simbolos.some(s => s.id === val)) {
                        simbolos = [...simbolos, {
                          id: val, nombre: val, rol: "parametro", constante: true, dependeDe: [], signo: "desconocido", dimension: null, unidad: null
                        }];
                      }
                      cambiar({
                        ...documento.modelo,
                        simbolos,
                        funciones: documento.modelo.funciones.map(f => f.id === fn.id ? {
                          ...f,
                          escala: val ? { simboloId: val, funcionAdimensional: funcionAdim } : undefined
                        } : f)
                      });
                    }}
                  />
                </td>
                <td>
                  <input
                    aria-label={`Función adimensional de ${fn.nombre}`}
                    value={fn.escala?.funcionAdimensional ?? ""}
                    placeholder="p. ej. Dh"
                    disabled={!tieneEscala && !fn.escala?.simboloId}
                    onChange={e => {
                      const val = e.target.value.trim();
                      if (!fn.escala) return;
                      cambiar({
                        ...documento.modelo,
                        funciones: documento.modelo.funciones.map(f => f.id === fn.id ? {
                          ...f,
                          escala: { ...f.escala!, funcionAdimensional: val }
                        } : f)
                      });
                    }}
                  />
                </td>
                <td>
                  {tieneEscala ? <span className="is-valid text-xs">Escala activa</span> : <small className="text-zinc-500">Sin extraer</small>}
                </td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
    </details>}
    <datalist id="adim-unidades">{["s", "min", "m", "cm", "L", "mL", "m^3", "kg", "g", "mol", "mol/L", "mol/m^3", "kg/m^3", "m^2/s", "K", "degC", "Pa", "J", "1"].map(u => <option key={u} value={u} />)}</datalist>
    <p className="adim-dimension-help">En las unidades, L = litro; kg = masa; mol = cantidad de sustancia. En las dimensiones, M, L, T, N representan masa, longitud, tiempo y cantidad. El rol es matemático; la magnitud se identifica por su dimensión y puede ser ambigua.</p>
    {!!dimensional?.faltantes.length && <p className="adim-dimension-help">Para determinar el resto basta indicar: <strong>{dimensional.faltantes.join(", ")}</strong>.</p>}
    {dato?.ecuaciones.map((eq, i) => <details className="adim-term-audit" key={eq.id} open={dato.ecuaciones.length === 1 || errores.length > 0}><summary>Ecuación {i + 1} · dimensiones de cada término <span><FormulaLatex latex={dimensionLatex(eq.dimension)} lectura="Dimensión esperada de la ecuación" /></span></summary><div className="adim-dimension-table"><table><thead><tr><th>Término</th><th>Operadores detectados</th><th>Dimensión</th><th>Comprobación</th></tr></thead><tbody>{eq.terminos.map(t => <tr key={t.ruta}><td><FormulaLatex bloque latex={latexExpresion(t.expresion)} lectura="Término de la ecuación" /><small>Lado {t.lado === "izquierda" ? "izquierdo" : "derecho"}</small></td><td>{t.operadores.map((o, j) => <small key={j}>{o.tipo === "derivada" ? `Derivada de orden ${o.orden} respecto a ${o.respecto}` : o.tipo === "llamada" ? `Función declarada ${o.nombre}` : o.nombre ?? o.tipo}{o.coordenadas ? ` en ${o.coordenadas.join(", ")}` : ""}</small>)}{!t.operadores.length && <small>Expresión algebraica</small>}</td><td><FormulaLatex latex={dimensionLatex(t.dimension)} lectura="Dimensión calculada del término" /></td><td className={t.estado === "incompatible" ? "is-error" : t.estado === "compatible" || t.estado === "cero" ? "is-valid" : ""}>{etiquetas[t.estado]}</td></tr>)}</tbody></table></div></details>)}
  </section>;
}
