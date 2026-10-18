import { compilarMotor, firmaMotor, VERSION_SOLVER } from './modeloNumerico';
import type { ConfiguracionMotor, ResultadoMotor, SistemaNumerico } from './modeloNumerico';
import type { FormulacionMateria } from './recorridoMateria';

const A:number[][]=[[],[1/5],[3/40,9/40],[44/45,-56/15,32/9],[19372/6561,-25360/2187,64448/6561,-212/729],[9017/3168,-355/33,46732/5247,49/176,-5103/18656],[35/384,0,500/1113,125/192,-2187/6784,11/84]];
const C=[0,1/5,3/10,4/5,8/9,1,1];
const B=[35/384,0,500/1113,125/192,-2187/6784,11/84,0],B4=[5179/57600,0,7571/16695,393/640,-92097/339200,187/2100,1/40];
function rk45(fun:(t:number,y:number[])=>number[],t:number,y:number[],h:number) {
  const k:number[][]=[];
  for(let s=0;s<7;s++){const v=y.map((v,i)=>v+h*A[s].reduce((sum,a,j)=>sum+a*k[j][i],0));k.push(fun(t+C[s]*h,v));}
  const alto=y.map((v,i)=>v+h*B.reduce((sum,b,j)=>sum+b*k[j][i],0));
  return {y:alto,error:y.map((_,i)=>h*B.reduce((sum,b,j)=>sum+(b-B4[j])*k[j][i],0))};
}
function resolverLineal(A:number[][],b:number[]) {
  const n=b.length,a=A.map((r,i)=>[...r,b[i]]);
  for(let j=0;j<n;j++){let pivote=j;for(let i=j+1;i<n;i++)if(Math.abs(a[i][j])>Math.abs(a[pivote][j]))pivote=i;
    if(Math.abs(a[pivote][j])<1e-14)throw new Error('Jacobiano singular en el paso implícito.');
    [a[j],a[pivote]]=[a[pivote],a[j]];
    for(let i=j+1;i<n;i++){const q=a[i][j]/a[j][j];for(let k=j;k<=n;k++)a[i][k]-=q*a[j][k];}
  }
  const x=Array(n).fill(0);for(let i=n-1;i>=0;i--)x[i]=(a[i][n]-a[i].slice(i+1,n).reduce((s,v,j)=>s+v*x[i+1+j],0))/a[i][i];return x;
}
function euler(s:SistemaNumerico,t:number,y:number[],h:number,np:number,c:ConfiguracionMotor) {
  const anterior=y.slice(0,np),x=[...anterior];
  for(let iter=0;iter<30;iter++) {
    const f=s.rhs(t+h,x),g=x.map((v,i)=>v-anterior[i]-h*f[i]);
    if(g.every((v,i)=>Math.abs(v)<=Math.max(32*Number.EPSILON*Math.max(Math.abs(x[i]),Math.abs(anterior[i])),1e-6*((s.variablesNumericas?.[i].toleranciaAbsoluta??c.atol)+c.rtol*Math.max(Math.abs(x[i]),Math.abs(anterior[i]))))))return [...x,...s.balance(t+h,x).map((v,i)=>y[np+i]+h*v)];
    const magnitud=x.map((v,i)=>Math.max(Math.abs(v),Math.abs(anterior[i]),h*Math.abs(f[i]),Math.sqrt(Number.MIN_VALUE)));
    // Conditioning only: this floor neither changes physical tolerances nor probe sizes of traces.
    const piso=Math.max(...magnitud)*Math.sqrt(Number.EPSILON),escala=magnitud.map(v=>Math.max(v,piso));
    const jac=Array.from({length:np},()=>Array(np).fill(0));
    for(let j=0;j<np;j++){const eps=Math.sqrt(Number.EPSILON)*magnitud[j],xp=[...x];xp[j]+=eps;const fp=s.rhs(t+h,xp);for(let i=0;i<np;i++)jac[i][j]=((i===j?1:0)-h*(fp[i]-f[i])/eps)*escala[j]/escala[i];}
    const delta=resolverLineal(jac,g.map((v,i)=>v/escala[i])).map((v,i)=>v*escala[i]);let aplicado=false;
    for(let j=0;j<14;j++){const intento=x.map((v,i)=>v-delta[i]*2**(-j));try{s.rhs(t+h,intento);for(let i=0;i<np;i++)x[i]=intento[i];aplicado=true;break;}catch{}}
    if(!aplicado)throw new Error('El paso implícito no converge dentro del dominio.');
  }
  throw new Error('El paso implícito no convergió.');
}
export async function resolverMotor(f:FormulacionMateria,c:ConfiguracionMotor,opciones:{signal?:AbortSignal;progreso?:(valor:number)=>void}={}):Promise<ResultadoMotor> {
  return resolverSistemaMotor(compilarMotor(f,c),c,{componentes:f.componentes!,firma:firmaMotor(f,c)},opciones);
}
export async function resolverSistemaMotor(s:SistemaNumerico,c:ConfiguracionMotor,identidad:{componentes:ResultadoMotor['componentes'];firma:string},opciones:{signal?:AbortSignal;progreso?:(valor:number)=>void}={}):Promise<ResultadoMotor> {
  if(opciones.signal?.aborted)throw new Error('Cálculo cancelado.');
  const np=s.n*s.nc;
  if(s.variablesNumericas&&(s.variablesNumericas.length!==np||new Set(s.variablesNumericas.map(v=>v.id)).size!==np||s.variablesNumericas.some(v=>v.rol!=='diferencial'||!['no_negativo','libre'].includes(v.restriccion)||!Number.isFinite(v.toleranciaAbsoluta)||v.toleranciaAbsoluta<=0)))throw new Error('Descriptores numéricos inválidos: declara un estado diferencial, identidad, restricción y tolerancia positiva por entrada del vector.');
  const agotable=(i:number)=>s.variablesNumericas?s.variablesNumericas[i].restriccion==='no_negativo':true;
  const negativo=(v:number,i:number)=>agotable(i)&&v<0;
  if(s.inicial.some(negativo))throw new Error('Estado inicial fuera de la restricción no negativa.');
  for(const evento of s.eventos??[]){const v=evento.valor(0,s.inicial);if(!Number.isFinite(v)||v<0)throw new Error(`Estado inicial fuera de dominio: ${evento.nombre}.`);}
  const fun=(t:number,y:number[])=>[...s.rhs(t,y.slice(0,np)),...s.balance(t,y.slice(0,np))];
  let y=[...s.inicial,...Array(s.balance(0,s.inicial).length).fill(0)],t=0,h=s.tfinal/100,pasos=0,rechazados=0,ultimaCesion=Date.now(),estado:ResultadoMotor['estado']='resuelto',mensaje='';
  const tiempos=[0],valores=[s.observacion(0,y.slice(0,np))];
  const paso=(t:number,y:number[],h:number)=>{
    if(c.metodo==='rk45')return rk45(fun,t,y,h);
    const completo=euler(s,t,y,h,np,c),medio=euler(s,t,y,h/2,np,c),alto=euler(s,t+h/2,medio,h/2,np,c);
    return {y:alto,error:alto.map((v,i)=>v-completo[i])};
  };
  const inicialDeriv=s.rhs(0,s.inicial);
  for(const evento of s.eventos??[])if(evento.valor(0,s.inicial)===0&&evento.derivada&&evento.derivada(0,s.inicial,inicialDeriv)<0){estado='parcial';mensaje=`Evento de dominio en t = 0: ${evento.nombre}.`;break;}
  if(s.inicial.some((v,i)=>agotable(i)&&v===0&&inicialDeriv[i]<0)){estado='parcial';mensaje='Agotamiento en t = 0: el balance retiraría materia de un estado vacío.';}
  for(let muestra=1;muestra<c.muestras&&estado==='resuelto';muestra++) {
    const objetivo=s.tfinal*(muestra/(c.muestras-1));
    while(t<objetivo&&estado==='resuelto') {
      if(Date.now()-ultimaCesion>18){opciones.progreso?.(t/s.tfinal);await new Promise<void>(resolve=>setTimeout(resolve,0));ultimaCesion=Date.now();}
      if(objetivo-t<=8*Number.EPSILON*Math.max(Math.abs(objetivo),Math.abs(t),Number.MIN_VALUE)){t=objetivo;break;}
      if(opciones.signal?.aborted)throw new Error('Cálculo cancelado.');
      if(pasos+rechazados>=150000){estado='parcial';mensaje='Límite de pasos alcanzado. Revisa rigidez, malla y tolerancias.';break;}
      h=Math.min(h,objetivo-t,s.limitePaso(t,y.slice(0,np)));
      if(h<1e-14*s.tfinal||t+h===t){estado='parcial';mensaje='El integrador no puede avanzar con las tolerancias y el dominio declarados.';break;}
      let trial:{y:number[];error:number[]};
      try{trial=paso(t,y,h);}catch(e){rechazados++;h*=.25;if(h<1e-12*s.tfinal){estado='parcial';mensaje=(e as Error).message;}continue;}
      const error=Math.max(...trial.error.slice(0,np).map((v,i)=>Math.abs(v)/((s.variablesNumericas?.[i].toleranciaAbsoluta??c.atol)+c.rtol*Math.max(Math.abs(y[i]),Math.abs(trial.y[i])))));
      if(!Number.isFinite(error)){estado='parcial';mensaje='El cálculo produjo un error no finito.';break;}
      if(error>1){rechazados++;h*=Math.max(.1,.9*error**(c.metodo==='rk45'?-.2:-.5));continue;}
      // Optional state-domain events use the same full step (including budget integrals).
      // Existing material systems have no such events and keep their previous trajectory.
      const contactos=(s.eventos??[]).filter(e=>{try{return e.valor(t+h,trial.y.slice(0,np))<0;}catch{return true;}});
      if(contactos.length){
        let primero=h,seguro=y,nombre='';
        for(const evento of contactos){
          let izq=0,der=h,candidato=y;
          for(let iter=0;iter<48;iter++){
            const medio=(izq+der)/2;
            try{const z=paso(t,y,medio).y,v=evento.valor(t+medio,z.slice(0,np));if(!Number.isFinite(v)||v<0)der=medio;else{izq=medio;candidato=z;}}catch{der=medio;}
          }
          if(izq<primero){primero=izq;seguro=candidato;nombre=evento.nombre;}
        }
        t+=primero;y=seguro;estado='parcial';mensaje=`Evento de dominio: ${nombre}.`;break;
      }
      if(trial.y.slice(0,np).some(negativo)) {
        let izq=0,der=h,seguro=y;
        for(let iter=0;iter<42;iter++){const medio=(izq+der)/2;try{const z=paso(t,y,medio).y;if(z.slice(0,np).some(negativo))der=medio;else{izq=medio;seguro=z;}}catch{der=medio;}}
        t+=izq;y=seguro;estado='parcial';mensaje='Agotamiento de materia. La trayectoria se detuvo antes de producir valores negativos.';break;
      }
      y=trial.y;t+=h;pasos++;h*=error===0?4:Math.min(4,Math.max(.2,.9*error**(c.metodo==='rk45'?-.2:-.5)));
    }
    if(t>tiempos[tiempos.length-1]){tiempos.push(t);valores.push(s.observacion(t,y.slice(0,np)));}
  }
  const pesos=s.dx;
  const conservacion=Array.from({length:s.nc},(_,i)=>{
    const cambio=y.slice(i*s.n,(i+1)*s.n).reduce((sum,v,j)=>sum+(v-s.inicial[i*s.n+j])*pesos,0);return cambio-y[np+i];
  });
  opciones.progreso?.(1);
  const conservacionGlobal=s.gruposGlobales?.map((g,i)=>({id:g.id,nombre:g.nombre,residuo:g.indices.reduce((sum,j)=>sum+(y[j]-s.inicial[j]),0)-y[np+s.nc+i]}));
  return {version:1,motor:VERSION_SOLVER,modo:s.modo,metodo:s.modo==='1d'?'Volúmenes finitos conservativos + RK45 (límite CFL)':c.metodo==='rk45'?'RK45 adaptativo (Dormand–Prince 5/4)':'Euler implícito adaptativo',tiempos,x:s.x,dx:s.dx,valores,componentes:identidad.componentes,estado,mensaje,pasos,rechazados,conservacion,unidadEstado:s.unidadEstado,firma:identidad.firma,...(s.estadosAcoplados?{estadosAcoplados:s.estadosAcoplados,conservacionGlobal}:{}),...(s.variablesNumericas?{variablesNumericas:s.variablesNumericas}:{}),...(s.evaluacionReglas?{evaluacionReglas:s.evaluacionReglas}:{})};
}
