export type MagnitudMotor = 'masa'|'tiempo'|'longitud'|'volumen'|'densidad'|'velocidad'|'difusividad'|'caudal'|'caudal_molar'|'caudal_volumetrico'|'tasa'|'flujo'|'energia'|'energia_especifica'|'capacidad_especifica'|'potencia'|'temperatura'|'presion';
export const UNIDADES_MOTOR: Record<MagnitudMotor,Record<string,number>> = {
  energia:{J:1,kJ:1000},energia_especifica:{'J/kg':1,'kJ/kg':1000},capacidad_especifica:{'J/(kg K)':1,'kJ/(kg K)':1000},potencia:{W:1,kW:1000},temperatura:{K:1,degC:1,degF:5/9},presion:{Pa:1,kPa:1000,bar:100000},
  masa:{kg:1,g:.001},tiempo:{s:1,min:60,h:3600},longitud:{m:1,cm:.01,mm:.001},volumen:{m3:1,L:.001},
  densidad:{'kg/m3':1,'g/L':1,'kg/L':1000},velocidad:{'m/s':1,'cm/s':.01},difusividad:{'m2/s':1,'cm2/s':.0001},
  caudal:{'kg/s':1,'g/s':.001,'kg/h':1/3600,'g/h':.001/3600},tasa:{'kg/(m3 s)':1,'g/(L s)':1,'kg/(m3 h)':1/3600},flujo:{'kg/(m2 s)':1,'g/(m2 s)':.001},
  caudal_volumetrico:{'m3/s':1,'L/s':.001,'L/min':.001/60,'m3/h':1/3600},
  caudal_molar:{'mol/s':1,'mol/h':1/3600,'kmol/h':1000/3600},
};
export function convertirUnidad(m:MagnitudMotor,v:number,u:string){const f=UNIDADES_MOTOR[m][u];if(f===undefined)throw new Error(`Unidad incompatible: ${u}.`);return m==='temperatura'?u==='degC'?v+273.15:u==='degF'?(v-32)*5/9+273.15:v:v*f;}
export function factorUnidad(m:MagnitudMotor,u:string){if(m==='temperatura'&&u!=='K')throw new Error('Temperatura absoluta: usa conversión con desplazamiento.');const f=UNIDADES_MOTOR[m][u];if(f===undefined)throw new Error(`Unidad incompatible: ${u}.`);return f;}
export const nombreUnidad=(u:string)=>u.replace('degC','°C').replace('degF','°F').replaceAll('m3','m³').replaceAll('m2','m²').replace(' s)', '·s)').replace(' h)','·h)');
