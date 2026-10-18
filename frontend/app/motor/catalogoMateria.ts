import { COORDENADAS, variableComponente } from './operadores';
import { campoEfectivo, indiceComponente } from './recorridoMateria';
import type { FormulacionMateria } from './recorridoMateria';

export type VariableMateria = { simbolo: string; nombre: string; unidad: string };
export type GrupoVariablesMateria = { nombre: string; variables: VariableMateria[] };
export function variablesMateria(f: FormulacionMateria): { volumen: GrupoVariablesMateria[]; corrientes: GrupoVariablesMateria[]; notacion: VariableMateria[] } {
  const componentes = f.componentes?.length ? f.componentes.map(c => ({ indice: indiceComponente(c), nombre: `${c.nombre} · ${c.simbolo}` })) : [{ indice: 'i', nombre: 'Componente i' }];
  const volumen: GrupoVariablesMateria[] = [{ nombre: 'Compartidas por la mezcla', variables: [
    { simbolo: 'V(t)', nombre: 'Volumen del dominio · compartido', unidad: 'm³' },
    { simbolo: 'm(t)', nombre: 'Masa total de la mezcla', unidad: 'kg' },
    { simbolo: String.raw`\rho(\mathbf x,t)`, nombre: 'Densidad de la mezcla', unidad: 'kg/m³' },
    { simbolo: String.raw`\mathbf v(\mathbf x,t)`, nombre: 'Velocidad media en masa', unidad: 'm/s' },
    { simbolo: String.raw`\mathbf v_b`, nombre: 'Velocidad de la frontera', unidad: 'm/s' },
  ] }, ...componentes.map(c => {
    const v = (base: string) => variableComponente(base, c.indice);
    return { nombre: c.nombre, variables: [
      { simbolo: `${v('m')}(t)`, nombre: 'Masa contenida', unidad: 'kg' },
      { simbolo: String.raw`${v(String.raw`\rho`)}(\mathbf x,t)`, nombre: 'Masa del componente / volumen de mezcla', unidad: 'kg/m³' },
      { simbolo: `${v(String.raw`\bar\rho`)}(t)`, nombre: 'Concentración másica media', unidad: 'kg/m³' },
      { simbolo: String.raw`${v('w')}(\mathbf x,t)`, nombre: 'Fracción másica local', unidad: '1' },
      { simbolo: String.raw`${v(String.raw`\gamma`)}(\mathbf x,t)`, nombre: 'Generación local', unidad: 'kg/(m³·s)' },
      { simbolo: String.raw`${v(String.raw`\chi`)}(\mathbf x,t)`, nombre: 'Consumo local', unidad: 'kg/(m³·s)' },
      { simbolo: `${v('G')}(t)`, nombre: 'Generación total', unidad: 'kg/s' },
      { simbolo: `${v('C')}(t)`, nombre: 'Consumo total', unidad: 'kg/s' },
      { simbolo: String.raw`${v(String.raw`\mathbf j`)}(\mathbf x,t)`, nombre: campoEfectivo(f).sinDifusion ? 'Flujo difusivo · cero' : 'Flujo difusivo interno', unidad: 'kg/(m²·s)' },
      ...(!campoEfectivo(f).sinDifusion && f.campo.difusion !== 'flujo' ? [{ simbolo: v('D'), nombre: 'Difusividad escalar', unidad: 'm²/s' }] : []),
    ] };
  })];
  const puertos = f.fronteras.map(p => ({ id: String(p.id), nombre: `${p.sentido === 'entrada' ? 'Entrada' : 'Salida'} ${p.id}` }));
  const corrientes: GrupoVariablesMateria[] = puertos.map(p => ({ nombre: p.nombre, variables: [
    { simbolo: String.raw`\dot m_{${p.id}}(t)`, nombre: 'Caudal másico de la mezcla', unidad: 'kg/s' },
    { simbolo: `Q_{${p.id}}(t)`, nombre: 'Caudal volumétrico · compartido', unidad: 'm³/s' },
    { simbolo: String.raw`\rho_{${p.id}}`, nombre: 'Densidad de la corriente', unidad: 'kg/m³' },
    { simbolo: `A_{${p.id}}`, nombre: 'Área del puerto', unidad: 'm²' },
    ...componentes.flatMap(c => [
      { simbolo: String.raw`\dot m_{${c.indice},${p.id}}(t)`, nombre: `Caudal másico · ${c.nombre}`, unidad: 'kg/s' },
      { simbolo: String.raw`\rho_{${c.indice},${p.id}}`, nombre: `Concentración másica · ${c.nombre}`, unidad: 'kg/m³' },
      { simbolo: `w_{${c.indice},${p.id}}`, nombre: `Fracción másica en la corriente · ${c.nombre}`, unidad: '1' },
    ]),
  ] }));
  corrientes.push({ nombre: f.fronteras.length ? 'Fuera de los puertos declarados' : 'Toda la frontera · sin puertos declarados', variables: componentes.map(c => ({ simbolo: String.raw`\Phi_{${c.indice},\mathrm{resto}}`, nombre: `Intercambio por otras superficies · ${c.nombre}`, unidad: 'kg/s' })) });
  return { volumen, corrientes, notacion: [
    { simbolo: String.raw`\mathbf n`, nombre: 'Normal exterior a la frontera', unidad: '1' },
    { simbolo: String.raw`\varepsilon_p`, nombre: 'Signo del puerto: −1 entrada, +1 salida', unidad: '1' },
    { simbolo: String.raw`\mathcal E,\;\mathcal S`, nombre: 'Conjuntos de puertos de entrada y salida', unidad: '1' },
    { simbolo: String.raw`S_{\mathrm{resto}}`, nombre: 'Parte de la frontera fuera de los puertos', unidad: 'm²' },
    { simbolo: 't', nombre: 'Tiempo', unidad: 's' },
    { simbolo: String.raw`i,\;p`, nombre: 'Índices de componente y puerto', unidad: '1' },
    { simbolo: String.raw`\mathbf x`, nombre: 'Posición en el dominio', unidad: 'm' },
    ...COORDENADAS[f.coordenadas].ejes.map(eje => ({ simbolo: eje, nombre: eje === 'r' ? 'Radio' : eje.endsWith('theta') ? 'Ángulo polar' : eje.endsWith('varphi') ? 'Ángulo azimutal' : `Coordenada ${eje}`, unidad: eje.startsWith('\\') ? 'rad' : 'm' })),
    { simbolo: String.raw`\mathbf e_a`, nombre: 'Vector unitario de la base local', unidad: '1' },
    { simbolo: 'f', nombre: 'Campo independiente o componente físico del vector', unidad: 'Según la variable' },
    { simbolo: String.raw`\nabla,\;\nabla\!\cdot,\;\nabla^2`, nombre: 'Gradiente, divergencia y laplaciano', unidad: '1/m · 1/m · 1/m²' },
  ] };
}
