'use client';
/** Derivación de un volumen de una red termodinámica, desde su ecuación fundamental (ARQUITECTURA_MOTOR.md §2,
 * principio 10: todo modelo parte de las ecuaciones fundamentales y llega, supuesto a supuesto, al modelo; nunca
 * se plantea directamente). La red no guarda su diario de pasos: se reconstruye con las mismas funciones que las
 * derivaciones de materia y energía de la hoja, a partir de los supuestos que declara el volumen. Es presentación;
 * las ecuaciones que se resuelven son las que ensambla el Engine, que se muestran debajo. */
import FormulaMateria from './FormulaMateria';
import styles from './balances.module.css';
import type { SolicitudEnsamblajeV2, VolumenV2 } from './contratoEnsamblajeV2';
import type { FormulacionMateria } from './recorridoMateria';
import { balanceActual, iniciarRecorrido } from './recorridoMateria';
import type { ContextoEnergia, FormulacionEnergia } from './recorridoEnergia';
import { ENERGIA_FUNDAMENTAL, ecuacionEnergia } from './recorridoEnergia';
import { CLAVES_TERMO } from './recorridoTermodinamico';

const SUPUESTOS_MATERIA: [string, string, string][] = [
  ['campo.sinReaccion', 'Sin reacción química', String.raw`r_i=0`],
  ['campo.sinGeneracion', 'Sin generación', String.raw`G_i=0`],
  ['campo.sinConsumo', 'Sin consumo', String.raw`C_i=0`],
  ['campo.sinDifusion', 'Sin difusión', String.raw`\mathbf j_i=\mathbf 0`],
  ['campo.sinConveccion', 'Sin convección', String.raw`\rho_i\mathbf v=\mathbf 0`],
  ['campo.estacionario', 'Estacionario local', String.raw`\partial\rho_i/\partial t=0`],
  ['fija', 'Frontera fija', String.raw`\mathbf v_b=\mathbf 0`],
  ['restoImpermeable', 'Resto de la frontera impermeable', String.raw`\rho_i(\mathbf v-\mathbf v_b)\cdot\mathbf n=0\ \text{en }S_{\mathrm{resto}}`],
  ['uniforme', 'Composición uniforme', String.raw`\rho_i(\mathbf x,t)=\rho_i(t)`],
  ['generacionUniforme', 'Generación uniforme en el volumen', String.raw`G_i=\gamma_i V`],
  ['consumoUniforme', 'Consumo uniforme en el volumen', String.raw`C_i=\chi_i V`],
  ['sinAcumulacion', 'Sin acumulación', String.raw`dm_i/dt=0`],
];
const SUPUESTOS_ENERGIA: [keyof FormulacionEnergia, string, string][] = [
  ['separarPresion', 'Separar presión y viscosidad', String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`],
  ['entalpia', 'Agrupar el trabajo de flujo en entalpía', String.raw`h=u+p/\rho`],
  ['sinCinetica', 'Energía cinética despreciable', String.raw`e_c\simeq0`],
  ['sinTrabajoViscoso', 'Trabajo viscoso despreciable', String.raw`\dot W_\tau=0`],
  ['sinFuerzasVolumen', 'Sin trabajo de fuerzas de volumen', String.raw`\dot W_{\mathbf b}=0`],
  ['sinFuenteVolumetrica', 'Sin aporte volumétrico', 'R=0'],
  ['adiabatico', 'Frontera adiabática', String.raw`\dot Q=0`],
  ['sinConduccionLocal', 'Flujo no convectivo local nulo', String.raw`\mathbf q=\mathbf 0`],
  ['uniforme', 'Temperatura y energía específica uniformes', String.raw`T(\mathbf x,t)=T(t),\quad U=m\bar u`],
  ['presionUniforme', 'Presión espacialmente uniforme', String.raw`p(\mathbf x,t)=P(t)`],
  ['presionPrescrita', 'Presión impuesta', String.raw`P(t)=P_{\mathrm{ext}}(t)`],
  ['estacionario', 'Sin acumulación local', String.raw`\partial(\rho e)/\partial t=0`],
  ['sinAcumulacionTotal', 'Sin acumulación total', String.raw`dE/dt=0`],
];
const leer = (o: Record<string, unknown>, ruta: string) => ruta.split('.').reduce<unknown>((x, k) => (x as Record<string, unknown> | undefined)?.[k], o);

function puertos(s: SolicitudEnsamblajeV2, v: VolumenV2) {
  return s.corrientes.filter(c => c.desde === v.id || c.hasta === v.id).map((c, k) => ({ id: k + 1, sentido: c.hasta === v.id ? 'entrada' as const : 'salida' as const, constante: true }));
}

export default function DerivacionVolumenRed({ s, v, panel }: { s: SolicitudEnsamblajeV2; v: VolumenV2; panel: 'materia' | 'energia' }) {
  const ports = puertos(s, v), comps = s.componentes.filter(c => v.componenteIds.includes(c.id));
  const pasos: { titulo: string; latex: string; relacion?: string }[] = [];
  if (panel === 'materia') {
    const fund = { ...iniciarRecorrido().pasos[0].formulacion, componentes: comps, fronteras: ports } as FormulacionMateria;
    const fin = { ...fund, ...v.formulacionMateria, componentes: comps, fronteras: ports } as FormulacionMateria;
    pasos.push({ titulo: 'Conservación local de cada componente', latex: balanceActual(fund) });
    for (const [ruta, nombre, relacion] of SUPUESTOS_MATERIA) if (leer(fin as unknown as Record<string, unknown>, ruta) === true && leer(fund as unknown as Record<string, unknown>, ruta) !== true) pasos.push({ titulo: nombre, latex: '', relacion });
    if (fin.vista !== 'campo') pasos.push({ titulo: 'Integrar sobre el volumen de control (Gauss y Reynolds)', latex: balanceActual({ ...fin, vista: 'integral' }) });
    if (fin.vista === 'cantidad') pasos.push({ titulo: 'Forma total: particionar la frontera en corrientes', latex: balanceActual(fin) });
  } else {
    const ctx: ContextoEnergia = { volumenId: v.id, fija: !!v.formulacionMateria.fija, restoCerrado: !!v.formulacionMateria.restoImpermeable, puertos: ports, componentesIds: v.componenteIds };
    const termo = new Set<string>(CLAVES_TERMO);
    const fin: FormulacionEnergia = { ...v.formulacionEnergia, ...Object.fromEntries(CLAVES_TERMO.map(k => [k, ENERGIA_FUNDAMENTAL[k]])) };
    pasos.push({ titulo: 'Conservación local de la energía (primer principio)', latex: ecuacionEnergia(ENERGIA_FUNDAMENTAL, ctx) });
    for (const [clave, nombre, relacion] of SUPUESTOS_ENERGIA) if (!termo.has(clave) && fin[clave] === true && ENERGIA_FUNDAMENTAL[clave] !== true) pasos.push({ titulo: nombre, latex: '', relacion });
    pasos.push({ titulo: 'Forma total con los supuestos del volumen', latex: ecuacionEnergia(fin, ctx) });
  }
  return <section aria-label={`Derivación de ${panel} desde la ecuación fundamental`}>
    <h3 className={styles.notaTermo}>Desde la ecuación fundamental · supuestos que declara el volumen</h3>
    {pasos.map((p, i) => <article key={i} className={styles.pasoEnergia} aria-label={`Paso ${i + 1}: ${p.titulo}`}><div className={styles.numeroEnergia}>{String(i + 1).padStart(2, '0')}</div><div><header><h3>{p.titulo}</h3></header>
      {p.latex && <div className={styles.formula}><FormulaMateria latex={p.latex} lectura={p.titulo} bloque /></div>}
      {p.relacion && <div className={styles.identidadEnergia}><FormulaMateria latex={p.relacion} lectura={p.titulo} bloque /></div>}</div></article>)}
    {panel === 'energia' && <p className={styles.notaTermo}>Los supuestos de estado (fases, u(T), densidad) y el cierre con el paquete están en el panel Termodinámica.</p>}
    <h3 className={styles.notaTermo}>Ecuaciones que ensambla el Engine con esos supuestos</h3>
  </section>;
}
