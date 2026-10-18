import { CAMPO_GENERAL, COORDENADAS, ecuacionCampoReducida, estacionarioLocalDeducido, fuentesActivas, simboloFrontera, transporteRelativo, variableComponente } from './operadores';
import type { Coordenadas, FronteraConstante, OpcionesCampo } from './operadores';

export type FormaMateria = 'campo' | 'integral' | 'cantidad';
export const FORMAS_MATERIA: Record<FormaMateria, string> = { campo: 'Diferencial', integral: 'Integral', cantidad: 'Total' };
import type {Componente,ReglasEstadoMateria} from './materiaEstado';
import {concentracionConstante} from './reglasEstadoMateria';
export type ComponenteMateria = Componente;
export const indiceComponente = (c: ComponenteMateria) => c.simbolo.length === 1 ? c.simbolo : String.raw`\mathrm{${c.simbolo}}`;
export type FormulacionMateria = {
  componentes?: ComponenteMateria[];
  reglasEstado?: ReglasEstadoMateria;
  campo: OpcionesCampo;
  coordenadas: Coordenadas;
  expandida: boolean;
  vista: FormaMateria;
  fronteras: FronteraConstante[];
  uniforme: boolean;
  fija: boolean;
  sinAcumulacion: boolean;
  invariantes: boolean[];
  generacionUniforme: boolean;
  consumoUniforme: boolean;
  restoImpermeable: boolean;
  cantidadVolumen: boolean;
  densidadMediaConstante: boolean;
  densidadComunPuertos: boolean;
  expandirProducto: boolean;
};
export type PasoMateria = { titulo: string; formulacion: FormulacionMateria; origen: number | null; operacion: Partial<FormulacionMateria> | null };
export type RecorridoMateria = { pasos: PasoMateria[]; activo: number; rehacer?: PasoMateria[]; ultimoComponenteId?: number };
export type AccionMateria =
  | { tipo: 'cambiar'; titulo: string; cambios: Partial<FormulacionMateria> }
  | { tipo: 'ir'; indice: number }
  | { tipo: 'rehacer' }
  | { tipo: 'reiniciar' };

export function iniciarRecorrido(): RecorridoMateria {
  return { activo: 0, rehacer: [], ultimoComponenteId: 0, pasos: [{ titulo: 'Conservación local', origen: null, operacion: null, formulacion: {
    componentes: [], campo: { ...CAMPO_GENERAL }, coordenadas: 'cartesianas', expandida: false, vista: 'campo',
    fronteras: [], uniforme: false, fija: false, sinAcumulacion: false, invariantes: [false, false, false],
    generacionUniforme: false, consumoUniforme: false, restoImpermeable: false,
    cantidadVolumen: false, densidadMediaConstante: false, densidadComunPuertos: false, expandirProducto: false,
  } }] };
}

