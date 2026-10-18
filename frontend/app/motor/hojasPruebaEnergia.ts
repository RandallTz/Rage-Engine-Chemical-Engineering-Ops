import type {HojaMotor} from './hojasMotor';
import {nuevaHoja} from './hojasMotor';
import {iniciarRecorrido,recorridoMateria} from './recorridoMateria';
import {iniciarEnergia,contextoEnergia,operarEnergia,transformarEnergia} from './recorridoEnergia';
import {iniciarConfiguracion} from './modeloNumerico';
const dato=(valor:number|string,unidad:string)=>({texto:String(valor),unidad});
/** Documents for verification, compiled by the same generic term evaluator as user-created sheets. */
export function crearHojaPruebaEnergia(nombre:string,m0:number,entrada:number,salida:number,T0:number,Tin:number,Q:number|string,tiempo:number,abierto:boolean):HojaMotor{
  let m=iniciarRecorrido();
  const op=(titulo:string,cambios:Parameters<typeof recorridoMateria>[1] & {tipo:'cambiar'})=>{m=recorridoMateria(m,{...cambios,titulo});};
  op('Declarar componente A',{tipo:'cambiar',titulo:'',cambios:{componentes:[{id:1,nombre:'Fluido de prueba',simbolo:'A'}]}});
  op('Integrar la conservación de materia',{tipo:'cambiar',titulo:'',cambios:{vista:'integral'}});
  op('Expresar la conservación material total',{tipo:'cambiar',titulo:'',cambios:{vista:'cantidad'}});
  op('Retirar generación y consumo materiales',{tipo:'cambiar',titulo:'',cambios:{campo:{...m.pasos[m.activo].formulacion.campo,sinReaccion:true}}});
  op('Cerrar el transporte material por el resto',{tipo:'cambiar',titulo:'',cambios:{restoImpermeable:true}});
  op(abierto?'Declarar dos puertos y frontera móvil':'Declarar recipiente cerrado y rígido',{tipo:'cambiar',titulo:'',cambios:abierto?{fronteras:[{id:1,sentido:'entrada',constante:true},{id:2,sentido:'salida',constante:true}]}:{fija:true}});
  const f=m.pasos[m.activo].formulacion,ctx=contextoEnergia(f);
  let e=iniciarEnergia(ctx);
  e=transformarEnergia(e,'integrada');e=transformarEnergia(e,'integral');
  e=operarEnergia(e,'Separar presión y viscosidad',{separarPresion:true},[String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`]);
  if(abierto)e=operarEnergia(e,'Agrupar el trabajo de flujo en entalpía',{entalpia:true},[String.raw`h=u+p/\rho`,String.raw`\mathbf v=(\mathbf v-\mathbf v_b)+\mathbf v_b`]);
  e=transformarEnergia(e,'total');
  e=operarEnergia(e,'Despreciar energía cinética',{sinCinetica:true},[String.raw`e_c\simeq0`]);
  e=operarEnergia(e,'Retirar trabajo viscoso',{sinTrabajoViscoso:true},[String.raw`\dot W_\tau=0`]);
  e=operarEnergia(e,'Retirar trabajo de fuerzas de volumen',{sinFuerzasVolumen:true},[String.raw`\dot W_{\mathbf b}=0`]);
  e=operarEnergia(e,'Retirar aportes volumétricos',{sinFuenteVolumetrica:true},['R=0']);
  e=operarEnergia(e,'Declarar temperatura y energía específica uniformes',{uniforme:true},[String.raw`T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u`]);
  e=operarEnergia(e,'Asumir una fase',{monofasico:true},[String.raw`N_{\mathrm{fases}}=1`]);
  e=operarEnergia(e,'Excluir cambio de fase',{sinCambioFase:true},[String.raw`\text{régimen sin transición de fase}`]);
  e=operarEnergia(e,'Declarar relación u(T) lineal',{modelo:'u_lineal'},[String.raw`u=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}})`]);
  if(abierto){e=operarEnergia(e,'Declarar densidad de mezcla constante',{densidadConstante:true},[String.raw`V=m/\rho_*`]);e=operarEnergia(e,'Declarar presión uniforme e impuesta',{presionUniforme:true,presionPrescrita:true},[String.raw`P=P_{\mathrm{ext}}(t)`,String.raw`\dot W_b=p\,dm/dt/\rho_*`]);}
  const h=nuevaHoja(nombre,m);
  return {...h,vistaBalance:'energia',balances:{materia:true,energia:true,momento:false},config:{...iniciarConfiguracion(),rtol:1e-8,atol:1e-11,tiempo:dato(tiempo,'s'),datos:{inicial_1:dato(m0,'kg'),...(abierto?{entrada_1_1:dato(entrada,'kg/s'),salida_1_2:dato(salida,'kg/s')}: {})}},energia:{historial:e,atol:1e-6,datos:{energia_c:dato(4000,'J/(kg K)'),energia_u_ref:dato(0,'J/kg'),energia_T_ref:dato(293.15,'K'),energia_T0:dato(T0,'K'),energia_T_min:dato(273.15,'K'),energia_T_max:dato(373.15,'K'),energia_Q:dato(Q,'W'),...(abierto?{energia_rho:dato(1000,'kg/m3'),energia_p:dato(100000,'Pa'),energia_T_1:dato(Tin,'K')}: {})}}};
}
export function crearHojasPruebaEnergia():HojaMotor[]{
  const llenado=crearHojaPruebaEnergia('Materia + energía · Llenado con entrada caliente',100,2,1,293.15,333.15,0,100,true);
  llenado.tableroIniciado=true;
  llenado.graficas=[
    {id:'masa',nombre:'Masa acumulada',tipo:'tiempo',x:'t',y:['m_1'],ancha:false,altura:310,instante:llenado.config.muestras-1},
    {id:'temperatura',nombre:'Temperatura del volumen',tipo:'tiempo',x:'t',y:['T'],ancha:false,altura:310,instante:llenado.config.muestras-1},
  ];
  return [
  crearHojaPruebaEnergia('Energía · Recipiente cerrado calentado',10,0,0,293.15,293.15,1000,300,false),
  crearHojaPruebaEnergia('Energía · Enfriamiento por calor declarado',10,0,0,323.15,293.15,'100*(293.15-T)',300,false),
  crearHojaPruebaEnergia('Materia + energía · Entrada caliente y cantidad constante',100,2,2,293.15,333.15,0,120,true),
  crearHojaPruebaEnergia('Materia + energía · Cantidad creciente y calor',100,3,2,293.15,313.15,8000,120,true),
  crearHojaPruebaEnergia('Materia + energía · Vaciado y entrada fría',100,1,2,323.15,283.15,0,40,true),
  llenado,
].map((h,i)=>({...h,id:`motor-prueba-energia-v1-${i+1}`}));}
