import type {FormulacionMateria} from './recorridoMateria';
import {campoEfectivo,terminosTotalesMateria} from './recorridoMateria';

export type FormaEnergia='local'|'integrada'|'integral'|'total';
export type ContextoEnergia={volumenId:string;fija:boolean;restoCerrado:boolean;puertos:{id:number;sentido:'entrada'|'salida';constante:boolean}[];componentesIds:number[]};
export type FormulacionEnergia={forma:FormaEnergia;trabajoTotalHeredado:boolean;separarPresion:boolean;entalpia:boolean;sinCinetica:boolean;sinTrabajoViscoso:boolean;sinFuerzasVolumen:boolean;sinFuenteVolumetrica:boolean;sinConduccionLocal:boolean;adiabatico:boolean;estacionario:boolean;sinAcumulacionTotal:boolean;uniforme:boolean;monofasico:boolean;sinCambioFase:boolean;densidadConstante:boolean;presionUniforme:boolean;presionPrescrita?:boolean;modelo:'sin_declarar'|'u_lineal'};
export const ENERGIA_FUNDAMENTAL:FormulacionEnergia={forma:'local',trabajoTotalHeredado:false,separarPresion:false,entalpia:false,sinCinetica:false,sinTrabajoViscoso:false,sinFuerzasVolumen:false,sinFuenteVolumetrica:false,sinConduccionLocal:false,adiabatico:false,estacionario:false,sinAcumulacionTotal:false,uniforme:false,monofasico:false,sinCambioFase:false,densidadConstante:false,presionUniforme:false,presionPrescrita:false,modelo:'sin_declarar'};
/** Only sheets written before this distinction inherit the old imposed-pressure semantics.
 * Spatial uniformity alone never prescribes pressure in a new formulation. */
