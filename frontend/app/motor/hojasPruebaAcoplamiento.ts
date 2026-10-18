import {nuevaHoja} from './hojasMotor';
import type {HojaMotor} from './hojasMotor';
import {iniciarConfiguracion} from './modeloNumerico';
import {iniciarRecorrido,recorridoMateria} from './recorridoMateria';
import {actualizarPuertos,claveCorriente,claveVolumen} from './ensamblajeMateria';
import type {EnsamblajeMateria,CorrienteMateria} from './ensamblajeMateria';
const dato=(texto:string|number,unidad:string)=>({texto:String(texto),unidad});
const agua=[{id:1,nombre:'Agua',simbolo:'A'}],ab=[{id:1,nombre:'A',simbolo:'A'},{id:2,nombre:'B',simbolo:'B'}];
function preparar(numero:number,nombre:string,nv:number,especies=agua){
  let h=iniciarRecorrido();h=recorridoMateria(h,{tipo:'cambiar',titulo:'Declarar componentes',cambios:{componentes:especies}});
  h=recorridoMateria(h,{tipo:'cambiar',titulo:'Usar conservación total temporal',cambios:{vista:'cantidad'}});
  h=recorridoMateria(h,{tipo:'cambiar',titulo:'Retirar fuentes y cerrar la superficie restante',cambios:{restoImpermeable:true,campo:{...h.pasos[h.activo].formulacion.campo,sinReaccion:true}}});
  const e:EnsamblajeMateria={version:1,volumenes:Array.from({length:nv},(_,i)=>({id:`v${i+1}`,nombre:`Volumen ${i+1}`,historial:structuredClone(h)})),corrientes:[],ultimoVolumen:nv,ultimaCorriente:0};
  return {...nuevaHoja(`Acoplado ${numero} · ${nombre}`,h),id:`motor-prueba-acoplado-v1-${numero}`,ensamblaje:e,volumenActivo:'v1',config:{...iniciarConfiguracion(),rtol:1e-8,atol:1e-11,tiempo:dato(10,'s')}};
}
function conectar(h:HojaMotor,corrientes:[string|null,string|null,string[]][]):HojaMotor{
  const e=h.ensamblaje!,cs=e.volumenes[0].historial.pasos[e.volumenes[0].historial.activo].formulacion.componentes!;
  e.corrientes=corrientes.map(([desde,hasta,expresiones],i)=>{const id=i+1;cs.forEach((s,j)=>h.config.datos[claveCorriente(id,s.id)]=dato(expresiones[j],'kg/s'));return {id,nombre:`Corriente ${id}`,desde,hasta,constante:expresiones.every(x=>Number.isFinite(Number(x)))} satisfies CorrienteMateria;});e.ultimaCorriente=e.corrientes.length;h.ensamblaje=actualizarPuertos(e);return h;
}
function iniciales(h:HojaMotor,masas:number[][]){h.ensamblaje!.volumenes.forEach((v,i)=>masas[i].forEach((m,j)=>h.config.datos[claveVolumen(v.id,`inicial_${j+1}`)]=dato(m,'kg')));return h;}
export function crearHojasPruebaAcoplamiento():HojaMotor[]{
  const linea=iniciales(conectar(preparar(1,'Dos tanques en serie',2),[[null,'v1',['3']],['v1','v2',['2']],['v2',null,['1']]]),[[100],[200]]);linea.config.tiempo=dato(10,'min');
  const cadena=iniciales(conectar(preparar(2,'Cadena de tres con expresiones',3),[['v1','v2',['0.1*m_A_v1']],['v2','v3',['0.1*m_A_v2']],['v3',null,['0.1*m_A_v3']]]),[[1],[0],[0]]);cadena.config.tiempo=dato(20,'s');
  const rama=iniciales(conectar(preparar(3,'División y reunión de corrientes',4),[[null,'v1',['3']],['v1','v2',['1']],['v1','v3',['2']],['v2','v4',['0.5']],['v3','v4',['1.5']],['v4',null,['2']]]),[[100],[20],[30],[40]]);rama.config.tiempo=dato(60,'s');
  const ciclo=iniciales(conectar(preparar(4,'Recirculación cerrada',3),[['v1','v2',['0.2*m_A_v1']],['v2','v3',['0.2*m_A_v2']],['v3','v1',['0.2*m_A_v3']]]),[[3],[0],[0]]);ciclo.config.tiempo=dato(20,'s');
  const selectivo=iniciales(conectar(preparar(5,'Intercambio selectivo de A',2,ab),[['v1','v2',['0.2*(m_A_v1-m_A_v2)','0']]]),[[1,2],[0,3]]);selectivo.config.tiempo=dato(10,'s');
  const reaccion=iniciales(conectar(preparar(6,'Conversión y transporte acoplados',2,ab),[['v1','v2',['0.2*m_A_v1','0.2*m_B_v1']]]),[[1,0],[0,0]]);reaccion.config.tiempo=dato(20,'s');
  const v=reaccion.ensamblaje!.volumenes[0];v.historial=recorridoMateria(v.historial,{tipo:'cambiar',titulo:'Activar generación y consumo de A y B',cambios:{campo:{...v.historial.pasos[v.historial.activo].formulacion.campo,sinReaccion:false}}});
  Object.assign(reaccion.config.datos,{v1__generacion_1:dato(0,'kg/s'),v1__consumo_1:dato('0.1*m_A','kg/s'),v1__generacion_2:dato('0.1*m_A','kg/s'),v1__consumo_2:dato(0,'kg/s')});
  return [linea,cadena,rama,ciclo,selectivo,reaccion];
}