export function recorridoMateria(estado: RecorridoMateria, accion: AccionMateria): RecorridoMateria {
  if (accion.tipo === 'reiniciar') return iniciarRecorrido();
  if (accion.tipo === 'rehacer') {
    const paso = estado.rehacer?.[0];
    if (!paso) return estado;
    const pasos = [...estado.pasos, { ...paso, origen: estado.activo }];
    return { ...estado, pasos, activo: pasos.length - 1, rehacer: estado.rehacer!.slice(1) };
  }
  if (accion.tipo === 'ir') {
    if (accion.indice < 0 || accion.indice >= estado.pasos.length) return estado;
    const camino = indicesCamino(estado, accion.indice);
    const actual = indicesCamino(estado, estado.activo);
    const posicion = actual.indexOf(accion.indice);
    const futuros = posicion < 0 ? [] : actual.slice(posicion + 1).map(i => estado.pasos[i]);
    const pasos = camino.map((i, n) => ({ ...estado.pasos[i], origen: n ? n - 1 : null }));
    return { pasos, activo: pasos.length - 1, rehacer: [...futuros, ...(posicion < 0 ? [] : estado.rehacer ?? [])], ultimoComponenteId: maximoComponente(estado) };
  }
  const anterior = estado.pasos[estado.activo].formulacion;
  const formulacion = { ...anterior, ...accion.cambios };
  if (JSON.stringify(formulacion) === JSON.stringify(anterior)) return estado;
  // A continuation replaces cancelled work. Only its ancestor chain is retained.
  const previos = indicesCamino(estado, estado.activo).map((i, n) => ({ ...estado.pasos[i], origen: n ? n - 1 : null }));
  const pasos = [...previos, { titulo: accion.titulo, formulacion, origen: previos.length - 1, operacion: accion.cambios }];
  const nuevoMaximo = (formulacion.componentes ?? []).reduce((max, c) => Math.max(max, c.id), maximoComponente(estado));
  return { pasos, activo: pasos.length - 1, rehacer: [], ultimoComponenteId: nuevoMaximo };
}
function indicesCamino(h: RecorridoMateria, indice: number) {
  const camino: number[] = [];
  let actual: number | null = indice;
  while (actual !== null && h.pasos[actual] && !camino.includes(actual)) { camino.unshift(actual); actual = h.pasos[actual].origen; }
  return camino;
}
function maximoComponente(h: RecorridoMateria) {
  return [...h.pasos, ...(h.rehacer ?? [])].reduce((max, paso) => (paso.formulacion.componentes ?? []).reduce((m, c) => Math.max(m, c.id), max), h.ultimoComponenteId ?? 0);
}
export function siguientePaso(h: RecorridoMateria) {
  return h.rehacer?.length ? h.pasos.length : -1;
}
/** A complete single-species material has no diffusion relative to its own
 * mass-averaged velocity. This is an identity, not a user approximation. */
export function campoEfectivo(f: FormulacionMateria) {
  return f.componentes?.length === 1 ? { ...f.campo, sinDifusion: true } : f.campo;
}
function sinTransporteRelativo(f: FormulacionMateria) {
  const campo = campoEfectivo(f);
  return f.fija && campo.sinConveccion && campo.sinDifusion;
}
export function acumulacionTotalNula(f: FormulacionMateria,indice?:string) {
  return f.sinAcumulacion || (f.fija && (f.campo.estacionario || estacionarioLocalDeducido(campoEfectivo(f), f.coordenadas, f.invariantes)
    || (f.cantidadVolumen && concentracionConstante(f,indice))));
}
export function fuenteUniforme(f: FormulacionMateria, rol: 'generacion' | 'consumo') {
  return (rol === 'generacion' ? f.generacionUniforme : f.consumoUniforme) || f.invariantes.every(Boolean);
}
function fuenteTotal(f: FormulacionMateria, rol: 'generacion' | 'consumo', integral: boolean, indice = 'i') {
  const local = variableComponente(rol === 'generacion' ? String.raw`\gamma` : String.raw`\chi`, indice);
  const total = variableComponente(rol === 'generacion' ? 'G' : 'C', indice) + '(t)';
  if (fuenteUniforme(f, rol)) return `${local}(t)${f.fija ? 'V' : 'V(t)'}`;
  return integral ? String.raw`\int_{${f.fija ? 'V' : 'V(t)'}}${local}(\mathbf x,t)\,dV` : total;
}
function fuentes(f: FormulacionMateria, integral: boolean, divisor?: string, indice = 'i') {
  const activas = fuentesActivas(f.campo);
  return (['generacion', 'consumo'] as const).filter(rol => activas[rol]).map(rol => {
    const term = fuenteTotal(f, rol, integral, indice);
    return (rol === 'generacion' ? '+' : '-') + (divisor ? String.raw`\frac{${term}}{${divisor}}` : term);
  }).join('');
}
export function balanceIntegrado(f: FormulacionMateria, indice = 'i') {
  const rho = variableComponente(String.raw`\rho`, indice);
  const V = f.fija ? 'V' : 'V(t)';
  const lhs = acumulacionTotalNula(f) ? '0' : String.raw`\frac{d}{dt}\int_{${V}}${rho}\,dV`;
  const flujo = transporteRelativo(campoEfectivo(f), f.fija, indice);
  const rhs = (sinTransporteRelativo(f) ? '' : String.raw`-\oint_{\partial ${V}}\left(${flujo}\right)\!\cdot\mathbf n\,dA`) + fuentes(f, true, undefined, indice);
  return lhs + '=' + (rhs.startsWith('+') ? rhs.slice(1) : rhs || '0');
}
export type TerminoTotalMateria = {
  rol: 'entrada' | 'salida' | 'resto' | 'generacion' | 'consumo';
  signo: 1 | -1;
  componente: string;
  puertoId?: number;
  forma: 'flujo' | 'fuente_integrada' | 'tasa_por_volumen';
  latex: string;
};
/** A nonoverlapping surface partition: declared ports + their complement.
 * Undeclared exchange stays in Phi, never in an additional phantom port sum. */
