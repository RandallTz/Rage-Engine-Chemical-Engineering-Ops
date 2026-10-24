/** Presentation-only compatibility for labels stored by earlier Spanish documents.
 * Protocol keys, equations, identifiers and user-authored names are never rewritten.
 */
const labels: Record<string, string> = {
  'cierre PH del paquete: energía de todas las fases': 'Package PH closure: energy of every phase',
  'cierre PH del paquete: volumen de todas las fases': 'Package PH closure: volume of every phase',
  'cierre UV del paquete: energía de todas las fases': 'Package UV closure: energy of every phase',
  'cierre UV del paquete: volumen de todas las fases': 'Package UV closure: volume of every phase',
  'reparto de equilibrio entre todas las fases candidatas, con prueba de estabilidad; una fase ausente tiene cantidad cero': 'Equilibrium partition over all candidate phases, with stability search; an absent phase has zero amount',
  'trabajo de frontera P dV/dt (comprobación)': 'Boundary work P dV/dt (verification)',
  'continuidad de presión declarada': 'Declared pressure continuity',
  'composición del donante según el signo del caudal': 'Donor composition follows the flow direction',
  'entalpía del donante según el signo del caudal': 'Donor enthalpy follows the flow direction',
  'caudal en base molar': 'Molar flow rate',
  'conservación por componente': 'Conservation of each component',
  'primera ley': 'First law',
  'conservación global del componente': 'Global component conservation',
  'conservación global de energía': 'Global energy conservation',
  'Conservación local': 'Local conservation', 'Dominio': 'Domain', 'Fronteras': 'Boundaries',
  'Masa inicial': 'Initial mass', 'Densidad inicial': 'Initial density', 'Volumen inicial': 'Initial volume',
  'Inicio del dominio': 'Domain start', 'Final del dominio': 'Domain end', 'Volumen del dominio': 'Domain volume',
  'Concentración media del componente': 'Mean component concentration', 'Flujo por la frontera restante': 'Flow through the remaining boundary',
  'Generación': 'Generation', 'Consumo': 'Consumption', 'Generación local': 'Local generation', 'Consumo local': 'Local consumption',
  'Flujo difusivo': 'Diffusive flux', 'Difusividad': 'Diffusivity', 'Dato inicial': 'Initial condition', 'Dato': 'Datum',
  'Geometría': 'Geometry', 'Parámetro': 'Parameter', 'Dato de frontera': 'Boundary datum',
  'Materia': 'Matter', 'Energía': 'Energy', 'Momento': 'Momentum', 'Termodinámica': 'Thermodynamics',
  'Balance fundamental': 'Fundamental balance', 'Diferencial': 'Differential', 'Integral': 'Integral', 'Total': 'Total',
  'masa': 'mass', 'densidad': 'density', 'volumen': 'volume', 'tiempo': 'time',
  'Energía interna': 'Internal energy', 'Temperatura': 'Temperature', 'Presión': 'Pressure',
  'Calor': 'Heat', 'Trabajo': 'Work', 'Componentes': 'Components', 'Corrientes': 'Streams',
  'Por balance': 'From balance', 'Por relación': 'From relation', 'Por cierre': 'From closure', 'Pendiente': 'Missing',
  'Sin modelo': 'No model', 'Composición': 'Composition', 'Conservación': 'Conservation',
  'La ecuación no tiene acumulación temporal. La resolución algebraica queda pendiente.': 'The equation has no time accumulation. Algebraic solution is not yet supported.',
  'Añade al menos un componente a la hoja.': 'Add at least one component in Model.',
  'La forma integral necesita una reducción total o una discretización espacial declarada.': 'The integral form requires a total reduction or a declared spatial discretization.',
  'La primera discretización 1D admite coordenadas cartesianas.': 'The current 1D discretization supports Cartesian coordinates.',
  'Deja una dirección espacial activa y declara invariancia en las otras dos.': 'Keep one active spatial direction and declare invariance in the other two.',
  'Declara una frontera fija para esta malla 1D.': 'Declare a fixed boundary for this 1D mesh.',
  'Concentración': 'Concentration', 'Volumen de control': 'Control volume',
};
const phrases: [RegExp, string][] = [
  [/^Velocidad en /, 'Velocity along '], [/^Entrada /, 'Inlet '], [/^Salida /, 'Outlet '],
  [/^Extremo izquierdo/, 'Left boundary'], [/^Extremo derecho/, 'Right boundary'],
  [/^Expresar en forma /, 'Express in '], [/^Coordenadas: /, 'Coordinates: '],
  [/^Añadir componente: /, 'Add component: '], [/^Renombrar componente /, 'Rename component '], [/^Retirar componente: /, 'Remove component: '],
  [/^Eliminar /, 'Remove '], [/^Restaurar /, 'Restore '], [/^Declarar /, 'Declare '], [/^Aplicar: /, 'Apply: '], [/^Retirar: /, 'Remove: '],
  [/convección/g, 'convection'], [/difusión/g, 'diffusion'], [/generación/g, 'generation'], [/consumo/g, 'consumption'],
  [/sin variación/gi, 'no variation'], [/variación/g, 'variation'], [/uniforme en el espacio/g, 'spatially uniform'], [/variable en el espacio/g, 'spatially variable'],
  [/^Fijar el dominio$/, 'Fix the domain'], [/^Permitir dominio móvil$/, 'Allow a moving domain'],
  [/^Anular acumulación local$/, 'Remove local accumulation'], [/^Anular acumulación total$/, 'Remove total accumulation'],
  [/^Frontera fija$/, 'Fixed boundary'], [/^Resto de la frontera sin flujo$/, 'No flow through the remaining boundary'],
  [/^Balance de /, 'Balance for '], [/^Evolución de la masa$/, 'Mass over time'], [/^Evolución de la densidad$/, 'Density over time'],
  [/^Evolución del volumen$/, 'Volume over time'], [/^Temperatura del volumen$/, 'Volume temperature'],
];
export function englishLabel(value: string): string {
  if (labels[value]) return labels[value];
  return phrases.reduce((text, [pattern, translation]) => text.replace(pattern, translation), value);
}
