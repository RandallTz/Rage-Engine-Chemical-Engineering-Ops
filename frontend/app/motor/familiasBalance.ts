export type FamiliaBalance='materia'|'energia'|'momento';
/** Vista de la hoja: un balance o la termodinámica, que no es un balance que se activa:
 * es el cierre de estado de cada volumen y está siempre presente (ARCHITECTURE.md §3). */
export type VistaHoja=FamiliaBalance|'termodinamica';
export const PANEL_TERMODINAMICA={id:'termodinamica' as const,nombre:"Thermodynamics",descripcion:"State, phases and equilibrium in each volume."};
export const FAMILIAS_BALANCE=[
  {id:'materia' as const,nombre:"Matter",descripcion:"Composition, transport and sources."},
  {id:'energia' as const,nombre:"Energy",descripcion:"Heat, work and stored energy."},
  {id:'momento' as const,nombre:"Momentum",descripcion:"Motion, pressure and forces."},
];
export type SupuestosFundamentales={estacionario:boolean;sinConduccion:boolean;sinTrabajoEsfuerzos:boolean;sinEsfuerzosViscosos:boolean;sinFuerzasVolumen:boolean};
export const SIN_SUPUESTOS:SupuestosFundamentales={estacionario:false,sinConduccion:false,sinTrabajoEsfuerzos:false,sinEsfuerzosViscosos:false,sinFuerzasVolumen:false};
/** UI reference only: conservation of total internal + kinetic energy, or
 * momentum, for a continuum without mass sources. No solver or state closure. */
export function ecuacionFundamental(familia:'energia'|'momento',s:SupuestosFundamentales){
  const acumulacion=s.estacionario?'0':familia==='energia'?String.raw`\frac{\partial(\rho e_t)}{\partial t}`:String.raw`\frac{\partial(\rho\mathbf v)}{\partial t}`;
  const transporte=familia==='energia'?String.raw`\nabla\!\cdot(\rho e_t\mathbf v)`:String.raw`\nabla\!\cdot(\rho\mathbf v\otimes\mathbf v)`;
  const terminos: {signo:1|-1;latex:string}[]=familia==='energia'?[
    ...(!s.sinConduccion?[{signo:-1 as const,latex:String.raw`\nabla\!\cdot\mathbf q`}]:[]),
    ...(!s.sinTrabajoEsfuerzos?[{signo:1 as const,latex:String.raw`\nabla\!\cdot(\boldsymbol\sigma\!\cdot\mathbf v)`}]:[]),
    ...(!s.sinFuerzasVolumen?[{signo:1 as const,latex:String.raw`\rho\mathbf b\!\cdot\mathbf v`}]:[]),
    {signo:1,latex:String.raw`r_v`},
  ]:[
    {signo:-1,latex:String.raw`\nabla p`},
    ...(!s.sinEsfuerzosViscosos?[{signo:1 as const,latex:String.raw`\nabla\!\cdot\boldsymbol\tau`}]:[]),
    ...(!s.sinFuerzasVolumen?[{signo:1 as const,latex:String.raw`\rho\mathbf b`}]:[]),
  ];
  return `${s.estacionario?'':`${acumulacion}+`}${transporte}=${terminos.map((t,i)=>`${t.signo===-1?'-':i?'+':''}${t.latex}`).join('')}`;
}