export const tienePresionPrescrita=(f:FormulacionEnergia,c:ContextoEnergia)=>f.presionPrescrita??(f.presionUniforme&&(!c.fija||c.puertos.length>0));
export type PasoEnergia={titulo:string;formulacion:FormulacionEnergia;contexto:ContextoEnergia;relaciones:string[];operation?:{changes:Partial<FormulacionEnergia>}|null};
export type RecorridoEnergia={version:1;pasos:PasoEnergia[];rehacer:PasoEnergia[]};
export type TerminoEnergia={id:string;rol:'corriente'|'calor'|'presion'|'viscoso'|'fuerzas'|'fuente'|'resto';signo:1|-1;unidad:'W';latex:string;puertoId?:number;sentido?:'entrada'|'salida'};
export function contextoEnergia(f:FormulacionMateria,volumenId='dominio'):ContextoEnergia{
  const transporte=terminosTotalesMateria(f);
  return {volumenId,fija:f.fija,restoCerrado:!transporte.some(t=>t.rol==='resto'),puertos:transporte.filter(t=>t.rol==='entrada'||t.rol==='salida').map(t=>({id:t.puertoId!,sentido:t.rol as 'entrada'|'salida',constante:f.fronteras.find(p=>p.id===t.puertoId)?.constante!==false})),componentesIds:(f.componentes??[]).map(c=>c.id)};
}
export const iniciarEnergia=(contexto:ContextoEnergia):RecorridoEnergia=>({version:1,pasos:[{titulo:'Local energy conservation',formulacion:{...ENERGIA_FUNDAMENTAL},contexto,relaciones:[String.raw`e=u+\frac{\mathbf v\cdot\mathbf v}{2}`,String.raw`\mathbf q:\ \text{nonconvective energy flux}`],operation:null}],rehacer:[]});
export const actualEnergia=(h:RecorridoEnergia)=>h.pasos[h.pasos.length-1];
export function operarEnergia(h:RecorridoEnergia,titulo:string,cambios:Partial<FormulacionEnergia>,relaciones:string[]=[],contexto=actualEnergia(h).contexto):RecorridoEnergia{
  const previa=actualEnergia(h).formulacion,f={...previa,...cambios};
  if(f.entalpia&&!f.separarPresion)throw new Error('Separate pressure stress before collecting flow work into enthalpy.');
  if(JSON.stringify(f)===JSON.stringify(previa)&&JSON.stringify(contexto)===JSON.stringify(actualEnergia(h).contexto))return h;
  return {version:1,pasos:[...h.pasos,{titulo,formulacion:f,contexto:structuredClone(contexto),relaciones,operation:{changes:structuredClone(cambios)}}],rehacer:[]};
}
export function volverEnergia(h:RecorridoEnergia,indice:number):RecorridoEnergia{
  if(!Number.isInteger(indice)||indice<0||indice>=h.pasos.length)return h;
  return {...h,pasos:h.pasos.slice(0,indice+1),rehacer:[...h.pasos.slice(indice+1),...h.rehacer]};
}
export const rehacerEnergia=(h:RecorridoEnergia):RecorridoEnergia=>h.rehacer.length?{...h,pasos:[...h.pasos,h.rehacer[0]],rehacer:h.rehacer.slice(1)}:h;
/** Every macro reduction retains the intervening mathematical identities in the journal. */
export function transformarEnergia(h:RecorridoEnergia,forma:FormaEnergia):RecorridoEnergia{
  const orden:FormaEnergia[]=['local','integrada','integral','total'],actual=orden.indexOf(actualEnergia(h).formulacion.forma),destino=orden.indexOf(forma);
  if(destino<actual)return operarEnergia(h,`Reexpress the balance in ${forma} form`,{forma});
  let r=h;
  for(let i=actual+1;i<=destino;i++){
    if(orden[i]==='integrada')r=operarEnergia(r,'Integrate over V(t) and apply Gauss',{forma:'integrada'},[String.raw`\int_{V(t)}\nabla\cdot\mathbf F\,dV=\oint_{\partial V(t)}\mathbf F\cdot\mathbf n\,dA`]);
    if(orden[i]==='integral')r=operarEnergia(r,'Apply Reynolds transport theorem',{forma:'integral'},[String.raw`\frac{d}{dt}\int_{V(t)}\rho e\,dV=\int_{V(t)}\frac{\partial(\rho e)}{\partial t}\,dV+\oint_{\partial V(t)}\rho e\mathbf v_b\cdot\mathbf n\,dA`,String.raw`E(t)=\int_{V(t)}\rho e\,dV`]);
    if(orden[i]==='total')r=operarEnergia(r,'Partition the boundary into streams and the remaining surface',{forma:'total'},[String.raw`\partial V=\left(\bigcup_p A_p\right)\cup S_{\mathrm{resto}},\quad A_p\cap A_q=\varnothing\ (p\ne q)`,String.raw`\dot m_p=\varepsilon_p\int_{A_p}\rho(\mathbf v-\mathbf v_b)\cdot\mathbf n\,dA,\quad\varepsilon_{\mathrm{ent}}=-1,\ \varepsilon_{\mathrm{sal}}=1`,String.raw`\dot m_p\bar h_p=\varepsilon_p\int_{A_p}\rho h(\mathbf v-\mathbf v_b)\cdot\mathbf n\,dA`]);
  }
  return r;
}
const sumar=(t:{signo:1|-1;latex:string}[])=>t.map((t,i)=>`${t.signo===-1?'-':i?'+':''}${t.latex}`).join('')||'0';
/** This exact term list feeds both LaTeX and the numerical energy evaluator. */
export function terminosEnergia(f:FormulacionEnergia,c:ContextoEnergia):TerminoEnergia[]{
  const t:TerminoEnergia[]=[],add=(id:string,rol:TerminoEnergia['rol'],signo:1|-1,latex:string)=>t.push({id,rol,signo,unidad:'W',latex});
  const transportado=f.entalpia?'h':'u',cin=f.sinCinetica?'':String.raw`+\overline{e_{c,p}}`;
  c.puertos.forEach(p=>t.push({id:`puerto_${p.id}`,rol:'corriente',signo:p.sentido==='entrada'?1:-1,unidad:'W',puertoId:p.id,sentido:p.sentido,latex:String.raw`\dot m_{${p.id}}\left(\bar ${transportado}_{${p.id}}${cin}\right)`}));
  if(!c.restoCerrado)add('resto','resto',-1,String.raw`\Phi_{E,\mathrm{resto}}`);
  if(!f.adiabatico&&!f.sinConduccionLocal)add('calor','calor',1,String.raw`\dot Q`);
  if(f.separarPresion){
    if(!f.entalpia&&!c.restoCerrado)add('presion_resto','resto',-1,String.raw`\Phi_{p,\mathrm{resto}}`);
    if(!f.entalpia)c.puertos.forEach(p=>t.push({id:`presion_flujo_${p.id}`,rol:'presion',signo:p.sentido==='entrada'?1:-1,unidad:'W',puertoId:p.id,latex:String.raw`\dot m_{${p.id}}\overline{(p/\rho)}_{${p.id}}`}));
    if(!c.fija)add('trabajo_frontera','presion',-1,String.raw`\dot W_b`);
    if(!f.sinTrabajoViscoso)add('trabajo_viscoso','viscoso',1,String.raw`\dot W_\tau`);
  }else add('esfuerzos','viscoso',1,String.raw`\dot W_\sigma`);
  if(!f.sinFuerzasVolumen)add('fuerzas','fuerzas',1,String.raw`\dot W_{\mathbf b}`);
  if(!f.sinFuenteVolumetrica)add('fuente','fuente',1,'R');
  return t;
}
export function ecuacionEnergia(f:FormulacionEnergia,c:ContextoEnergia):string{
  const e=f.sinCinetica?'u':'e',cinetica=f.sinCinetica?'':String.raw`+e_c`;
  const energia=f.sinCinetica?'U':'E';
  if(f.forma==='total')return `${f.sinAcumulacionTotal||(f.estacionario&&c.fija)?'0':String.raw`\frac{d${energia}}{dt}`}=${sumar(terminosEnergia(f,c))}`;
  const fuente=f.sinFuenteVolumetrica?'':String.raw`+r_v`;
  if(f.forma==='local'){
    const transporte=f.entalpia?String.raw`\rho(h${cinetica})\mathbf v`:String.raw`\rho ${e}\mathbf v`;
    let rhs=String.raw`-\nabla\cdot(${transporte})`;
    if(!f.sinConduccionLocal)rhs+=String.raw`-\nabla\cdot\mathbf q`;
    if(f.separarPresion){if(!f.entalpia)rhs+=String.raw`-\nabla\cdot(p\mathbf v)`;if(!f.sinTrabajoViscoso)rhs+=String.raw`+\nabla\cdot(\boldsymbol\tau\cdot\mathbf v)`;}
    else rhs+=String.raw`+\nabla\cdot(\boldsymbol\sigma\cdot\mathbf v)`;
    if(!f.sinFuerzasVolumen)rhs+=String.raw`+\rho\mathbf b\cdot\mathbf v`;
    return `${f.estacionario?'0':String.raw`\frac{\partial(\rho ${e})}{\partial t}`}=${rhs}${fuente}`;
  }
  const integrado=f.forma==='integrada',v=c.fija||integrado?String.raw`\mathbf v`:String.raw`\mathbf v-\mathbf v_b`,transporte=f.entalpia?String.raw`\rho(h${cinetica})`:String.raw`\rho ${e}`;
  const lhs=integrado?String.raw`\int_{V(t)}${f.estacionario?'0':String.raw`\frac{\partial(\rho ${e})}{\partial t}`}\,dV`:String.raw`\frac{d${energia}}{dt}`;
  // Local stationarity does not remove moving-control-volume accumulation.
  const izq=!integrado&&f.sinAcumulacionTotal?'0':!integrado&&f.estacionario&&!c.fija?String.raw`\frac{d${energia}}{dt}`:!integrado&&f.estacionario?'0':lhs;
  let rhs=String.raw`-\oint_{\partial V(t)}${transporte}(${v})\cdot\mathbf n\,dA`;
  if(!f.sinConduccionLocal&&!f.adiabatico)rhs+=String.raw`-\oint_{\partial V(t)}\mathbf q\cdot\mathbf n\,dA`;
  if(f.separarPresion){
    if(!f.entalpia)rhs+=String.raw`-\oint_{\partial V(t)}p\mathbf v\cdot\mathbf n\,dA`;
    else if(!c.fija&&!integrado)rhs+=String.raw`-\oint_{\partial V(t)}p\mathbf v_b\cdot\mathbf n\,dA`;
    if(!f.sinTrabajoViscoso)rhs+=String.raw`+\oint_{\partial V(t)}(\boldsymbol\tau\cdot\mathbf v)\cdot\mathbf n\,dA`;
  }else rhs+=String.raw`+\oint_{\partial V(t)}(\boldsymbol\sigma\cdot\mathbf v)\cdot\mathbf n\,dA`;
  if(!f.sinFuerzasVolumen)rhs+=String.raw`+\int_{V(t)}\rho\mathbf b\cdot\mathbf v\,dV`;
  if(!f.sinFuenteVolumetrica)rhs+=String.raw`+\int_{V(t)}r_v\,dV`;
  return `${izq}=${rhs}`;
}
export function relacionesEnergia(f:FormulacionEnergia,c:ContextoEnergia):string[]{
  const r=[String.raw`e=u+e_c,\quad e_c=\frac{\mathbf v\cdot\mathbf v}{2}`];
  if(f.forma!=='local')r.push(String.raw`E=\int_V\rho e\,dV,\quad U=\int_V\rho u\,dV`);
  if(f.separarPresion)r.push(String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`);
  if(f.trabajoTotalHeredado)r.push(String.raw`\nabla\cdot(\boldsymbol\sigma\cdot\mathbf v)=0\quad\text{(restricción heredada pendiente de revisión)}`);
  if(f.entalpia)r.push(String.raw`h=u+\frac{p}{\rho}`);
  if(f.presionUniforme)r.push(String.raw`p(\mathbf x,t)=P(t)`);
  if(tienePresionPrescrita(f,c))r.push(String.raw`P(t)=P_{\mathrm{ext}}(t)`);
  if(f.forma==='total'){
    if(f.separarPresion)r.push(String.raw`\dot W_\tau=\oint_{\partial V}(\boldsymbol\tau\cdot\mathbf v)\cdot\mathbf n\,dA`);
    else r.push(String.raw`\dot W_\sigma=\oint_{\partial V}(\boldsymbol\sigma\cdot\mathbf v)\cdot\mathbf n\,dA`);
    r.push(String.raw`\dot W_{\mathbf b}=\int_V\rho\mathbf b\cdot\mathbf v\,dV`);
    r.push(String.raw`\dot Q=-\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA`,String.raw`R=\int_V r_v\,dV`);
    if(!c.fija)r.push(String.raw`\dot W_b=\oint_{\partial V}p\mathbf v_b\cdot\mathbf n\,dA`);
    if(f.presionUniforme&&!c.fija)r.push(String.raw`\dot W_b=p\frac{dV}{dt}`);
    if(f.uniforme)r.push(String.raw`T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u`);
    if(f.uniforme&&f.modelo==='u_lineal')r.push(String.raw`U=m\,u(T)`);
    if(f.modelo==='u_lineal')r.push(String.raw`u(T)=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}}),\quad c_u>0`,String.raw`T=T_{\mathrm{ref}}+\frac{U/m-u_{\mathrm{ref}}}{c_u}`);
    if(f.densidadConstante)r.push(String.raw`V=\frac{m}{\rho_*},\quad\frac{dV}{dt}=\frac{1}{\rho_*}\frac{dm}{dt}`);
    if(f.sinCinetica&&f.uniforme&&f.modelo==='u_lineal')r.push(String.raw`\frac{dU}{dt}=u(T)\frac{dm}{dt}+m c_u\frac{dT}{dt}`);
  }
  if(f.sinAcumulacionTotal)r.push(String.raw`\frac{dE}{dt}=0`);
  if(f.estacionario)r.push(String.raw`\frac{\partial(\rho e)}{\partial t}=0`);
  if(f.adiabatico)r.push(String.raw`\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA=0\ \text{(no impone }\mathbf q=0\text{ dentro)} `);
  if(c.fija)r.push(String.raw`\mathbf v_b=\mathbf0`);
  return r;
}
export const sinFuentesMateriales=(f:FormulacionMateria)=>!terminosTotalesMateria(f).some(t=>t.rol==='generacion'||t.rol==='consumo');
export const transporteMaterialEliminado=(f:FormulacionMateria)=>campoEfectivo(f).sinConveccion;