export function terminosTotalesMateria(f: FormulacionMateria, indice = 'i'): TerminoTotalMateria[] {
  const t: TerminoTotalMateria[] = [];
  if (!sinTransporteRelativo(f)) {
    for (const sentido of ['entrada', 'salida'] as const) for (const p of f.fronteras.filter(p => p.sentido === sentido)) t.push({ rol: sentido, signo: sentido === 'entrada' ? 1 : -1, componente: indice, puertoId: p.id, forma: 'flujo', latex: simboloFrontera(p, indice) });
    if (!f.restoImpermeable) t.push({ rol: 'resto', signo: -1, componente: indice, forma: 'flujo', latex: String.raw`\Phi_{${indice},\mathrm{resto}}` });
  }
  const activas = fuentesActivas(f.campo);
  for (const rol of ['generacion', 'consumo'] as const) if (activas[rol]) t.push({ rol, signo: rol === 'generacion' ? 1 : -1, componente: indice, forma: fuenteUniforme(f, rol) ? 'tasa_por_volumen' : 'fuente_integrada', latex: fuenteTotal(f, rol, false, indice) });
  return t;
}
function ladoDerechoTotal(f: FormulacionMateria, indice: string, volumetricos = false) {
  const rho = variableComponente(String.raw`\bar\rho`, indice);
  return terminosTotalesMateria(f, indice).map((t, i) => {
    let latex = t.latex;
    if (volumetricos) {
      const p = f.fronteras.find(p => p.id === t.puertoId);
      latex = p ? p.constante === false ? `Q_{${p.id}}(t)` : String.raw`Q^{\mathrm{cte}}_{${p.id}}` : String.raw`\frac{${latex}}{${rho}}`;
    }
    return (t.signo < 0 ? '-' : i ? '+' : '') + latex;
  }).join('') || '0';
}
export function balanceTotal(f: FormulacionMateria, indice = 'i') {
  const masse = variableComponente('m', indice);
  const nula = acumulacionTotalNula(f,indice),constante=concentracionConstante(f,indice);
  if (!f.cantidadVolumen) return (nula ? '0' : String.raw`\frac{d${masse}}{dt}`) + '=' + ladoDerechoTotal(f, indice);
  const rho = variableComponente(String.raw`\bar\rho`, indice);
  if (constante && f.densidadComunPuertos) return (nula ? '0' : String.raw`\frac{dV}{dt}`) + '=' + ladoDerechoTotal(f, indice, true);
  const lhs = nula ? '0' : f.fija ? String.raw`V\frac{d${rho}}{dt}` : constante ? String.raw`${rho}\frac{dV}{dt}`
    : f.expandirProducto ? String.raw`${rho}(t)\frac{dV}{dt}+V(t)\frac{d${rho}}{dt}` : String.raw`\frac{d}{dt}\left[${rho}(t)V(t)\right]`;
  return lhs + '=' + ladoDerechoTotal(f, indice);
}
export function balanceActual(f: FormulacionMateria, indice = 'i') {
  return f.vista === 'campo' ? ecuacionCampoReducida({ ...campoEfectivo(f), generacionUniforme: fuenteUniforme(f, 'generacion'), consumoUniforme: fuenteUniforme(f, 'consumo') }, f.coordenadas, f.invariantes, f.expandida, indice)
    : f.vista === 'integral' ? balanceIntegrado(f, indice) : balanceTotal(f, indice);
}
export function unidadBalance(f: FormulacionMateria) {
  return f.vista === 'campo' ? 'kg/(m³·s)' : f.vista === 'cantidad' && f.cantidadVolumen && f.densidadMediaConstante && f.densidadComunPuertos ? 'm³/s' : 'kg/s';
}

