import type {HojaMotor} from './hojasMotor';
import {nuevaHoja} from './hojasMotor';
import {iniciarRecorrido,recorridoMateria} from './recorridoMateria';
import {iniciarEnergia,contextoEnergia,operarEnergia,transformarEnergia} from './recorridoEnergia';
import {iniciarConfiguracion} from './modeloNumerico';
import {iniciarTermo,operarTermo} from './recorridoTermodinamico';
const dato=(valor:number|string,unidad:string)=>({texto:String(valor),unidad});
/** Documents for verification, compiled by the same generic term evaluator as user-created sheets. */
export function crearHojaPruebaEnergia(nombre:string,m0:number,entrada:number,salida:number,T0:number,Tin:number,Q:number|string,tiempo:number,abierto:boolean):HojaMotor{
  let m=iniciarRecorrido();
  const op=(titulo:string,cambios:Parameters<typeof recorridoMateria>[1] & {tipo:'cambiar'})=>{m=recorridoMateria(m,{...cambios,titulo});};
  op('Declare component A',{tipo:'cambiar',titulo:'',cambios:{componentes:[{id:1,nombre:'Reference fluid',simbolo:'A'}]}});
  op('Integrate material conservation',{tipo:'cambiar',titulo:'',cambios:{vista:'integral'}});
  op('Express total material conservation',{tipo:'cambiar',titulo:'',cambios:{vista:'cantidad'}});
  op('Exclude material generation and consumption',{tipo:'cambiar',titulo:'',cambios:{campo:{...m.pasos[m.activo].formulacion.campo,sinReaccion:true}}});
  op('Close material transport outside the streams',{tipo:'cambiar',titulo:'',cambios:{restoImpermeable:true}});
  op(abierto?'Declare two streams and a moving boundary':'Declare a closed rigid vessel',{tipo:'cambiar',titulo:'',cambios:abierto?{fronteras:[{id:1,sentido:'entrada',constante:true},{id:2,sentido:'salida',constante:true}]}:{fija:true}});
  const f=m.pasos[m.activo].formulacion,ctx=contextoEnergia(f);
  let e=iniciarEnergia(ctx);
  e=transformarEnergia(e,'integrada');e=transformarEnergia(e,'integral');
  e=operarEnergia(e,'Separate pressure and viscous stress',{separarPresion:true},[String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`]);
  if(abierto)e=operarEnergia(e,'Collect flow work into enthalpy',{entalpia:true},[String.raw`h=u+p/\rho`,String.raw`\mathbf v=(\mathbf v-\mathbf v_b)+\mathbf v_b`]);
  e=transformarEnergia(e,'total');
  e=operarEnergia(e,'Neglect kinetic energy',{sinCinetica:true},[String.raw`e_c\simeq0`]);
  e=operarEnergia(e,'Exclude viscous work',{sinTrabajoViscoso:true},[String.raw`\dot W_\tau=0`]);
  e=operarEnergia(e,'Exclude body-force work',{sinFuerzasVolumen:true},[String.raw`\dot W_{\mathbf b}=0`]);
  e=operarEnergia(e,'Exclude volumetric energy sources',{sinFuenteVolumetrica:true},['R=0']);
  e=operarEnergia(e,'Declare uniform temperature and specific internal energy',{uniforme:true},[String.raw`T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u`]);
  // Los supuestos termodinámicos van en su propia derivación (cada ecuación en su lugar); el balance de energía los usa.
  let t=iniciarTermo();
  t=operarTermo(t,'Assume a single phase',{monofasico:true},[String.raw`N_{\mathrm{fases}}=1`]);
  t=operarTermo(t,'Exclude phase change',{sinCambioFase:true},[String.raw`\text{constant phase regime}`]);
  t=operarTermo(t,'Declare a linear u(T) relation',{modelo:'u_lineal'},[String.raw`u=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}})`]);
  if(abierto)t=operarTermo(t,'Declare constant mixture density',{densidadConstante:true},[String.raw`V=m/\rho_*`]);
  if(abierto){e=operarEnergia(e,'Declare spatially uniform prescribed pressure',{presionUniforme:true,presionPrescrita:true},[String.raw`P=P_{\mathrm{ext}}(t)`,String.raw`\dot W_b=p\,dm/dt/\rho_*`]);}
  const h=nuevaHoja(nombre,m);
  return {...h,recorridoTermodinamico:t,vistaBalance:'energia',balances:{materia:true,energia:true,momento:false},config:{...iniciarConfiguracion(),rtol:1e-8,atol:1e-11,tiempo:dato(tiempo,'s'),datos:{inicial_1:dato(m0,'kg'),...(abierto?{entrada_1_1:dato(entrada,'kg/s'),salida_1_2:dato(salida,'kg/s')}: {})}},energia:{historial:e,atol:1e-6,datos:{energia_c:dato(4000,'J/(kg K)'),energia_u_ref:dato(0,'J/kg'),energia_T_ref:dato(293.15,'K'),energia_T0:dato(T0,'K'),energia_T_min:dato(273.15,'K'),energia_T_max:dato(373.15,'K'),energia_Q:dato(Q,'W'),...(abierto?{energia_rho:dato(1000,'kg/m3'),energia_p:dato(100000,'Pa'),energia_T_1:dato(Tin,'K')}: {})}}};
}
export function crearHojasPruebaEnergia():HojaMotor[]{
  const llenado=crearHojaPruebaEnergia('Matter & energy · Filling with a hot inlet',100,2,1,293.15,333.15,0,100,true);
  llenado.tableroIniciado=true;
  llenado.graficas=[
    {id:'masa',nombre:'Accumulated mass',tipo:'tiempo',x:'t',y:['m_1'],ancha:false,altura:310,instante:llenado.config.muestras-1},
    {id:'temperatura',nombre:'Volume temperature',tipo:'tiempo',x:'t',y:['T'],ancha:false,altura:310,instante:llenado.config.muestras-1},
  ];
  return [
  crearHojaPruebaEnergia('Energy · Closed heated vessel',10,0,0,293.15,293.15,1000,300,false),
  crearHojaPruebaEnergia('Energy · Cooling with a declared heat law',10,0,0,323.15,293.15,'100*(293.15-T)',300,false),
  crearHojaPruebaEnergia('Matter & energy · Hot inlet at constant inventory',100,2,2,293.15,333.15,0,120,true),
  crearHojaPruebaEnergia('Matter & energy · Growing inventory with heating',100,3,2,293.15,313.15,8000,120,true),
  crearHojaPruebaEnergia('Matter & energy · Draining with a cold inlet',100,1,2,323.15,283.15,0,40,true),
  llenado,
].map((h,i)=>({...h,id:`motor-prueba-energia-v1-${i+1}`}));}
