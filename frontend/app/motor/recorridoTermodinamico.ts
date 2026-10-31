/** Derivación termodinámica de la hoja (ARCHITECTURE.md §2, principio 10 y §8 «cada ecuación en su
 * lugar»): parte SIEMPRE de las relaciones termodinámicas fundamentales y, supuesto a supuesto, llega a la
 * relación de estado que usa el modelo. Los supuestos termodinámicos (número de fases, cambio de fase,
 * densidad constante, u(T) declarada) se declaran aquí, no en el balance de energía; el balance de energía
 * los usa (formulacionEnergiaHoja los añade a su formulación efectiva). */
import type { FormulacionEnergia, RecorridoEnergia } from './recorridoEnergia';
import type { HojaMotor } from './hojasMotor';

export type SupuestosTermo = Pick<FormulacionEnergia, 'monofasico' | 'sinCambioFase' | 'densidadConstante' | 'modelo' | 'soloLiquido' | 'referenciaFormacion'>;
export const CLAVES_TERMO = ['monofasico', 'sinCambioFase', 'densidadConstante', 'modelo', 'soloLiquido', 'referenciaFormacion'] as const;
export const TERMO_FUNDAMENTAL: SupuestosTermo = { monofasico: false, sinCambioFase: false, densidadConstante: false, modelo: 'sin_declarar' };
/** Additive assumptions (30 October 2026): present only once recorded, so earlier documents are unchanged. */
export const TERMO_OPCIONAL: Required<Pick<SupuestosTermo, 'soloLiquido' | 'referenciaFormacion'>> = { soloLiquido: false, referenciaFormacion: null };
/** The value that removes an assumption: its fundamental value, or the optional default. */
export const valorRetirado = (clave: keyof SupuestosTermo): SupuestosTermo[keyof SupuestosTermo] =>
  Object.hasOwn(TERMO_FUNDAMENTAL, clave) ? TERMO_FUNDAMENTAL[clave] : TERMO_OPCIONAL[clave as keyof typeof TERMO_OPCIONAL];
export type PasoTermo = { titulo: string; supuestos: SupuestosTermo; relaciones: string[]; operation?: {changes:Partial<SupuestosTermo>} | null };
export type RecorridoTermodinamico = { version: 1; pasos: PasoTermo[]; rehacer: PasoTermo[] };

export const TITULO_FUNDAMENTAL_TERMO = 'Fundamental thermodynamic relations';
export const iniciarTermo = (): RecorridoTermodinamico => ({ version: 1, pasos: [{ titulo: TITULO_FUNDAMENTAL_TERMO, supuestos: { ...TERMO_FUNDAMENTAL }, relaciones: [], operation:null }], rehacer: [] });
export const actualTermo = (r: RecorridoTermodinamico) => r.pasos[r.pasos.length - 1];
export function operarTermo(r: RecorridoTermodinamico, titulo: string, cambios: Partial<SupuestosTermo>, relaciones: string[] = []): RecorridoTermodinamico {
  const previa = actualTermo(r).supuestos, s = { ...previa, ...cambios };
  if (JSON.stringify(s) === JSON.stringify(previa)) return r;
  return { version: 1, pasos: [...r.pasos, { titulo, supuestos: s, relaciones, operation:{changes:structuredClone(cambios)} }], rehacer: [] };
}
export function volverTermo(r: RecorridoTermodinamico, indice: number): RecorridoTermodinamico {
  if (!Number.isInteger(indice) || indice < 0 || indice >= r.pasos.length) return r;
  return { ...r, pasos: r.pasos.slice(0, indice + 1), rehacer: [...r.pasos.slice(indice + 1), ...r.rehacer] };
}
export const rehacerTermo = (r: RecorridoTermodinamico): RecorridoTermodinamico => r.rehacer.length ? { ...r, pasos: [...r.pasos, r.rehacer[0]], rehacer: r.rehacer.slice(1) } : r;

/** Los supuestos que se pueden declarar, con la relación que introducen. */
export const OPERACIONES_TERMO: { clave: keyof SupuestosTermo; nombre: string; valor: SupuestosTermo[keyof SupuestosTermo]; relacion: string; efecto: string }[] = [
  { clave: 'monofasico', nombre: 'Assume a single phase', valor: true, relacion: String.raw`N_{\mathrm{fases}}=1`, efecto: 'Restrict the present phase count to one; stop if equilibrium requires another phase.' },
  { clave: 'sinCambioFase', nombre: 'No phase change', valor: true, relacion: String.raw`\{\text{fases}\}(t)=\{\text{fases}\}(0)`, efecto: 'The initial phase set must remain valid throughout the calculation.' },
  { clave: 'densidadConstante', nombre: 'Constant mixture density', valor: true, relacion: String.raw`\rho=\rho_*,\qquad V=\frac{m}{\rho_*}`, efecto: 'Volume state relation: an incompressible liquid with declared density.' },
  { clave: 'soloLiquido', nombre: 'Liquid-only phase set', valor: true, relacion: String.raw`\mathcal P\subseteq\{\mathrm{liquid}\}`, efecto: 'The vapour is not modelled (for example acetic acid); requires the single-phase liquid policy of the package.' },
  { clave: 'referenciaFormacion', nombre: 'Liquid formation reference', valor: 'liquido', relacion: String.raw`\bar h_i(T_0,P_0)=\Delta_f h_i^{\circ,\mathrm{liq}}`, efecto: 'Package energies carry the tabulated liquid formation data, so the reaction heat needs no source term.' },
  { clave: 'referenciaFormacion', nombre: 'Ideal-gas formation reference', valor: 'gas', relacion: String.raw`\bar h_i^{\mathrm{ig}}(T_0,P_0)=\Delta_f h_i^{\circ,\mathrm{ig}}`, efecto: 'Package energies carry the ideal-gas formation data; refused for liquid-only species.' },
  { clave: 'modelo', nombre: 'Declared linear u(T) law', valor: 'u_lineal', relacion: String.raw`u(T)=u_{\mathrm{ref}}+c_u\,(T-T_{\mathrm{ref}}),\qquad c_u>0`, efecto: 'Internal-energy relation, valid in the declared interval [T_min, T_max] monitored by the Engine.' },
];