/** Definition and assumption equations, separate from the conservation equation.
 * Only newly introduced relations are printed on a new worksheet row.
 */
export function relacionesMateria(f: FormulacionMateria, indice = 'i'): string[] {
  const rho = variableComponente(String.raw`\rho`, indice), media = variableComponente(String.raw`\bar\rho`, indice), masse = variableComponente('m', indice);
  const j = variableComponente(String.raw`\mathbf j`, indice), D = variableComponente('D', indice), w = variableComponente('w', indice);
  const gamma = variableComponente(String.raw`\gamma`, indice), chi = variableComponente(String.raw`\chi`, indice);
  const r: string[] = [];
  const V = f.fija ? 'V' : 'V(t)', activas = fuentesActivas(f.campo);
  if (f.fija) r.push(String.raw`\mathbf v_b=\mathbf0,\quad dV/dt=0`);
  if (f.campo.estacionario) r.push(String.raw`\partial${rho}/\partial t=0`);
  if (f.sinAcumulacion) r.push(String.raw`d${masse}/dt=0`);
  if (f.campo.sinConveccion) r.push(String.raw`\mathbf v=\mathbf0`);
  if (campoEfectivo(f).sinDifusion) r.push(String.raw`${j}=\mathbf0`);
  else if (f.campo.difusion !== 'flujo') r.push(f.campo.difusion === 'fick' ? String.raw`${j}=-\rho ${D}\nabla ${w}` : String.raw`${j}=-${D}\nabla${rho},\quad\nabla\rho=\mathbf0,\quad\nabla ${D}=\mathbf0`);
  f.invariantes.forEach((invariante, i) => { if (invariante) r.push(String.raw`\partial f/\partial ${COORDENADAS[f.coordenadas].ejes[i]}=0`); });
  if (f.vista === 'integral' || f.coordenadas !== 'cartesianas') r.push(f.coordenadas === 'cartesianas' ? String.raw`dV=dx\,dy\,dz`
    : f.coordenadas === 'cilindricas' ? String.raw`dV=r\,dr\,d\varphi\,dz` : String.raw`dV=r^2\sin\theta\,dr\,d\theta\,d\varphi`);
  if (!activas.generacion) r.push(`${gamma}=0`);
  if (!activas.consumo) r.push(`${chi}=0`);
  for (const rol of ['generacion', 'consumo'] as const) {
    if (!activas[rol]) continue;
    const local = rol === 'generacion' ? gamma : chi, total = variableComponente(rol === 'generacion' ? 'G' : 'C', indice) + '(t)';
    if (fuenteUniforme(f, rol)) r.push(`${local}(\\mathbf x,t)=${local}(t)`);
    if (f.vista !== 'campo') r.push(String.raw`${total}=\int_{${V}}${local}(\mathbf x,t)\,dV` + (fuenteUniforme(f, rol) ? `=${local}(t)${V}` : ''));
  }
  if (f.vista !== 'campo') {
    r.push(String.raw`${masse}(t)=\int_{${V}}${rho}(\mathbf x,t)\,dV`);
    const phi = transporteRelativo(campoEfectivo(f), f.fija, indice);
    if (f.vista === 'cantidad') {
      r.push(String.raw`\dot m_{${indice},p}(t)=\varepsilon_p\int_{A_p}\left(${phi}\right)\!\cdot\mathbf n\,dA,\quad\varepsilon_{\mathrm{ent}}=-1,\;\varepsilon_{\mathrm{sal}}=1`);
      r.push(f.restoImpermeable ? String.raw`\left(${phi}\right)\!\cdot\mathbf n=0\quad\text{en }S_{\mathrm{resto}}`
        : String.raw`\Phi_{${indice},\mathrm{resto}}=\int_{S_{\mathrm{resto}}}\left(${phi}\right)\!\cdot\mathbf n\,dA`);
    }
  }
  f.fronteras.forEach(p => {
    r.push(String.raw`\dot m_{${indice},${p.id}}(t)=${p.sentido === 'entrada' ? '-' : ''}\int_{A_{${p.id}}}\left(${transporteRelativo(campoEfectivo(f),f.fija,indice)}\right)\!\cdot\mathbf n\,dA`);
    if (p.constante !== false) r.push(String.raw`\dot m_{${indice},${p.id}}(t)=${simboloFrontera(p,indice)}`);
    if (f.uniforme) r.push(String.raw`\left(${transporteRelativo(campoEfectivo(f),f.fija,indice)}\right)\!\cdot\mathbf n=${p.sentido === 'entrada' ? '-' : ''}\frac{${simboloFrontera(p,indice)}}{A_{${p.id}}}`);
  });
  if (f.restoImpermeable && f.vista !== 'cantidad') r.push(String.raw`\left(${transporteRelativo(campoEfectivo(f),f.fija,indice)}\right)\!\cdot\mathbf n=0\quad\text{en }S_{\mathrm{resto}}`);
  if (f.cantidadVolumen) {
    r.push(String.raw`${media}(t)=\frac{1}{${V}}\int_{${V}}${rho}\,dV,\quad ${masse}(t)=${media}(t)${V},\quad ${V}>0`);
    if (concentracionConstante(f,indice)) r.push(String.raw`d${media}/dt=0`);
    if (concentracionConstante(f,indice) && f.densidadComunPuertos) r.push(String.raw`${j}\!\cdot\mathbf n=0\text{ en }A_p,\quad\rho_{${indice},p}=${media}>0,\quad\dot m_{${indice},p}=${media}Q_p`);
  }
  return r;
}
export function relacionesNuevas(paso: PasoMateria, origen?: PasoMateria) {
  const anteriores = new Set(origen ? relacionesFormulacion(origen.formulacion) : []);
  return relacionesFormulacion(paso.formulacion).filter(r => !anteriores.has(r));
}

