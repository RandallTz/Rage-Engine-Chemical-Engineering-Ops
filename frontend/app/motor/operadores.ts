export type Coordenadas = 'cartesianas' | 'cilindricas' | 'esfericas';
export type LeyDifusion = 'flujo' | 'fick' | 'laplaciano';
export type OpcionesCampo = { sinReaccion: boolean; sinGeneracion?: boolean; sinConsumo?: boolean; generacionUniforme?: boolean; consumoUniforme?: boolean; sinDifusion: boolean; sinConveccion: boolean; estacionario: boolean; difusion: LeyDifusion };
export const CAMPO_GENERAL: OpcionesCampo = { sinReaccion: false, sinDifusion: false, sinConveccion: false, estacionario: false, difusion: 'flujo' };
export function fuentesActivas(o: OpcionesCampo) {
  return { generacion: !(o.sinReaccion || o.sinGeneracion), consumo: !(o.sinReaccion || o.sinConsumo) };
}
export function variableComponente(base: string, indice = 'i') { return indice === 'i' ? `${base}_i` : `${base}_{${indice}}`; }
type Factor = { r: number; seno: number };
const uno: Factor = { r: 0, seno: 0 };
export const COORDENADAS: Record<Coordenadas, { nombre: string; variables: string; ejes: string[]; escalas: Factor[] }> = {
  cartesianas: { nombre: 'Cartesianas', variables: 'x, y, z', ejes: ['x', 'y', 'z'], escalas: [uno, uno, uno] },
  cilindricas: { nombre: 'Polares / cilíndricas', variables: 'r, φ, z', ejes: ['r', String.raw`\varphi`, 'z'], escalas: [uno, { r: 1, seno: 0 }, uno] },
  esfericas: { nombre: 'Esféricas', variables: 'r, θ, φ', ejes: ['r', String.raw`\theta`, String.raw`\varphi`], escalas: [uno, { r: 1, seno: 0 }, { r: 1, seno: 1 }] },
};
const multiplicar = (a: Factor, b: Factor): Factor => ({ r: a.r + b.r, seno: a.seno + b.seno });
const dividir = (a: Factor, b: Factor): Factor => ({ r: a.r - b.r, seno: a.seno - b.seno });
function factoresLatex(f: Factor) {
  const producto = (r: number, seno: number) => [r ? (r === 1 ? 'r' : `r^{${r}}`) : '', seno ? (seno === 1 ? String.raw`\sin\theta` : String.raw`\sin^{${seno}}\theta`) : ''].filter(Boolean).join(String.raw`\,`) || '1';
  const num = producto(Math.max(0, f.r), Math.max(0, f.seno));
  return f.r < 0 || f.seno < 0 ? String.raw`\frac{${num}}{${producto(Math.max(0, -f.r), Math.max(0, -f.seno))}}` : num;
}
function coeficiente(f: Factor) { return f.r || f.seno ? `{${factoresLatex(f)}}` : ''; }
function separar(f: Factor, eje: string) {
  const interior = { r: eje === 'r' ? f.r : 0, seno: eje === String.raw`\theta` ? f.seno : 0 };
  return { interior, exterior: dividir(f, interior) };
}
export function terminosMetricos(sistema: Coordenadas, potencia: 1 | 2) {
  const c = COORDENADAS[sistema];
  const H = c.escalas.reduce(multiplicar, uno);
  return c.ejes.map((eje, a) => {
    const h = potencia === 1 ? c.escalas[a] : multiplicar(c.escalas[a], c.escalas[a]);
    const partes = separar(dividir(H, h), eje);
    return { eje, a, interior: partes.interior, exterior: dividir(partes.exterior, H) };
  });
}
const derivada = (campo: string, eje: string) => String.raw`\frac{\partial ${campo}}{\partial ${eje}}`;

/** Orthogonal-coordinate operators generated from metric scale factors h_a.
 * Scalars are physical fields; vector inputs are physical unit-basis components.
 */