/** Editable inputs to the same incidence engine; no special solver branches. */
export function crearHojasPruebaMulticomponente():HojaMotor[]{
  const especies=(n:number)=>Array.from({length:n},(_,i)=>({id:i+1,nombre:`Componente ${String.fromCharCode(65+i)}`,simbolo:String.fromCharCode(65+i)}));
  const serie=iniciales(conectar(preparar(7,'Mezcla de tres componentes en serie',2,especies(3)),[
    [null,'v1',['3','2','1']],['v1','v2',['1','0.5','0.25']],['v2',null,['0.25','0.25','0.25']]
  ]),[[10,20,30],[40,50,60]]);
  const selectivo=iniciales(conectar(preparar(8,'Intercambio selectivo de cuatro componentes',2,especies(4)),[
    ['v1','v2',['0.3*(rho_A_v1-rho_A_v2)','0.1*(rho_B_v1-rho_B_v2)','0.2*(rho_C_v1-rho_C_v2)','0']]
  ]),[[3,0,2,1],[0,6,4,2]]);
  selectivo.ensamblaje!.volumenes.forEach((v,i)=>{v.volumenDeclarado=true;selectivo.config.datos[claveVolumen(v.id,'volumen')]=dato(i+1,'m3');});
  const conversion=iniciales(conectar(preparar(9,'Conversión A → B → C e inerte D',3,especies(4)),[
    ['v1','v2',['0.2*m_A_v1','0.2*m_B_v1','0.2*m_C_v1','0.2*m_D_v1']],
    ['v2','v3',['0.2*m_A_v2','0.2*m_B_v2','0.2*m_C_v2','0.2*m_D_v2']]
  ]),[[1,0,0,2],[0,0,0,0],[0,0,0,0]]);conversion.config.tiempo=dato(20,'s');
  for(const v of conversion.ensamblaje!.volumenes){
    v.historial=recorridoMateria(v.historial,{tipo:'cambiar',titulo:'Conversión másica A → B → C; D inerte',cambios:{campo:{...v.historial.pasos[v.historial.activo].formulacion.campo,sinReaccion:false}}});
    const generaciones=['0','0.1*m_A','0.1*m_B','0'],consumos=['0.1*m_A','0.1*m_B','0','0'];
    generaciones.forEach((g,i)=>{conversion.config.datos[claveVolumen(v.id,`generacion_${i+1}`)]=dato(g,'kg/s');conversion.config.datos[claveVolumen(v.id,`consumo_${i+1}`)]=dato(consumos[i],'kg/s');});
  }
  const trazas=iniciales(conectar(preparar(10,'Ocho componentes y trazas',2,especies(8)),[
    ['v1','v2',especies(8).map((s,i)=>`${(0.1+0.05*i).toFixed(2)}*(m_${s.simbolo}_v1-m_${s.simbolo}_v2)`)]
  ]),[[1,2,3,4,0.01,1e-4,1e-6,1e-8],Array(8).fill(0)]);trazas.config.atol=1e-16;
  // Separate scales keep trace species visible; each plot compares both volumes.
  trazas.graficas=especies(8).map(s=>({id:`comparar-${s.id}`,nombre:`Componente ${s.simbolo} · ambos volúmenes`,tipo:'tiempo',x:'t',y:[`m_v1_c${s.id}`,`m_v2_c${s.id}`],ancha:false,altura:310,instante:trazas.config.muestras-1}));
  trazas.tableroIniciado=true;
  return [serie,selectivo,conversion,trazas].map((h,i)=>({...h,id:`motor-prueba-multicomponente-v1-${i+1}`,nombre:h.nombre.replace(/^Acoplado \d+ · /,'Multicomponente · ')}));
}