export function crearComponente(h: RecorridoMateria, nombre: string): ComponenteMateria {
  const id = maximoComponente(h) + 1;
  return { id, nombre: nombre.trim(), simbolo: id <= 26 ? String.fromCharCode(64 + id) : `S${id}` };
}

export function balancesComponentes(f: FormulacionMateria) {
  return f.componentes?.length
    ? f.componentes.map(c => ({ componente: c, latex: balanceActual(f, indiceComponente(c)) }))
    : [{ componente: null, latex: balanceActual(f) }];
}

export function relacionesMezcla(f: FormulacionMateria): string[] {
  if (!f.componentes?.length) return [];
  const indices = f.componentes.map(indiceComponente);
  const suma = (base: string) => indices.map(i => variableComponente(base, i)).join('+');
  const r = [String.raw`m=${suma('m')}`, String.raw`\rho=${suma(String.raw`\rho`)}`];
  r.push(...indices.map(i => String.raw`${variableComponente('w', i)}=\frac{${variableComponente(String.raw`\rho`, i)}}{\rho},\quad\rho>0`));
  r.push(String.raw`${suma('w')}=1`);
  // The transport convention uses the mass-averaged velocity of the mixture.
  if (!f.campo.sinDifusion) r.push(String.raw`${suma(String.raw`\mathbf j`)}=\mathbf0`);
  const puertos = f.fronteras.length ? f.fronteras.map(p => String(p.id)) : ['p'];
  r.push(...puertos.map(p => String.raw`\dot m_{${p}}=${indices.map(i => String.raw`\dot m_{${i},${p}}`).join('+')}`));
  return r;
}

export function relacionesFormulacion(f: FormulacionMateria) {
  const indices = f.componentes?.length ? f.componentes.map(indiceComponente) : ['i'];
  return [...new Set([...indices.flatMap(i => relacionesMateria(f, i)), ...relacionesMezcla(f)])];
}