export function expandirDivergencia(sistema: Coordenadas, componente: (eje: string) => string, invariantes: boolean[] = []) {
  return terminosMetricos(sistema, 1).flatMap(t => {
    if (invariantes[t.a]) {
      // Differentiate the metric, not the invariant physical component.
      // Constant radial components still have divergence in curved coordinates.
      const potencia = t.eje === 'r' ? t.interior.r : t.eje === String.raw`\theta` ? t.interior.seno : 0;
      if (!potencia) return [];
      const f = multiplicar(t.exterior, t.interior);
      if (t.eje === 'r') f.r--;
      else f.seno--;
      return [(potencia === 1 ? '' : `${potencia}`) + coeficiente(f) + (t.eje === String.raw`\theta` ? String.raw`\cos\theta\,` : '') + componente(t.eje)];
    }
    const dentro = coeficiente(t.interior) + componente(t.eje);
    return coeficiente(t.exterior) + derivada(String.raw`\left(${dentro}\right)`, t.eje);
  });
}
export function expandirDifusion(sistema: Coordenadas, campo: string, peso?: string, invariantes: boolean[] = []) {
  return terminosMetricos(sistema, 2).filter(t => !invariantes[t.a]).map(t => {
    const fuera = coeficiente(t.exterior);
    if (!peso && !t.interior.r && !t.interior.seno) return fuera + String.raw`\frac{\partial^2 ${campo}}{\partial ${t.eje}^2}`;
    return fuera + derivada(String.raw`\left(${coeficiente(t.interior)}${peso ?? ''}${derivada(campo, t.eje)}\right)`, t.eje);
  });
}
export function expandirGradiente(sistema: Coordenadas, campo: string, invariantes: boolean[] = []) {
  const c = COORDENADAS[sistema];
  return c.ejes.flatMap((eje, a) => invariantes[a] ? [] : [coeficiente(dividir(uno, c.escalas[a])) + derivada(campo, eje) + String.raw`\mathbf e_{${eje}}`]);
}
export function sumaExpandida(izquierda: string, terminos: string[]) {
  return `${izquierda}=${terminos.join('+') || '0'}`;
}
export function ecuacionCampoReducida(o: OpcionesCampo, sistema: Coordenadas, invariantes: boolean[], expandir = false, indice = 'i') {
  const rho = variableComponente(String.raw`\rho`, indice), D = variableComponente('D', indice), w = variableComponente('w', indice);
  const gamma = variableComponente(String.raw`\gamma`, indice), chi = variableComponente(String.raw`\chi`, indice);
  if (!expandir && !invariantes.some(Boolean)) return ecuacionCampo(o, indice);
  const terminos: { signo: string; texto: string }[] = [];
  if (!o.sinConveccion) terminos.push(...expandirDivergencia(sistema, e => String.raw`${rho} v_{${e}}`, invariantes).map(texto => ({ signo: '-', texto })));
  if (!o.sinDifusion) {
    const dif = o.difusion === 'flujo' ? expandirDivergencia(sistema, e => String.raw`j_{${indice},${e}}`, invariantes)
      : expandirDifusion(sistema, o.difusion === 'fick' ? w : rho, o.difusion === 'fick' ? String.raw`\rho ${D}` : undefined, invariantes);
    terminos.push(...dif.map(t => ({ signo: o.difusion === 'flujo' ? '-' : '+', texto: (o.difusion === 'laplaciano' ? D : '') + t })));
  }
  const fuentes = fuentesActivas(o);
  if (fuentes.generacion) terminos.push({ signo: '+', texto: o.generacionUniforme ? `${gamma}(t)` : String.raw`${gamma}(\mathbf x,t)` });
  if (fuentes.consumo) terminos.push({ signo: '-', texto: o.consumoUniforme ? `${chi}(t)` : String.raw`${chi}(\mathbf x,t)` });
  const lhs = o.estacionario ? '0' : String.raw`\frac{\partial${rho}}{\partial t}`;
  const rhs = terminos.map((t, i) => (i === 0 && t.signo === '+' ? '' : t.signo) + t.texto).join('') || '0';
  return `${lhs}=${rhs}`;
}
export function estacionarioLocalDeducido(o: OpcionesCampo, sistema: Coordenadas, invariantes: boolean[]) {
  const fuentes = fuentesActivas(o);
  if (fuentes.generacion || fuentes.consumo) return false;
  const conv = o.sinConveccion ? [] : expandirDivergencia(sistema, e => String.raw`\rho_i v_{${e}}`, invariantes);
  const dif = o.sinDifusion ? [] : o.difusion === 'flujo' ? expandirDivergencia(sistema, e => String.raw`j_{i,${e}}`, invariantes)
    : expandirDifusion(sistema, o.difusion === 'fick' ? 'w_i' : String.raw`\rho_i`, o.difusion === 'fick' ? String.raw`\rho D_i` : undefined, invariantes);
  return conv.length === 0 && dif.length === 0;
}
export function ecuacionCampo(o: OpcionesCampo, indice = 'i') {
  const rho = variableComponente(String.raw`\rho`, indice), j = variableComponente(String.raw`\mathbf j`, indice), D = variableComponente('D', indice), w = variableComponente('w', indice);
  const gamma = variableComponente(String.raw`\gamma`, indice), chi = variableComponente(String.raw`\chi`, indice);
  const partes: { signo: string; texto: string }[] = [];
  if (!o.sinConveccion) partes.push({ signo: '-', texto: String.raw`\nabla\!\cdot(${rho}\mathbf v)` });
  if (!o.sinDifusion) partes.push(o.difusion === 'flujo'
    ? { signo: '-', texto: String.raw`\nabla\!\cdot${j}` }
    : { signo: '+', texto: o.difusion === 'fick' ? String.raw`\nabla\!\cdot(\rho ${D}\nabla ${w})` : String.raw`${D}\nabla^2${rho}` });
  const fuentes = fuentesActivas(o);
  if (fuentes.generacion) partes.push({ signo: '+', texto: o.generacionUniforme ? `${gamma}(t)` : String.raw`${gamma}(\mathbf x,t)` });
  if (fuentes.consumo) partes.push({ signo: '-', texto: o.consumoUniforme ? `${chi}(t)` : String.raw`${chi}(\mathbf x,t)` });
  const rhs = partes.map((t, i) => (i === 0 && t.signo === '+' ? '' : t.signo) + t.texto).join('') || '0';
  return (o.estacionario ? '0' : String.raw`\frac{\partial${rho}}{\partial t}`) + '=' + rhs;
}

