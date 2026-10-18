import type {HojaMotor} from './hojasMotor';
import {contextoEnergiaHoja,formulacionEnergiaHoja,donanteCorrienteEnergia} from './estadoEnergiaHoja';
import {terminosEnergia,tienePresionPrescrita} from './recorridoEnergia';
import {campoGeometria} from './volumenControl';

export type RelacionSistemaEnergia={id:string;nombre:string;latex:string;datos:string[];definicion?:boolean};

/** Active relations of the declared model. Presentation and solver provenance share this list.
 * These identities do not certify a thermodynamic state or an independent-equation rank. */
export function relacionesSistemaEnergia(h:HojaMotor):RelacionSistemaEnergia[]{
  const f=formulacionEnergiaHoja(h),c=contextoEnergiaHoja(h),geo=campoGeometria(h),r:RelacionSistemaEnergia[]=[];
  const add=(id:string,nombre:string,latex:string,datos:string[]=[],definicion=false)=>r.push({id,nombre,latex,datos,definicion});
  if(!f.sinCinetica)add('relacion-energia-total','Energía total almacenada',String.raw`E=U+E_c,\quad E_c=\int_V\frac{\rho\mathbf v\cdot\mathbf v}{2}\,dV`,[],true);
  if(f.uniforme)add('relacion-energia','Energía almacenada',f.modelo==='u_lineal'?String.raw`U=m\,u(T)`:String.raw`U=m\,\bar u`);
  if(f.modelo==='u_lineal')add('relacion-u','Cierre energético · lineal',String.raw`u(T)=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}})`,['energia_c','energia_u_ref','energia_T_ref']);
  if(f.presionUniforme)add('relacion-presion-uniforme','Presión uniforme',String.raw`p(\mathbf x,t)=P(t)`);
  if(tienePresionPrescrita(f,c))add('relacion-presion','Presión impuesta',String.raw`P(t)=P_{\mathrm{ext}}(t)`,['energia_p']);
  if(geo)add('relacion-geometria','Volumen del dominio · fijo',String.raw`V=V_{\mathrm{geom}},\quad \frac{dV}{dt}=0`,[geo.id]);
  if(f.densidadConstante){
    add('relacion-volumen-ocupado','Volumen ocupado · densidad constante',String.raw`V_{\mathrm{ocup}}=\frac{m}{\rho_*}`,['energia_rho']);
    add('relacion-volumen','Dominio ocupado por el fluido',String.raw`V=V_{\mathrm{ocup}},\quad\frac{dV}{dt}=\frac{1}{\rho_*}\frac{dm}{dt}`);
    if(c.fija)add('relacion-compatibilidad-volumen','Compatibilidad · dominio fijo y densidad constante',String.raw`\frac{dm}{dt}=0`);
  }
  if(f.forma==='total'){
    for(const p of c.puertos){
      const donante=donanteCorrienteEnergia(h,p.id),T=donante==='exterior'?String.raw`T_{\mathrm{ext},${p.id}}`:donante==='volumen'?'T':String.raw`T_{\mathrm{don},${p.id}}`;
      if(f.modelo==='u_lineal'&&donante==='variable')add(`relacion-donante-${p.id}`,`Donante · corriente ${p.id}`,String.raw`T_{\mathrm{don},${p.id}}=\begin{cases}T_{\mathrm{ext},${p.id}}&\dot m_{${p.id}}${p.sentido==='entrada'?'>':'<'}0\\T&\dot m_{${p.id}}${p.sentido==='entrada'?String.raw`\le`:String.raw`\ge`}0\end{cases}`,[`energia_T_${p.id}`]);
      if(f.modelo==='u_lineal'&&f.entalpia&&f.densidadConstante)add(`relacion-h-${p.id}`,`Entalpía · corriente ${p.id}`,String.raw`\bar h_{${p.id}}=u(${T})+\frac{P}{\rho_*}`,donante==='volumen'?[]:[`energia_T_${p.id}`]);
      else{
        if(f.modelo==='u_lineal')add(`relacion-u-${p.id}`,`Energía transportada · corriente ${p.id}`,String.raw`\bar u_{${p.id}}=u(${T})`,donante==='volumen'?[]:[`energia_T_${p.id}`]);
        if(f.separarPresion)add(`relacion-h-${p.id}`,f.entalpia?`Entalpía · corriente ${p.id}`:`Trabajo de flujo · corriente ${p.id}`,f.entalpia?String.raw`\bar h_{${p.id}}=\bar u_{${p.id}}+\overline{(p/\rho)}_{${p.id}}`:f.densidadConstante?String.raw`\overline{(p/\rho)}_{${p.id}}=\frac{P}{\rho_*}`:String.raw`\bar h_{${p.id}}=\bar u_{${p.id}}+\overline{(p/\rho)}_{${p.id}}`);
      }
    }
    if(f.separarPresion){
      if(c.fija)add('relacion-trabajo-frontera','Trabajo de frontera',String.raw`\dot W_b=0`);
      else add('relacion-trabajo-frontera','Trabajo de frontera',f.presionUniforme?String.raw`\dot W_b=P\frac{dV}{dt}`:String.raw`\dot W_b=\oint_{\partial V}p\mathbf v_b\cdot\mathbf n\,dA`);
    }
    for(const t of terminosEnergia(f,c)){
      if(t.id==='calor')add('relacion-calor','Calor hacia el volumen',String.raw`\dot Q=-\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA`,['energia_Q'],true);
      if(t.id==='trabajo_viscoso')add('relacion-viscoso','Trabajo viscoso',String.raw`\dot W_\tau=\oint_{\partial V}(\boldsymbol\tau\cdot\mathbf v)\cdot\mathbf n\,dA`,['energia_Wtau'],true);
      if(t.id==='esfuerzos')add('relacion-esfuerzos','Trabajo de esfuerzos',String.raw`\dot W_\sigma=\oint_{\partial V}(\boldsymbol\sigma\cdot\mathbf v)\cdot\mathbf n\,dA`,[],true);
      if(t.id==='fuerzas')add('relacion-fuerzas','Trabajo de fuerzas de volumen',String.raw`\dot W_{\mathbf b}=\int_V\rho\mathbf b\cdot\mathbf v\,dV`,['energia_Wb'],true);
      if(t.id==='fuente')add('relacion-fuente','Aporte volumétrico integrado',String.raw`R=\int_Vr_v\,dV`,['energia_R'],true);
    }
  }
  return r;
}
