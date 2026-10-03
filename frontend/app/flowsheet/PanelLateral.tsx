"use client";

import { useState } from "react";
import type { Node } from "@xyflow/react";
import { desdeSI, molARepresentacionMasica, type Unidades } from "./unidades";
import {
  DatosNodo,
  DatosOperacion,
  MetodoColumna,
  metodosDisponibles,
  ecuacionReaccion,
  listaReacciones,
  guardarReacciones,
  A_POR_DEFECTO,
  EA_POR_DEFECTO,
  type ReaccionUI,
  variablesDeCorriente,
  variablesDeOperacion,
  etiquetaVariable,
  estadoDe,
  valorDe,
  formatear,
  UNIDAD,
} from "./modelo";

export interface InformeBloque {
  bloque: string;
  incognitas: string[];
  faltantes_para_disparar: string[];
  puede_dispararse: boolean;
}

export interface Redundancia {
  bloque: string;
  sobran: number;
  dados: string[];
  necesarios: number;
}

export interface Inconsistencia {
  bloque: string;
  // Opcionales: si el problema lo detecta el propio bloque al resolver,
  // solo hay mensaje (no una variable concreta con valor esperado).
  variable: string | null;
  dado: number | null;
  implicado: number | null;
  mensaje: string;
}

interface Props {
  nodo: Node<DatosNodo> | undefined;
  componentes: string[];
  dados: Record<string, string>;
  pool: Record<string, number>;
  diagnostico: InformeBloque[];
  inconsistencias: Inconsistencia[];
  incognitas: string[];
  completo: boolean | null;
  onValor: (clave: string, valor: string) => void;
  onDatos: (cambio: Partial<DatosOperacion>) => void;
  onEliminar: () => void;
  onRenombrar: (viejo: string, nuevo: string) => string | null;
  onIrA: (nodoId: string) => void;
  unidades: Unidades;
  redundancias: Redundancia[];
  masasMolares: Record<string, number>;
}

export default function PanelLateral({
  nodo, componentes, dados, pool, diagnostico, inconsistencias, incognitas, completo,
  onValor, onDatos, onEliminar, onRenombrar, onIrA, unidades, redundancias, masasMolares,
}: Props) {
  return (
    <aside className="flex w-[340px] min-h-0 flex-col border-l border-zinc-800 bg-zinc-900">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {inconsistencias.length > 0 && (
          <section className="border-b border-red-900 bg-red-950/40 px-3 py-2">
            <h2 className="mb-1 text-sm font-semibold text-red-200">
              Datos incompatibles ({inconsistencias.length})
            </h2>
            <p className="mb-2 text-[10px] text-red-200/70">
              Diste más valores de los necesarios y no cumplen las ecuaciones. Borra alguno para que el
              simulador lo calcule.
            </p>
            {inconsistencias.map((inc) => (
              <div key={inc.bloque + inc.variable} className="mb-1.5 rounded border border-red-800/60 bg-red-950/40 p-1.5">
                <div className="text-[11px] font-medium text-red-100">{inc.bloque}</div>
                {inc.variable && inc.dado !== null && inc.implicado !== null ? (
                  <div className="font-mono text-[10px] text-red-200">
                    {inc.variable}: diste {formatear(inc.dado, inc.variable)} · implica {formatear(inc.implicado, inc.variable)}
                  </div>
                ) : (
                  <div className="text-[10px] text-red-200">{inc.mensaje}</div>
                )}
              </div>
            ))}
          </section>
        )}

        {nodo ? (
          <EditorElemento
            nodo={nodo}
            componentes={componentes}
            dados={dados}
            pool={pool}
            inconsistencias={inconsistencias}
            onValor={onValor}
            onDatos={onDatos}
            onEliminar={onEliminar}
            onRenombrar={onRenombrar}
            unidades={unidades}
            masasMolares={masasMolares}
          />
        ) : (
          <Guia
            diagnostico={diagnostico}
            incognitas={incognitas}
            completo={completo}
            componentes={componentes}
            onIrA={onIrA}
            redundancias={redundancias}
          />
        )}
      </div>
    </aside>
  );
}