export type FronteraConstante = { id: number; sentido: 'entrada' | 'salida'; constante?: boolean };
export const simboloFrontera = (f: FronteraConstante, indice = 'i') => f.constante === false ? String.raw`\dot m_{${indice},${f.id}}(t)` : String.raw`\dot m^{\mathrm{cte}}_{${indice},${f.id}}`;
export function transporteRelativo(o: OpcionesCampo, fija: boolean, indice = 'i') {
  const rho = variableComponente(String.raw`\rho`, indice), j = variableComponente(String.raw`\mathbf j`, indice), D = variableComponente('D', indice), w = variableComponente('w', indice);
  const t = [...(!o.sinConveccion ? [String.raw`${rho}\mathbf v`] : []), ...(!o.sinDifusion ? [o.difusion === 'flujo' ? j : o.difusion === 'fick' ? String.raw`-\rho ${D}\nabla ${w}` : String.raw`-${D}\nabla${rho}`] : []), ...(!fija ? [String.raw`-${rho}\mathbf v_b`] : [])];
  return t.map((x, i) => i && !x.startsWith('-') ? '+' + x : x).join('') || '\\mathbf 0';
}
export function condicionFrontera(f: FronteraConstante, uniforme: boolean, fija: boolean, o: OpcionesCampo) {
  if (!uniforme) return String.raw`\dot m_{i,${f.id}}(t)=${simboloFrontera(f)}`;
  return String.raw`\left(${transporteRelativo(o, fija)}\right)\!\cdot\mathbf n=${f.sentido === 'entrada' ? '-' : ''}\frac{${simboloFrontera(f)}}{A_{${f.id}}(t)}`;
}
export function netoFronteras(fronteras: FronteraConstante[]) {
  // No declared boundary is NOT an absent flow; preserve unknown aggregates.
  return (['entrada', 'salida'] as const).map((sentido, i) => {
    const grupo = fronteras.filter(f => f.sentido === sentido).map(f => simboloFrontera(f));
    const suma = grupo.length ? (grupo.length > 1 ? String.raw`\left(${grupo.join('+')}\right)` : grupo[0]) : (i ? 'S_i' : 'E_i');
    return (i ? '-' : '') + suma;
  }).join('');
}
export function balanceCantidad(f: FronteraConstante[], sinReaccion: boolean, sinAcumulacion: boolean) {
  return (sinAcumulacion ? '0' : String.raw`\frac{dm_i}{dt}`) + '=' + netoFronteras(f) + (sinReaccion ? '' : '+G_i-C_i');
}
export function solucionCantidad(f: FronteraConstante[], sinReaccion: boolean, sinAcumulacion: boolean) {
  if (!sinReaccion || f.some(x => x.constante === false) || !f.some(x => x.sentido === 'entrada') || !f.some(x => x.sentido === 'salida')) return null;
  return sinAcumulacion ? 'm_i(t)=m_i(0)' : String.raw`m_i(t)=m_i(0)+\left[${netoFronteras(f)}\right]t`;
}

