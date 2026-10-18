import { nuevaHoja } from './hojasMotor';
import type { HojaMotor, GraficaMotor } from './hojasMotor';
import { iniciarRecorrido, recorridoMateria } from './recorridoMateria';
import type { FormulacionMateria, RecorridoMateria } from './recorridoMateria';
import { iniciarConfiguracion } from './modeloNumerico';
import type { DatoMotor, ConfiguracionMotor } from './modeloNumerico';

/** Editable documents only. No new scenario branch in the compiler or solver. */
const dato=(texto:number|string,unidad:string):DatoMotor=>({texto:String(texto),unidad});
const agua=[{id:1,nombre:'Agua',simbolo:'A'}];
const mezcla=[{id:1,nombre:'Componente A',simbolo:'A'},{id:2,nombre:'Componente B',simbolo:'B'}];
export const IDS_PRUEBA_MATERIA=Array.from({length:8},(_,i)=>`motor-prueba-materia-v1-${i+1}`);

function operar(h:RecorridoMateria,titulo:string,cambios:Partial<FormulacionMateria>){return recorridoMateria(h,{tipo:'cambiar',titulo,cambios});}
function total(){
  let h=operar(iniciarRecorrido(),'Declarar agua como única especie',{componentes:agua});
  h=operar(h,'Expresar la conservación total',{vista:'cantidad'});
  h=operar(h,'Retirar generación y consumo',{campo:{...h.pasos[h.activo].formulacion.campo,sinReaccion:true}});
  return operar(h,'Declarar impermeable la frontera fuera de los puertos',{restoImpermeable:true});
}
function puertos(h:RecorridoMateria,entrada=true){return operar(h,'Declarar los caudales de frontera constantes',{fronteras:[...(entrada?[{id:1,sentido:'entrada' as const,constante:true}]:[]),{id:2,sentido:'salida',constante:true}]});}
function temporal(masa:number,entrada:number,salida:number,tiempo:number,unidadTiempo='s'):ConfiguracionMotor{
  return {...iniciarConfiguracion(),rtol:1e-7,atol:1e-10,tiempo:dato(tiempo,unidadTiempo),datos:{inicial_1:dato(masa,'kg'),entrada_1_1:dato(entrada,'kg/s'),salida_1_2:dato(salida,'kg/s')}};
}
function grafica(id:string,nombre:string,y:string[],tipo:'tiempo'|'perfil'='tiempo'):GraficaMotor{
  return {id,nombre,y,tipo,x:tipo==='tiempo'?'t':'x',altura:270,ancha:false,instante:100};
}
function hoja(numero:number,nombre:string,historial:RecorridoMateria,config:ConfiguracionMotor,graficas?:GraficaMotor[]):HojaMotor{
  const h=nuevaHoja(`${String(numero).padStart(2,'0')} · ${nombre}`,historial);
  return {...h,id:IDS_PRUEBA_MATERIA[numero-1],config,graficas:graficas??[],tableroIniciado:!!graficas};
}
function campo(componentes=agua){
  let h=operar(iniciarRecorrido(),'Declarar los componentes',{componentes});
  h=operar(h,'Retirar generación y consumo',{campo:{...h.pasos[h.activo].formulacion.campo,sinReaccion:true}});
  h=operar(h,'Declarar invariancia en y y z',{invariantes:[false,true,true],expandida:true});
  return operar(h,'Fijar los extremos del dominio',{fija:true});
}

export function crearHojasPruebaMateria():HojaMotor[]{
  const hojas:HojaMotor[]=[];
  hojas.push(hoja(1,'Tanque que se llena',puertos(total()),temporal(100,3,2,10,'min')));
  hojas.push(hoja(2,'Tanque que se vacía',puertos(total()),temporal(100,1,3,30)));
  let volumen=operar(puertos(total()),'Expresar la masa como densidad media por volumen',{cantidadVolumen:true});
  volumen=operar(volumen,'Declarar densidad media constante',{densidadMediaConstante:true});
  volumen=operar(volumen,'Convertir los puertos convectivos a caudales volumétricos',{densidadComunPuertos:true});
  hojas.push(hoja(3,'Llenado en litros',volumen,{...iniciarConfiguracion(),rtol:1e-7,atol:1e-11,tiempo:dato(5,'min'),datos:{inicial_1:dato(100,'L'),entrada_1_1:dato(3,'L/s'),salida_1_2:dato(1,'L/s')}}));
  hojas.push(hoja(4,'Entradas y salidas iguales',puertos(total()),temporal(100,2,2,10,'min')));
  const vaciado=temporal(100,0,2,120);delete vaciado.datos.entrada_1_1;
  hojas.push(hoja(5,'Vaciado hasta agotarse',puertos(total(),false),vaciado));
  let reaccion=operar(iniciarRecorrido(),'Declarar A y B',{componentes:mezcla});
  reaccion=operar(reaccion,'Usar balances de cantidad por componente',{vista:'cantidad'});
  reaccion=operar(reaccion,'Cerrar el dominio y retirar transporte',{fija:true,restoImpermeable:true,campo:{...reaccion.pasos[reaccion.activo].formulacion.campo,sinConveccion:true,sinDifusion:true}});
  hojas.push(hoja(6,'Conversión de A en B',reaccion,{...iniciarConfiguracion(),rtol:1e-8,atol:1e-11,tiempo:dato(20,'s'),datos:{inicial_1:dato(1,'kg'),inicial_2:dato(0,'kg'),generacion_1:dato(0,'kg/s'),consumo_1:dato('0.2*m_A','kg/s'),generacion_2:dato('0.2*m_A','kg/s'),consumo_2:dato(0,'kg/s')}},[grafica('masas','Masas de A y B',['m_1','m_2'])]));
  const unoD={...iniciarConfiguracion(),frontera:'periodica' as const,celdas:80,rtol:1e-8,atol:1e-11};
  hojas.push(hoja(7,'Transporte por convección · 1D',campo(),{...unoD,tiempo:dato(.25,'s'),datos:{inicio:dato(0,'m'),fin:dato(1,'m'),velocidad:dato(1,'m/s'),inicial_1:dato('2+0.3*sin(2*pi*x)','kg/m3')}},[grafica('evolucion','Densidad en el centro',['celda_1_40']),grafica('perfil','Perfil espacial',['rho_1'],'perfil')]));
  let difusion=campo(mezcla);
  difusion=operar(difusion,'Retirar convección y aplicar Fick con densidad total y D uniformes',{campo:{...difusion.pasos[difusion.activo].formulacion.campo,sinConveccion:true,difusion:'laplaciano'}});
  hojas.push(hoja(8,'Difusión de dos componentes · 1D',difusion,{...unoD,tiempo:dato(.5,'s'),datos:{inicio:dato(0,'m'),fin:dato(1,'m'),inicial_1:dato('0.5+0.1*sin(2*pi*x)','kg/m3'),inicial_2:dato('0.5-0.1*sin(2*pi*x)','kg/m3'),difusion_1:dato(.05,'m2/s'),difusion_2:dato(.05,'m2/s')}},[grafica('evolucion','Densidades en el centro',['celda_1_40','celda_2_40']),grafica('perfil','Perfiles de A y B',['rho_1','rho_2'],'perfil')]));
  return hojas;
}
