export type SupuestosMateria = {
  sinReaccion: boolean;
  sinDifusion: boolean;
  fronteraFija: boolean;
  estacionario: boolean;
};

export const SIN_SUPUESTOS: SupuestosMateria = {
  sinReaccion: false,
  sinDifusion: false,
  fronteraFija: false,
  estacionario: false,
};

/** Conservación por especie, base másica y velocidad media másica.
 * El estacionario local no anula la acumulación de un dominio móvil:
 * Reynolds conserva entonces el transporte debido a su frontera.
 * Estas expresiones son simbólicas; no describen el ensamblaje del backend.
 */
export function ecuacionesMateria(s: SupuestosMateria) {
  const localIzquierda = s.estacionario ? '0' : String.raw`\frac{\partial\rho_i}{\partial t}`;
  const local = localIzquierda + String.raw`=-\nabla\!\cdot(\rho_i\mathbf v)`
    + (s.sinDifusion ? '' : String.raw`-\nabla\!\cdot\mathbf j_i`)
    + (s.sinReaccion ? '' : '+r_i');

  const integralIzquierda = !s.estacionario
    ? String.raw`\frac{d}{dt}\int_{V(t)}\rho_i\,dV`
    : s.fronteraFija ? '0'
    : String.raw`\oint_{\partial V(t)}\rho_i\mathbf v_b\!\cdot\mathbf n\,dA`;
  const velocidad = s.fronteraFija ? String.raw`\mathbf v` : String.raw`(\mathbf v-\mathbf v_b)`;
  const secundarios = (s.sinDifusion ? '' : String.raw`-\oint_{\partial V(t)}\mathbf j_i\!\cdot\mathbf n\,dA`)
    + (s.sinReaccion ? '' : String.raw`+\int_{V(t)}r_i\,dV`);
  const integral = String.raw`\begin{aligned}` + integralIzquierda
    + String.raw`&=-\oint_{\partial V(t)}\rho_i` + velocidad + String.raw`\!\cdot\mathbf n\,dA`
    + (secundarios ? String.raw`\\&\quad` + secundarios : '') + String.raw`\end{aligned}`;
  return { local, integral };
}

export const OPCIONES_MATERIA: { id: keyof SupuestosMateria; nombre: string; condicion: string }[] = [
  { id: 'sinReaccion', nombre: 'Sin reacción', condicion: 'r_i=0' },
  { id: 'sinDifusion', nombre: 'Sin difusión', condicion: String.raw`\mathbf j_i=\mathbf 0` },
  { id: 'fronteraFija', nombre: 'Frontera fija', condicion: String.raw`\mathbf v_b=\mathbf 0` },
  { id: 'estacionario', nombre: 'Estado estacionario', condicion: String.raw`\partial\rho_i/\partial t=0` },
];

export const SIMBOLOS_MATERIA = [
  { simbolo: String.raw`\rho_i`, nombre: 'Densidad de la especie i', unidad: 'kg/m³' },
  { simbolo: String.raw`\mathbf v`, nombre: 'Velocidad media másica', unidad: 'm/s' },
  { simbolo: String.raw`\mathbf j_i`, nombre: 'Flujo difusivo de la especie i', unidad: 'kg/(m²·s)' },
  { simbolo: 'r_i', nombre: 'Generación − consumo por reacción', unidad: 'kg/(m³·s)' },
  { simbolo: 't', nombre: 'Tiempo', unidad: 's' },
  { simbolo: 'V(t)', nombre: 'Volumen de control', unidad: 'm³' },
  { simbolo: String.raw`\partial V(t)`, nombre: 'Superficie del volumen de control', unidad: '—' },
  { simbolo: String.raw`\mathbf v_b`, nombre: 'Velocidad de la frontera', unidad: 'm/s' },
  { simbolo: String.raw`\mathbf n`, nombre: 'Normal unitaria hacia el exterior', unidad: '1' },
  { simbolo: 'dV', nombre: 'Elemento de volumen', unidad: 'm³' },
  { simbolo: 'dA', nombre: 'Elemento de área', unidad: 'm²' },
  { simbolo: String.raw`\nabla\!\cdot`, nombre: 'Divergencia', unidad: '1/m' },
];