/** Relaciones de estado vigentes con los supuestos declarados (las que el balance de energía usa). */
export function relacionesTermo(s: SupuestosTermo): string[] {
  const r: string[] = [];
  if (s.monofasico) r.push(String.raw`N_{\mathrm{fases}}=1`);
  if (s.sinCambioFase) r.push(String.raw`\text{constant phase regime}`);
  if (s.modelo === 'u_lineal') r.push(String.raw`u(T)=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}}),\quad c_u>0`, String.raw`T=T_{\mathrm{ref}}+\frac{U/m-u_{\mathrm{ref}}}{c_u}`, String.raw`U=m\,u(T)`);
  if (s.densidadConstante) r.push(String.raw`V=\frac{m}{\rho_*},\quad\frac{dV}{dt}=\frac{1}{\rho_*}\frac{dm}{dt}`);
  return r;
}

const termoDe = (f: FormulacionEnergia): SupuestosTermo => ({ monofasico: f.monofasico, sinCambioFase: f.sinCambioFase, densidadConstante: f.densidadConstante, modelo: f.modelo });
const sinTermo = (f: FormulacionEnergia): FormulacionEnergia => ({ ...f, ...TERMO_FUNDAMENTAL });

/** Migración sin pérdida de una derivación de energía anterior: los pasos que declaraban supuestos
 * termodinámicos pasan, en el mismo orden y con sus relaciones, a la derivación termodinámica; la de
 * energía conserva el resto. La formulación efectiva (energía + termodinámica) no cambia. */
export function separarTermodinamica(e: RecorridoEnergia): { energia: RecorridoEnergia; termo: RecorridoTermodinamico } {
  let termo = iniciarTermo();
  const pasos: RecorridoEnergia['pasos'] = [];
  e.pasos.forEach((p, i) => {
    const antes = i ? termoDe(e.pasos[i - 1].formulacion) : TERMO_FUNDAMENTAL, ahora = termoDe(p.formulacion);
    const cambiaTermo = JSON.stringify(antes) !== JSON.stringify(ahora);
    const cambiaEnergia = !i || JSON.stringify(sinTermo(e.pasos[i - 1].formulacion)) !== JSON.stringify(sinTermo(p.formulacion)) || JSON.stringify(e.pasos[i - 1].contexto) !== JSON.stringify(p.contexto);
    if (cambiaTermo) termo = { ...termo, pasos: [...termo.pasos, { titulo: p.titulo, supuestos: ahora, relaciones: cambiaEnergia ? [] : p.relaciones }] };
    if (cambiaEnergia) pasos.push({ ...p, ...(p.operation?{operation:{changes:Object.fromEntries(Object.entries(p.operation.changes).filter(([key])=>!CLAVES_TERMO.includes(key as typeof CLAVES_TERMO[number])))}}:{}), formulacion: sinTermo(p.formulacion) });
  });
  return { energia: { ...e, pasos: pasos.length ? pasos : [{ ...e.pasos[0], formulacion: sinTermo(e.pasos[0].formulacion) }], rehacer: [] }, termo };
}

/** La hoja con su derivación termodinámica separada de la de energía (idempotente). */
export function migrarTermoHoja(h: HojaMotor): HojaMotor {
  if (h.redTermodinamica || h.recorridoTermodinamico || !h.energia) return h;
  const { energia, termo } = separarTermodinamica(h.energia.historial);
  return { ...h, energia: { ...h.energia, historial: energia }, recorridoTermodinamico: termo };
}
export const recorridoTermoHoja = (h: HojaMotor): RecorridoTermodinamico => migrarTermoHoja(h).recorridoTermodinamico ?? iniciarTermo();
/** Declarar o retirar un supuesto termodinámico de la hoja: un paso de su derivación termodinámica. */
export function cambiarTermoHoja(h: HojaMotor, titulo: string, cambios: Partial<SupuestosTermo>, relaciones: string[] = []): HojaMotor {
  const m = migrarTermoHoja(h);
  return { ...m, recorridoTermodinamico: operarTermo(m.recorridoTermodinamico ?? iniciarTermo(), titulo, cambios, relaciones) };
}
