import type {EspecificacionEstado,PoliticaEstado} from './contratoTermodinamica';
export type RelacionTermodinamica={id:string;titulo:string;latex:string};
/** Fundamental relations apply to the closure of a volume as well as a point query.
 * They are a framework, not additional independent equations or evidence of a
 * supported package. The backend publishes its actual assembled residuals.
 * Macroscopic simple-compressible equilibrium, common reference states, no
 * capillarity/external fields. Chemical-potential equality concerns species
 * exchanged between present phases; absent phases require stability inequalities.
 * No global G minimization is claimed for PH/UP specifications. */
export function fundamentosEquilibrio(tipo:EspecificacionEstado['tipo'],p:PoliticaEstado):RelacionTermodinamica[]{
  const r=[{id:'fundamental',titulo:'Relación fundamental',latex:String.raw`dU=T\,dS-P\,dV+\sum_i\mu_i\,dn_i`},
    {id:'estado',titulo:'Energía y volumen',latex:String.raw`U=\sum_\alpha m^\alpha u^\alpha,\quad V=\sum_\alpha m^\alpha v^\alpha,\quad H=U+PV`},
    {id:'materia',titulo:'Reparto de componentes',latex:String.raw`n_i=\sum_\alpha n^\alpha x_i^\alpha,\quad z_i=\sum_\alpha\beta_\alpha x_i^\alpha`},
    {id:'bases',titulo:'Fracciones de fase',latex:String.raw`\beta_\alpha=\frac{n^\alpha}{n},\quad\chi_\alpha=\frac{m^\alpha}{m},\quad\varepsilon_\alpha=\frac{V^\alpha}{V}`},
    {id:'normalizacion',titulo:'Normalización y cambio de base',latex:String.raw`\sum_\alpha\beta_\alpha=1,\quad\sum_i x_i^\alpha=1,\quad m_i=M_i n_i`},
    {id:'equilibrio',titulo:'Equilibrio entre fases presentes',latex:String.raw`T^\alpha=T^\beta,\quad P^\alpha=P^\beta,\quad \mu_i^\alpha=\mu_i^\beta`},
    {id:'potenciales',titulo:'Potenciales termodinámicos',latex:String.raw`G=H-TS,\quad A=U-TS`},
    {id:'potencial-quimico',titulo:'Potencial químico',latex:String.raw`\mu_i=\left(\frac{\partial G}{\partial n_i}\right)_{T,P,n_{j\ne i}}`},
    {id:'fugacidad',titulo:'Fugacidad entre fases',latex:String.raw`\mu_i^\alpha=\mu_i^\circ(T)+RT\ln\!\left(\frac{f_i^\alpha}{f^\circ}\right),\quad f_i^\alpha=f_i^\beta`}];
  r.push(tipo==='TP'?{id:'estabilidad',titulo:'Estabilidad · T, P y cantidades dados',latex:String.raw`\min_{\{n_i^\alpha\geq0\}}\sum_\alpha G^\alpha,\quad\sum_\alpha n_i^\alpha=n_i`}:tipo==='UV'?{id:'estabilidad',titulo:'Estabilidad · U, V y cantidades dados',latex:String.raw`\max\sum_\alpha S^\alpha,\quad\sum_\alpha U^\alpha=U,\quad\sum_\alpha V^\alpha=V,\quad\sum_\alpha n_i^\alpha=n_i`}:tipo==='UP'?{id:'restricciones',titulo:'Reconstrucción de U a presión dada',latex:String.raw`U_{\mathrm{dato}}=\sum_\alpha m^\alpha u^\alpha(T,P,\mathbf x^\alpha)`}:{id:'restricciones',titulo:'Reconstrucción de h a presión dada',latex:String.raw`h_{\mathrm{dato}}=\sum_\alpha\chi_\alpha h^\alpha(T,P,\mathbf x^\alpha)`});
  if(tipo==='PH'||tipo==='UP')r.push({id:'estabilidad-reconstruida',titulo:'Estabilidad a T y P reconstruidos',latex:String.raw`G_{\mathrm{eq}}(T,P,\mathbf n)\leq G_{\mathrm{alternativa}}(T,P,\mathbf n)`});
  if(p.cantidad==='monofasico')r.push({id:'monofasico',titulo:'Restricción solicitada',latex:String.raw`N_{\mathrm{fases}}=1`});
  return r;
}
export function relacionesTermodinamicas(e:EspecificacionEstado,p:PoliticaEstado){return fundamentosEquilibrio(e.tipo,p);}
