export type Familia = 'entrada' | 'salida' | 'generacion' | 'consumo';
export type Naturaleza = 'constante' | 'convectiva' | 'difusiva' | 'reaccion' | 'compartida';
export type Volumen = { id: number; nombre: string };
export type Aportacion = { id: number; volumen: number; familia: Familia; naturaleza: Naturaleza };
export type Conexion = { id: number; desde: number; hacia: number };
export type ModeloModular = { volumenes: Volumen[]; aportaciones: Aportacion[]; conexiones: Conexion[] };
export type Simplificaciones = { sinReaccion: boolean; sinDifusion: boolean; sinAcumulacion: boolean };
export type TerminoModular = { clave: string; simbolo: string; familia: Familia; naturaleza: Naturaleza; conexion?: Conexion; aportacion?: Aportacion };

export const SIMPLIFICACIONES_INICIALES: Simplificaciones = { sinReaccion: false, sinDifusion: false, sinAcumulacion: false };
export const FAMILIAS: { id: Familia; nombre: string; signo: string }[] = [
  { id: 'entrada', nombre: 'Entrada', signo: '+' },
  { id: 'salida', nombre: 'Salida', signo: '−' },
  { id: 'generacion', nombre: 'Generación', signo: '+' },
  { id: 'consumo', nombre: 'Consumo', signo: '−' },
];

export function simboloAportacion(a: Aportacion) {
  if (a.familia === 'generacion') return `g_{i,${a.id}}`;
  if (a.familia === 'consumo') return `c_{i,${a.id}}`;
  const tipo = { constante: 'cte', convectiva: 'conv', difusiva: 'dif', reaccion: 'rxn', compartida: 'int' }[a.naturaleza];
  return String.raw`\dot m^{\mathrm{${tipo}}}_{i,${a.id}}`;
}

export function definicionAportacion(a: Aportacion) {
  const simbolo = simboloAportacion(a);
  if (a.naturaleza === 'constante') return `${simbolo}(t)=${simbolo}(0)`;
  if (a.naturaleza === 'reaccion') {
    const tasa = a.familia === 'generacion' ? '\\gamma' : '\\chi';
    return `${simbolo}=\\int_{V(t)}${tasa}_{i,${a.id}}\\,dV,\\quad ${tasa}_{i,${a.id}}\\geq0`;
  }
  const flujo = a.naturaleza === 'difusiva' ? String.raw`\mathbf j_i` : String.raw`\rho_i(\mathbf v-\mathbf v_b)`;
  const signo = a.familia === 'entrada' ? '-' : '';
  return `${simbolo}=\\int_{A_{${a.id}}}\\left[${signo}${flujo}\\!\\cdot\\mathbf n\\right]_+\\,dA`;
}

/** One oriented connection, referenced by both balances; never two independent flows. */
export function terminosVolumen(m: ModeloModular, id: number): TerminoModular[] {
  return [
    ...m.aportaciones.filter(a => a.volumen === id).map(a => ({ ...a, aportacion: a, clave: `a${a.id}`, simbolo: simboloAportacion(a) })),
    ...m.conexiones.filter(c => c.desde === id || c.hacia === id).map(c => ({
      clave: `c${c.id}`, simbolo: `\\phi_{i,${c.id}}`, familia: (c.desde === id ? 'salida' : 'entrada') as Familia,
      naturaleza: 'compartida' as const, conexion: c,
    })),
  ];
}

export function terminoActivo(t: TerminoModular, s: Simplificaciones) {
  return !(s.sinDifusion && t.naturaleza === 'difusiva')
    && !(s.sinReaccion && ['generacion', 'consumo'].includes(t.familia));
}

function familiaLatex(terminos: TerminoModular[], familia: Familia, id: number, s: Simplificaciones) {
  if (s.sinReaccion && ['generacion', 'consumo'].includes(familia)) return null;
  const declarados = terminos.filter(t => t.familia === familia);
  const activos = declarados.filter(t => terminoActivo(t, s));
  if (!declarados.length) return `${{ entrada: 'E', salida: 'S', generacion: 'G', consumo: 'C' }[familia]}_{i,${id}}`;
  if (!activos.length) return null;
  const suma = activos.map(t => t.simbolo).join('+');
  return activos.length > 1 ? String.raw`\left(${suma}\right)` : suma;
}

export function balanceVolumen(m: ModeloModular, id: number, s: Simplificaciones) {
  const terminos = terminosVolumen(m, id);
  const rhs = FAMILIAS.flatMap(f => {
    const valor = familiaLatex(terminos, f.id, id, s);
    return valor ? [{ signo: f.signo === '−' ? '-' : '+', valor }] : [];
  }).map((t, i) => (i === 0 && t.signo === '+' ? '' : t.signo) + t.valor).join('') || '0';
  const lhs = s.sinAcumulacion ? '0' : String.raw`\frac{dm_{i,${id}}}{dt}`;
  return lhs + '=' + rhs;
}

/** Coefficients are summed by identity, independently of their displayed LaTeX. */
export function coeficientesGlobales(m: ModeloModular, s: Simplificaciones) {
  const resultado = new Map<string, number>();
  for (const v of m.volumenes) for (const t of terminosVolumen(m, v.id)) {
    if (!terminoActivo(t, s)) continue;
    const signo = ['entrada', 'generacion'].includes(t.familia) ? 1 : -1;
    resultado.set(t.clave, (resultado.get(t.clave) ?? 0) + signo);
  }
  return resultado;
}