function EditorElemento({
  nodo, componentes, dados, pool, inconsistencias, onValor, onDatos, onEliminar,
  onRenombrar, unidades, masasMolares,
}: {
  nodo: Node<DatosNodo>;
  componentes: string[];
  dados: Record<string, string>;
  pool: Record<string, number>;
  inconsistencias: Inconsistencia[];
  onValor: (clave: string, valor: string) => void;
  onDatos: (cambio: Partial<DatosOperacion>) => void;
  onEliminar: () => void;
  onRenombrar: (viejo: string, nuevo: string) => string | null;
  unidades: Unidades;
  masasMolares: Record<string, number>;
}) {
  const esCorriente = nodo.data.clase === "corriente";
  const datosOp = nodo.data as DatosOperacion;
  const variables = esCorriente ? variablesDeCorriente(componentes.length) : variablesDeOperacion(datosOp);
  const clavesMalas = new Set(inconsistencias.map((i) => i.variable));

  return (
    <div>
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <div className="min-w-0 flex-1">
          <NombreEditable nodoId={nodo.id} onRenombrar={onRenombrar} />
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">
            {esCorriente ? "corriente" : `${datosOp.tipo}${datosOp.metodo ? ` · ${datosOp.metodo}` : ""}`}
          </div>
        </div>
        <button onClick={onEliminar} className="ml-2 shrink-0 text-xs text-red-400 hover:text-red-300">eliminar</button>
      </div>

      {!esCorriente && (
        <div className="space-y-1.5 border-b border-zinc-800 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">Configuración del equipo</div>
          {datosOp.tipo === "columna" && (
            <>
              <label className="block text-[10px] text-zinc-500">método</label>
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                value={datosOp.metodo ?? "mccabe_thiele"}
                onChange={(e) => onDatos({ metodo: e.target.value as MetodoColumna })}
              >
                {/* Los métodos que no aplican a esta mezcla se deshabilitan
                    DICIENDO POR QUÉ. Antes se podían elegir igual y el fallo
                    aparecía después, al resolver, como un error del motor. */}
                {metodosDisponibles(componentes.length).map((m) => (
                  <option key={m.valor} value={m.valor} disabled={!m.disponible}>
                    {m.etiqueta}{m.disponible ? "" : ` — ${m.motivo}`}
                  </option>
                ))}
              </select>
              {(datosOp.metodo === "ponchon_savarit" || datosOp.metodo === "fug") && (
                <CampoConfig etiqueta="q (fijo)" valor={String(datosOp.q_fijo ?? 1)} onChange={(v) => onDatos({ q_fijo: Number(v) })} />
              )}
              {datosOp.metodo === "fug" && (
                <>
                  <label className="block pt-1 text-[10px] text-zinc-500">clave ligero (LK)</label>
                  <select
                    className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                    value={datosOp.indice_LK ?? 0}
                    onChange={(e) => onDatos({ indice_LK: Number(e.target.value) })}
                  >
                    {componentes.map((c, i) => <option key={c} value={i}>{c}</option>)}
                  </select>
                  <label className="block text-[10px] text-zinc-500">clave pesado (HK)</label>
                  <select
                    className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                    value={datosOp.indice_HK ?? 1}
                    onChange={(e) => onDatos({ indice_HK: Number(e.target.value) })}
                  >
                    {componentes.map((c, i) => <option key={c} value={i}>{c}</option>)}
                  </select>
                  {(datosOp.indice_LK ?? 0) === (datosOp.indice_HK ?? 1) && (
                    <p className="text-[10px] text-red-400">
                      Los dos claves deben ser componentes distintos.
                    </p>
                  )}
                  <p className="text-[10px] leading-snug text-zinc-500">
                    En FUG no se dan purezas sino <span className="text-zinc-400">recuperaciones</span>: cuánto
                    del clave ligero se va por el domo y cuánto del pesado por el fondo. Las composiciones de
                    producto son resultado del método.
                  </p>
                </>
              )}
            </>
          )}
          {datosOp.tipo === "columna" && (
            <label className="flex items-center gap-2 pt-1 text-[11px] text-zinc-300">
              <input
                type="checkbox"
                checked={datosOp.con_balance_energia !== false}
                onChange={(e) => onDatos({ con_balance_energia: e.target.checked })}
              />
              incluir balance de energia
            </label>
          )}
          {datosOp.tipo === "columna" && datosOp.con_balance_energia === false && (
            <p className="text-[10px] text-zinc-500">
              Solo balance de materia y etapas: Q_c, Q_R, R_int y V_barra no se calculan ni cuentan para
              los grados de libertad.
            </p>
          )}
          {datosOp.tipo === "divisor" && (
            <CampoConfig etiqueta="fracciones" valor={datosOp.fracciones ?? "0.5,0.5"} onChange={(v) => onDatos({ fracciones: v })} />
          )}
          {datosOp.tipo === "reactor_cstr" && (
            <>
              <EditorReaccion datos={datosOp} componentes={componentes} onDatos={onDatos} />
              <CampoCaidaPresion
                valor={datosOp.caida_P}
                onCambio={(v) => onDatos({ caida_P: v })}
              />
            </>
          )}
          {datosOp.tipo === "reactor_cstr" && (
            <>
              <label className="flex items-center gap-2 text-[11px] text-zinc-400">
                <input
                  type="checkbox"
                  checked={datosOp.con_balance_energia !== false}
                  onChange={(e) => onDatos({ con_balance_energia: e.target.checked })}
                />
                incluir balance de energía
              </label>
              {datosOp.con_balance_energia === false ? (
                <p className="text-[10px] text-zinc-500">
                  Solo balance de materia. Q y Q_reacción no se calculan ni cuentan para los
                  grados de libertad.
                </p>
              ) : (
                <>
              <label className="block text-[10px] text-zinc-500">balance de energía</label>
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                value={String(datosOp.modo_energia ?? "isotermo")}
                onChange={(e) => onDatos({ modo_energia: e.target.value })}
              >
                <option value="isotermo">Isotermo — das T, se calcula el calor</option>
                <option value="adiabatico">Adiabático — Q=0, se calcula la T</option>
                <option value="calor_dado">Calor dado — das Q, se calcula la T</option>
              </select>
              {datosOp.modo_energia === "calor_dado" && (
                <CampoConfig
                  etiqueta="Q [W]"
                  valor={String(datosOp.Q ?? 0)}
                  onChange={(v) => onDatos({ Q: Number(v) })}
                />
              )}
              <p className="text-[10px] text-zinc-500">
                En isotermo, Q es el resultado: cuánta refrigeración cuesta mantener esa
                temperatura. Con una exotérmica suele ser la restricción de diseño real.
                Necesita la T y la P de la corriente de entrada.
              </p>
                </>
              )}
            </>
          )}
          {/* ------------------------------------------------- flash */}
          {datosOp.tipo === "flash" && (
            <>
              <label className="block text-[10px] text-zinc-500">especificación</label>
              {/* UNA sola, nunca dos. El núcleo rechaza las combinaciones
                  sobre-especificadas (fijar T y beta a la vez solo es
                  consistente por casualidad), así que el panel ofrece un
                  selector en vez de tres casillas que se puedan marcar
                  todas. */}
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                value={String(datosOp.spec_flash ?? "adiabatico")}
                onChange={(e) => onDatos({ spec_flash: e.target.value })}
              >
                <option value="adiabatico">Calor dado (0 = adiabático)</option>
                <option value="isotermo">Temperatura del recipiente</option>
                <option value="fraccion">Fracción vaporizada (diseño)</option>
              </select>
              {(datosOp.spec_flash ?? "adiabatico") === "adiabatico" && (
                <CampoConfig
                  etiqueta="Q [J/mol alim.]"
                  valor={String(datosOp.Q_por_mol ?? 0)}
                  onChange={(v) => onDatos({ Q_por_mol: Number(v) })}
                />
              )}
              {datosOp.spec_flash === "isotermo" && (
                <CampoConfig
                  etiqueta="T [K]"
                  valor={String(datosOp.T_operacion ?? 350)}
                  onChange={(v) => onDatos({ T_operacion: Number(v) })}
                />
              )}
              {datosOp.spec_flash === "fraccion" && (
                <CampoConfig
                  etiqueta="β = V/F"
                  valor={String(datosOp.fraccion_vapor ?? 0.5)}
                  onChange={(v) => onDatos({ fraccion_vapor: Number(v) })}
                />
              )}
              <p className="text-[10px] text-zinc-500">
                El vapor sale por el puerto de arriba y el líquido por el de abajo, los dos
                en equilibrio a la misma T y P.
              </p>
            </>
          )}

          {/* ---------------------------------------- intercambiador */}
          {datosOp.tipo === "intercambiador" && (
            <>
              <label className="block text-[10px] text-zinc-500">especificación</label>
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                value={String(datosOp.spec_intercambiador ?? "Q_por_mol")}
                onChange={(e) => onDatos({ spec_intercambiador: e.target.value })}
              >
                <option value="Q_por_mol">Dar el calor, calcular la T</option>
                <option value="T_salida">Dar la T, calcular el calor</option>
              </select>
              {(datosOp.spec_intercambiador ?? "Q_por_mol") === "Q_por_mol" ? (
                <CampoConfig
                  etiqueta="Q [J/mol]"
                  valor={String(datosOp.Q_por_mol ?? 0)}
                  onChange={(v) => onDatos({ Q_por_mol: Number(v) })}
                />
              ) : (
                <CampoConfig
                  etiqueta="T salida [K]"
                  valor={String(datosOp.T_salida ?? 350)}
                  onChange={(v) => onDatos({ T_salida: Number(v) })}
                />
              )}
              <CampoCaidaPresion
                valor={datosOp.caida_P}
                onCambio={(v) => onDatos({ caida_P: v })}
              />
              <p className="text-[10px] text-zinc-500">
                Si calientas lo suficiente, la corriente vaporiza: β a la salida lo dice.
              </p>
            </>
          )}

          {/* ----------------------------------------------- válvula */}
          {datosOp.tipo === "valvula" && (
            <>
              <CampoConfig
                etiqueta="P salida [Pa]"
                valor={String(datosOp.P_salida ?? 101325)}
                onChange={(v) => onDatos({ P_salida: Number(v) })}
              />
              <p className="text-[10px] text-zinc-500">
                Expansión isentálpica: la entalpía se conserva y el líquido se vaporiza en
                parte. Como el calor latente sale de la propia corriente, SE ENFRÍA sin que
                nadie le quite energía.
              </p>
            </>
          )}


          {/* -------------------------------------------- separador */}
          {datosOp.tipo === "separador" && (
            <>
              <CampoConfig
                etiqueta="recuperaciones"
                valor={String(datosOp.recuperaciones ?? "")}
                onChange={(v) => onDatos({ recuperaciones: v })}
              />
              <p className="text-[10px] text-zinc-500">
                Fracción de cada componente que sale por «ligeros», en el orden{" "}
                <span className="text-zinc-400">{componentes.join(", ") || "—"}</span>. El resto
                se va por «pesados».
              </p>
              <p className="text-[10px] text-amber-500/70">
                Es una especificación, no física: nada comprueba que un equipo real pudiera
                conseguirla. Sirve para montar el diagrama antes de decidir con qué se separa.
              </p>
            </>
          )}

          {/* -------------------------------------------- compresor */}
          {datosOp.tipo === "compresor" && (
            <>
              <CampoConfig
                etiqueta="P salida [Pa]"
                valor={String(datosOp.P_salida ?? 303975)}
                onChange={(v) => onDatos({ P_salida: Number(v) })}
              />
              <CampoConfig
                etiqueta="eficiencia isentr."
                valor={String(datosOp.eficiencia ?? 0.75)}
                onChange={(v) => onDatos({ eficiencia: Number(v) })}
              />
              <p className="text-[10px] text-zinc-500">
                Si la presión de salida es MENOR que la de entrada, el mismo equipo funciona
                como turbina y el trabajo sale negativo. Supone gas ideal.
              </p>
            </>
          )}

          {/* ------------------------------ intercambiador de dos corrientes */}
          {datosOp.tipo === "intercambiador_doble" && (
            <>
              <label className="block text-[10px] text-zinc-500">especificación</label>
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1 text-xs"
                value={String(datosOp.spec_ic ?? "T_salida_caliente")}
                onChange={(e) => onDatos({ spec_ic: e.target.value })}
              >
                <option value="T_salida_caliente">T de salida del lado caliente</option>
                <option value="T_salida_frio">T de salida del lado frío</option>
                <option value="Q">Calor intercambiado</option>
              </select>
              {(datosOp.spec_ic ?? "T_salida_caliente") === "T_salida_caliente" && (
                <CampoConfig
                  etiqueta="T cal. salida [K]"
                  valor={String(datosOp.T_salida_caliente ?? 350)}
                  onChange={(v) => onDatos({ T_salida_caliente: Number(v) })}
                />
              )}
              {datosOp.spec_ic === "T_salida_frio" && (
                <CampoConfig
                  etiqueta="T fría salida [K]"
                  valor={String(datosOp.T_salida_frio ?? 340)}
                  onChange={(v) => onDatos({ T_salida_frio: Number(v) })}
                />
              )}
              {datosOp.spec_ic === "Q" && (
                <CampoConfig
                  etiqueta="Q [W]"
                  valor={String(datosOp.Q ?? 100000)}
                  onChange={(v) => onDatos({ Q: Number(v) })}
                />
              )}
              <CampoConfig
                etiqueta="aproximación mín. [K]"
                valor={String(datosOp.aproximacion_minima ?? 5)}
                onChange={(v) => onDatos({ aproximacion_minima: Number(v) })}
              />
              {/* El área, solo si se da el coeficiente global. */}
              <CampoConfig
                etiqueta="U [W/m²K] (vacío = sin área)"
                valor={datosOp.coeficiente_global_U === undefined
                  ? "" : String(datosOp.coeficiente_global_U)}
                onChange={(v) => onDatos({
                  coeficiente_global_U: v === "" ? undefined : Number(v),
                })}
              />
              {datosOp.coeficiente_global_U ? (
                <>
                  <CampoConfig
                    etiqueta="F (corrección LMTD, ≤ 1)"
                    valor={String(datosOp.factor_correccion_F ?? 1)}
                    onChange={(v) => onDatos({ factor_correccion_F: Number(v) })}
                  />
                  <p className="text-[10px] leading-snug text-zinc-500">
                    A = |Q| / (U·ΔT<sub>ml</sub>·F). El coeficiente global depende del
                    ensuciamiento, la geometría y la velocidad: su rango típico es un factor
                    2 o más, y el área hereda esa incertidumbre.
                  </p>
                </>
              ) : (
                <p className="text-[10px] leading-snug text-zinc-500">
                  Sin U no hay área. Inventarle un valor por omisión sería dar como
                  resultado una suposición.
                </p>
              )}
              {/* Una por lado: son dos circuitos distintos (tubos y
                  carcasa) con geometrías y caudales distintos. */}
              <CampoCaidaPresion
                etiqueta="ΔP lado caliente [Pa]"
                valor={datosOp.caida_P_caliente}
                onCambio={(v) => onDatos({ caida_P_caliente: v })}
                nota={false}
              />
              <CampoCaidaPresion
                etiqueta="ΔP lado frío [Pa]"
                valor={datosOp.caida_P_frio}
                onCambio={(v) => onDatos({ caida_P_frio: v })}
                nota={false}
              />
              <label className="flex items-center gap-2 text-[11px] text-zinc-400">
                <input
                  type="checkbox"
                  checked={datosOp.contracorriente !== false}
                  onChange={(e) => onDatos({ contracorriente: e.target.checked })}
                />
                contracorriente
              </label>
              <p className="text-[10px] text-zinc-500">
                Lo que pierde la corriente caliente lo gana la fría. Si las temperaturas se
                cruzan, el equipo se rechaza: el calor no sube solo.
              </p>
            </>
          )}

          {/* -------------------------- dimensionado de la columna */}
          {datosOp.tipo === "columna" && datosOp.metodo !== "fug" && (
            <>
              <label className="flex items-center gap-2 text-[11px] text-zinc-300">
                <input
                  type="checkbox"
                  checked={datosOp.con_dimensionado === true}
                  onChange={(e) => onDatos({ con_dimensionado: e.target.checked })}
                />
                calcular el diámetro
              </label>
              {datosOp.con_dimensionado ? (
                <>
                  <CampoConfig
                    etiqueta="espaciado de platos [mm]"
                    valor={String(datosOp.espaciado_platos_mm ?? 600)}
                    onChange={(v) => onDatos({ espaciado_platos_mm: Number(v) })}
                  />
                  <CampoConfig
                    etiqueta="fracción de inundación"
                    valor={String(datosOp.fraccion_de_inundacion ?? 0.8)}
                    onChange={(v) => onDatos({ fraccion_de_inundacion: Number(v) })}
                  />
                  <p className="text-[10px] leading-snug text-zinc-500">
                    Correlación de Fair. Se dimensionan los <strong>dos extremos</strong> y
                    manda el mayor: el caudal de vapor no es el mismo arriba y abajo salvo
                    que q = 1, y las propiedades del fondo tampoco son las de la cabeza.
                  </p>
                  <p className="text-[10px] leading-snug text-zinc-500">
                    El espaciado va en <strong>milímetros</strong> y entre 150 y 900: es el
                    rango en el que la correlación está ajustada. Diseñar al 60 % en vez del
                    80 % cuesta un 15 % de diámetro, que son un 33 % más de sección.
                  </p>
                </>
              ) : null}
            </>
          )}

          {/* ------------------------------------ reactor de equilibrio */}
          {datosOp.tipo === "reactor_equilibrio" && (
            <>
              <EditorReaccion datos={datosOp} componentes={componentes} onDatos={onDatos} />
              <CampoCaidaPresion
                valor={datosOp.caida_P}
                onCambio={(v) => onDatos({ caida_P: v })}
              />
              <p className="text-[10px] text-zinc-500">
                El avance lo fija el equilibrio químico, ∏aᵢ^νᵢ = K_eq(T): no hace falta
                cinética ni volumen. Responde a «por mucho tanque que pongas, no pasas de
                aquí», que es el límite termodinámico del reactor cinético.
              </p>
            </>
          )}

          {/* ------------------------------------------------- PFR */}
          {datosOp.tipo === "reactor_pfr" && (
            <>
              <EditorReaccion datos={datosOp} componentes={componentes} onDatos={onDatos} />
              {/* En un tubo la caída es lo normal, no la excepción: es el
                  precio de la fricción a lo largo del lecho. */}
              <CampoCaidaPresion
                valor={datosOp.caida_P}
                onCambio={(v) => onDatos({ caida_P: v })}
              />
              <p className="text-[10px] text-zinc-500">
                Flujo pistón: la composición cambia a lo largo del tubo y la velocidad se
                integra, en vez de evaluarse en la salida como en el CSTR. Para el mismo
                volumen convierte más, porque la entrada reacciona a la velocidad del
                alimento.
              </p>
            </>
          )}

          {/* ------------------------------------------ absorbedor */}
          {datosOp.tipo === "absorbedor" && (
            <>
              <CampoConfig
                etiqueta="etapas teóricas"
                valor={String(datosOp.N_etapas ?? 6)}
                onChange={(v) => onDatos({ N_etapas: Number(v) })}
              />
              <CampoConfig
                etiqueta="T operación [K]"
                valor={String(datosOp.T_operacion ?? "")}
                onChange={(v) => onDatos({ T_operacion: v === "" ? undefined : Number(v) })}
              />
              {/* Del lado del gas: es donde ocurre. El gas sube pagando la
                  fricción del relleno y el líquido baja por gravedad. */}
              <CampoCaidaPresion
                etiqueta="ΔP del gas [Pa]"
                valor={datosOp.caida_P_gas}
                onCambio={(v) => onDatos({ caida_P_gas: v })}
                nota={false}
              />
              <p className="text-[10px] text-zinc-500">
                Método de Kremser. El gas entra por abajo y el líquido por arriba. Si lo
                dejas en blanco, opera a la temperatura del líquido que entra.
              </p>
              <p className="text-[10px] text-zinc-500">
                El mismo equipo DESORBE: si el líquido entra más cargado de lo que el
                equilibrio admite, el componente pasa al gas.
              </p>
              <p className="text-[10px] text-amber-500/70">
                Supone sistema diluido, caudales constantes y operación isoterma. Si se
                absorbe una fracción grande del gas, el método deja de valer y lo dice.
              </p>
            </>
          )}

          <CampoConfig etiqueta="P operación [Pa]" valor={String(datosOp.P_sistema)} onChange={(v) => onDatos({ P_sistema: Number(v) })} />
        </div>
      )}

      {variables.length === 0 ? (
        <p className="px-3 py-3 text-[11px] text-zinc-500">
          Este equipo no tiene variables propias — todo se define en sus corrientes.
        </p>
      ) : (
        <div className="px-3 py-2">
          <p className="mb-2 text-[10px] text-zinc-500">
            Escribe lo que conozcas. Lo que dejes en blanco lo calcula el simulador.
          </p>
          {variables.map((v) => {
            const clave = `${nodo.id}.${v}`;
            const estado = estadoDe(clave, dados, pool);
            const malo = clavesMalas.has(clave);
            const magnitudes = unidades.magnitudesDe(clave);
            const unidad = unidades.unidadDe(clave);
            const crudo = valorDe(clave, dados, pool);
            const mw = masasMolares[nodo.id];
            const masica = v === "F" && unidad?.magnitud === "flujo_masico";
            // Lo escrito ya esta en la unidad elegida; lo calculado llega
            // en SI. Un caudal en masa se convierte con la MW de la mezcla.
            const mostrado =
              crudo === null ? null
              : estado === "dado" ? crudo
              : masica ? (mw ? molARepresentacionMasica(crudo, mw, unidad!) : null)
              : desdeSI(crudo, unidad);
            return (
              <div key={v} className="mb-1.5">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-[11px] text-zinc-400">{etiquetaVariable(v, componentes)}</label>
                  <div className="flex items-center gap-1">
                    <input
                      className={`w-24 rounded border bg-zinc-800 p-1 text-right font-mono text-xs ${
                        malo ? "border-red-500 text-red-200"
                          : estado === "dado" ? "border-emerald-600 text-emerald-200"
                          : "border-zinc-700 text-zinc-100"
                      }`}
                      placeholder={estado === "calculado" && mostrado !== null ? formatear(mostrado, v) : "falta"}
                      value={dados[clave] ?? ""}
                      onChange={(e) => onValor(clave, e.target.value)}
                    />
                    {magnitudes.length > 0 ? (
                      <select
                        className="w-[74px] rounded border border-zinc-700 bg-zinc-800 p-1 text-[10px] text-zinc-300"
                        value={unidad?.simbolo ?? magnitudes[0].si}
                        onChange={(e) => unidades.elegir(clave, e.target.value)}
                        title="La unidad es de ESTA corriente: otra puede usar una distinta. La conversión se hace internamente."
                      >
                        {magnitudes.flatMap((m) => m.unidades).map((u) => (
                          <option key={u.simbolo} value={u.simbolo}>{u.etiqueta}</option>
                        ))}
                      </select>
                    ) : unidades.listo ? (
                      <span className="w-[74px] text-right text-[10px] text-zinc-600">adim.</span>
                    ) : (
                      // Sin tabla de unidades NO se puede afirmar que la
                      // variable sea adimensional: decirlo hacia que un
                      // backend caido disfrazara F, T y P de numeros puros.
                      <span
                        className="w-[74px] text-right text-[10px] text-amber-500"
                        title="No se pudo cargar la tabla de unidades del servidor; no se sabe en qué unidad está este valor."
                      >
                        ¿unidad?
                      </span>
                    )}
                    <button
                      className={`w-3 ${dados[clave] ? "text-zinc-600 hover:text-zinc-200" : "invisible"}`}
                      title="borrar este dato para que lo calcule"
                      onClick={() => onValor(clave, "")}
                    >
                      x
                    </button>
                  </div>
                </div>
                {masica && !mw && estado !== "dado" && (
                  <div className="text-right text-[10px] text-zinc-500">
                    para verlo en masa hace falta la composición de esta corriente
                  </div>
                )}
                {estado === "calculado" && mostrado !== null && (
                  <div className="text-right text-[10px] text-sky-400">
                    calculado: {formatear(mostrado, v)} {unidad?.etiqueta ?? ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Guia({
  diagnostico, incognitas, completo, componentes, onIrA, redundancias,
}: {
  diagnostico: InformeBloque[];
  incognitas: string[];
  completo: boolean | null;
  componentes: string[];
  onIrA: (nodoId: string) => void;
  redundancias: Redundancia[];
}) {
  const bloqueados = diagnostico.filter((d) => !d.puede_dispararse);

  // Se cuenta cuantas ecuaciones bloqueadas desbloquearia cada variable:
  // las que aparecen en mas sitios son las que mas conviene dar primero.
  const conteo = new Map<string, number>();
  for (const b of bloqueados) {
    for (const v of b.faltantes_para_disparar) conteo.set(v, (conteo.get(v) ?? 0) + 1);
  }
  const sugeridas = [...conteo.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <div className="px-3 py-3">
      <h2 className="mb-1 text-sm font-semibold">Qué falta</h2>

      {redundancias.length > 0 && (
        <div className="mb-3 rounded border border-amber-700/60 bg-amber-950/30 p-2">
          <div className="mb-1 text-[11px] font-medium text-amber-200">Dónde sobran datos</div>
          <p className="mb-1.5 text-[10px] text-amber-100/70">
            Estas ecuaciones tienen más datos de los que necesitan. No es un error, pero por eso puede
            decir que sobran datos y que a la vez faltan variables: están mal repartidos.
          </p>
          {redundancias.map((r) => (
            <div key={r.bloque} className="mb-1 text-[10px]">
              <div className="text-zinc-300">{r.bloque}</div>
              <div className="font-mono text-zinc-500">
                diste {r.dados.join(", ")} · necesita {r.necesarios}
              </div>
            </div>
          ))}
        </div>
      )}

      {completo === null && (
        <p className="text-[11px] text-zinc-500">
          Escribe valores en las corrientes y equipos, y pulsa <strong>Resolver</strong>. Haz clic en cualquier
          elemento del diagrama para editarlo aquí.
        </p>
      )}

      {completo === true && (
        <p className="rounded border border-emerald-800 bg-emerald-950/40 p-2 text-[11px] text-emerald-300">
          Resuelto por completo: todas las variables quedaron determinadas.
        </p>
      )}

      {completo === false && (
        <>
          <p className="mb-2 text-[11px] text-amber-300">
            Faltan {incognitas.length} variables. El simulador no puede avanzar hasta desbloquear alguna ecuación.
          </p>

          {sugeridas.length > 0 && (
            <div className="mb-3">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
                Dar una de éstas desbloquea más cosas
              </div>
              {sugeridas.map(([clave, cuantas]) => {
                const [nodoId, variable] = clave.split(".");
                return (
                  <button
                    key={clave}
                    onClick={() => onIrA(nodoId)}
                    className="mb-1 flex w-full items-center justify-between rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-left hover:border-emerald-500"
                  >
                    <span className="font-mono text-[11px] text-zinc-200">
                      {nodoId}.<span className="text-emerald-300">{etiquetaVariable(variable, componentes)}</span>
                    </span>
                    <span className="text-[10px] text-zinc-500">desbloquea {cuantas}</span>
                  </button>
                );
              })}
            </div>
          )}

          <div className="text-[10px] uppercase tracking-wide text-zinc-500">Ecuaciones bloqueadas</div>
          {bloqueados.map((b) => (
            <div key={b.bloque} className="mb-1.5 rounded border border-zinc-800 bg-zinc-950 p-1.5">
              <div className="text-[11px] text-zinc-300">{b.bloque}</div>
              <div className="font-mono text-[10px] text-zinc-500">
                necesita: {b.faltantes_para_disparar.join(", ") || "(nada)"}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function CampoConfig({ etiqueta, valor, onChange }: { etiqueta: string; valor: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <label className="text-[11px] text-zinc-400">{etiqueta}</label>
      <input
        className="w-28 rounded border border-zinc-700 bg-zinc-800 p-1 text-right font-mono text-xs"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}


/**
 * Editor de la reaccion.
 *
 * Antes la estequiometria se escribia como una cadena suelta ("-1,-1,1")
 * en la que habia que acordarse del orden de los componentes y del signo,
 * y no habia forma de comprobar lo que se habia puesto sin resolver. Aqui
 * cada componente tiene su propio control, con su papel (reactivo /
 * producto / no participa) elegido aparte del coeficiente, y la ecuacion
 * se ve escrita debajo mientras se edita.
 */
/**
 * El campo de caida de presion, y la nota que explica lo que no se ve.
 *
 * La nota no es decorativa: el estado de SALIDA se evalua a la presion de
 * salida, asi que subir la caida aumenta la fraccion vaporizada. Quien no
 * lo sepa puede leer el resultado como un error del simulador cuando es
 * justo lo contrario -- evaluarlo a la presion de entrada esconderia que
 * la corriente sale en dos fases.
 */
function CampoCaidaPresion({
  valor, onCambio, etiqueta = "caída de presión [Pa]", nota = true,
}: {
  valor: number | undefined;
  onCambio: (v: number) => void;
  etiqueta?: string;
  nota?: boolean;
}) {
  const dP = valor ?? 0;
  return (
    <>
      <CampoConfig etiqueta={etiqueta} valor={String(dP)} onChange={(v) => onCambio(Number(v))} />
      {nota && dP > 0 && (
        <p className="text-[10px] leading-snug text-zinc-500">
          El estado de salida se evalúa a la presión de <strong>salida</strong>, así que con
          caída sale algo más de vapor. Es lo correcto: a la presión de entrada se
          escondería que la corriente sale en dos fases.
        </p>
      )}
    </>
  );
}

function EditorReaccion({
  datos, componentes, onDatos,
}: {
  datos: DatosOperacion;
  componentes: string[];
  onDatos: (cambio: Partial<DatosOperacion>) => void;
}) {
  const reacciones = listaReacciones(datos);
  const varias = reacciones.length > 1;
  const nEntradas = Math.max(1, datos.n_entradas ?? 1);

  const coefsDe = (r: ReaccionUI) =>
    componentes.map((_, i) => {
      const partes = (r.nu ?? "").split(",");
      const v = Number((partes[i] ?? "").trim());
      return Number.isFinite(v) ? v : 0;
    });

  const cambiarReaccion = (j: number, cambio: Partial<ReaccionUI>) => {
    onDatos(guardarReacciones(reacciones.map((r, k) => (k === j ? { ...r, ...cambio } : r))));
  };

  const escribirCoef = (j: number, indice: number, valor: number) => {
    const nuevos = [...coefsDe(reacciones[j])];
    nuevos[indice] = valor;
    cambiarReaccion(j, { nu: nuevos.join(",") });
  };

  const anadirReaccion = () => {
    // La nueva arranca VACIA, no copiando la anterior: dos reacciones con
    // la misma estequiometria son indistinguibles y el sistema que reparte
    // los avances sale singular. Copiarla parece un atajo amable y lleva
    // derecho a un error que cuesta entender.
    onDatos(guardarReacciones([
      ...reacciones,
      { nu: componentes.map(() => 0).join(","), A: A_POR_DEFECTO, Ea: EA_POR_DEFECTO },
    ]));
  };

  const quitarReaccion = (j: number) => {
    onDatos(guardarReacciones(reacciones.filter((_, k) => k !== j)));
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">
          {varias ? `Reacciones (${reacciones.length})` : "Reacción"}
        </span>
        <button
          onClick={anadirReaccion}
          className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400 hover:border-emerald-500 hover:text-emerald-300"
          title="Casi ningún sistema real tiene una sola reacción. Añadir otra hace que los avances pasen a llamarse ξ₀, ξ₁… y que el calor y el balance sumen las dos."
        >
          + reacción
        </button>
      </div>

      {reacciones.map((reaccion, j) => {
      const coefs = coefsDe(reaccion);
      const escribir = (indice: number, valor: number) => escribirCoef(j, indice, valor);
      const ecuacion = ecuacionReaccion(coefs.join(","), componentes);
      return (
      <div key={j} className={varias ? "space-y-1 rounded border border-zinc-800 bg-zinc-900/40 p-2" : "space-y-1"}>
      {varias && (
        <div className="flex items-center justify-between pb-0.5">
          <span className="font-mono text-[10px] text-emerald-400">
            ξ{"₀₁₂₃₄₅₆₇₈₉"[j] ?? j} — reacción {j + 1}
          </span>
          <button
            onClick={() => quitarReaccion(j)}
            className="text-[10px] text-zinc-500 hover:text-red-400"
          >
            quitar
          </button>
        </div>
      )}
      <div className="space-y-1">
        {componentes.map((nombre, i) => {
          const papel = coefs[i] < 0 ? "reactivo" : coefs[i] > 0 ? "producto" : "ninguno";
          return (
            <div key={nombre} className="flex items-center gap-1.5">
              <span className="w-[86px] truncate text-[11px] text-zinc-300" title={nombre}>
                {nombre}
              </span>
              <select
                className={`w-[78px] rounded border border-zinc-700 bg-zinc-800 p-0.5 text-[10px] ${
                  papel === "reactivo" ? "text-orange-300"
                  : papel === "producto" ? "text-emerald-300" : "text-zinc-500"
                }`}
                value={papel}
                onChange={(e) => {
                  const p = e.target.value;
                  const magnitud = Math.abs(coefs[i]) || 1;
                  escribir(i, p === "reactivo" ? -magnitud : p === "producto" ? magnitud : 0);
                }}
              >
                <option value="reactivo">reactivo</option>
                <option value="producto">producto</option>
                <option value="ninguno">no entra</option>
              </select>
              <input
                type="number"
                min={0}
                step={1}
                disabled={papel === "ninguno"}
                className="w-[52px] rounded border border-zinc-700 bg-zinc-800 p-0.5 text-right font-mono text-[11px] text-zinc-100 disabled:opacity-40"
                value={Math.abs(coefs[i]) || ""}
                placeholder="0"
                onChange={(e) => {
                  const magnitud = Math.abs(Number(e.target.value)) || 0;
                  escribir(i, papel === "reactivo" ? -magnitud : magnitud);
                }}
                title="Coeficiente estequiométrico (solo la magnitud; el signo lo pone el papel)"
              />
            </div>
          );
        })}
      </div>

      <div className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1.5">
        {ecuacion ? (
          <span className="font-mono text-[11px] text-emerald-300">{ecuacion}</span>
        ) : (
          <span className="text-[10px] text-amber-500">
            Marca al menos un reactivo y un producto.
          </span>
        )}
      </div>

      {/* Arrhenius va DENTRO de cada reacción: cada una tiene su propia
          velocidad, y es justo esa diferencia la que decide la
          selectividad. Tenerlo fuera sugeriría que lo comparten. */}
      {datos.con_cinetica !== false && (
        <div className="grid grid-cols-2 gap-1.5 pt-0.5">
          <CampoConfig
            etiqueta="A (Arrhenius)"
            valor={String(reaccion.A ?? A_POR_DEFECTO)}
            onChange={(v) => cambiarReaccion(j, { A: Number(v) })}
          />
          <CampoConfig
            etiqueta="Ea [J/mol]"
            valor={String(reaccion.Ea ?? EA_POR_DEFECTO)}
            onChange={(v) => cambiarReaccion(j, { Ea: Number(v) })}
          />
        </div>
      )}
      </div>
      );
      })}

      {varias && (
        <p className="text-[10px] leading-snug text-zinc-500">
          Los avances se llaman ξ₀, ξ₁…, y hacen falta tantos datos como reacciones: los avances,
          o las fracciones de salida de tantos componentes como reacciones. Una sola conversión X
          no basta — no dice cómo se reparte el reactivo entre ellas.
        </p>
      )}

      <label className="block pt-1 text-[10px] text-zinc-500">corrientes de entrada</label>
      <div className="flex items-center gap-1.5">
        <button
          className="rounded border border-zinc-700 px-2 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-30"
          disabled={nEntradas <= 1}
          onClick={() => onDatos({ n_entradas: nEntradas - 1 })}
          title="Quitar una entrada. Si estaba conectada, desconéctala antes."
        >
          −
        </button>
        <span className="w-6 text-center font-mono text-xs text-zinc-100">{nEntradas}</span>
        <button
          className="rounded border border-zinc-700 px-2 text-xs text-zinc-300 hover:bg-zinc-800"
          onClick={() => onDatos({ n_entradas: nEntradas + 1 })}
          title="Añadir otro puerto de entrada: el reactor mezcla internamente todas sus alimentaciones"
        >
          +
        </button>
        <span className="text-[10px] leading-snug text-zinc-500">
          se mezclan dentro del reactor
        </span>
      </div>

      <label className="flex items-center gap-2 pt-1 text-[11px] text-zinc-300">
        <input
          type="checkbox"
          checked={datos.con_cinetica !== false}
          onChange={(e) => onDatos({ con_cinetica: e.target.checked })}
        />
        resolver con cinética
      </label>
      {datos.con_cinetica === false && (
        <p className="text-[10px] leading-snug text-zinc-500">
          Sin cinética el reactor solo hace balances: hay que darle el avance ξ o la conversión X, y no se
          puede dimensionar el volumen.
        </p>
      )}
    </>
  );
}

/**
 * Nombre del elemento, editable in situ.
 *
 * Los nombres automaticos (s1, col1, r1) sirven para empezar, pero un
 * diagrama que se va a leer o compartir necesita nombres que signifiquen
 * algo ("alimentacion", "reactor-MTBE"). El renombrado tiene que arrastrar
 * las aristas, los datos y las unidades -- de eso se encarga onRenombrar;
 * aqui solo se recoge el texto y se muestra el motivo si se rechaza.
 */
function NombreEditable({
  nodoId, onRenombrar,
}: { nodoId: string; onRenombrar: (viejo: string, nuevo: string) => string | null }) {
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState(nodoId);
  const [error, setError] = useState<string | null>(null);

  function confirmar() {
    const fallo = onRenombrar(nodoId, borrador);
    if (fallo) { setError(fallo); return; }
    setError(null);
    setEditando(false);
  }

  if (!editando) {
    return (
      <button
        className="block max-w-full truncate text-left text-sm font-semibold hover:underline"
        title="Clic para renombrar este elemento"
        onClick={() => { setBorrador(nodoId); setError(null); setEditando(true); }}
      >
        {nodoId}
      </button>
    );
  }

  return (
    <div>
      <input
        autoFocus
        className={`w-full rounded border bg-zinc-800 px-1 py-0.5 text-sm font-semibold ${
          error ? "border-red-600" : "border-zinc-600"
        }`}
        value={borrador}
        onChange={(e) => { setBorrador(e.target.value); setError(null); }}
        onBlur={confirmar}
        onKeyDown={(e) => {
          if (e.key === "Enter") confirmar();
          if (e.key === "Escape") { setError(null); setEditando(false); }
        }}
      />
      {error && <div className="mt-0.5 text-[10px] text-red-400">{error}</div>}
    </div>
  );
}
