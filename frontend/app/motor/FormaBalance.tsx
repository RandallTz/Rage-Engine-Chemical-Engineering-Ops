'use client';
import {useEffect,useId,useRef} from 'react';
import type {FamiliaBalance} from './familiasBalance';
import styles from './balances.module.css';

const VERTEX='attribute vec2 position; void main(){gl_Position=vec4(position,0.0,1.0);}';
/** Decorative ray-marched shape, following the organic study on the home page.
 * One geometry, three treatments. It does not represent a computed state. */
const FRAGMENT=`precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float mode;
mat2 rotate(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
float merge(float a,float b,float k){float h=max(k-abs(a-b),0.0)/k;return min(a,b)-h*h*k*0.25;}
float surface(vec3 p){
  p.y-=0.10*sin(time*0.6);
  p.xz=rotate(time*0.17+0.55)*p.xz;
  p.xy=rotate(0.18*sin(time*0.3))*p.xy;
  float a=length(p/vec3(0.85,1.08,0.85))-0.88;
  float b=length((p-vec3(0.62,0.32,0.1))/vec3(0.75,0.84,0.8))-0.68;
  float c=length((p-vec3(-0.48,-0.52,0.19))/vec3(0.82,0.8,0.88))-0.66;
  float d=merge(merge(a,b,0.62),c,0.5);
  d+=0.05*sin(p.x*4.0+time*0.45)*sin(p.y*3.2-time*0.3)*sin(p.z*3.5+0.4);
  if(mode>0.5&&mode<1.5)d+=0.055*sin(p.x*9.0-time*1.0)*sin(p.y*7.0+time*0.9)*sin(p.z*8.0);
  return d*0.72;
}
vec3 normalAt(vec3 p){vec2 e=vec2(0.002,0.0);return normalize(vec3(surface(p+e.xyy)-surface(p-e.xyy),surface(p+e.yxy)-surface(p-e.yxy),surface(p+e.yyx)-surface(p-e.yyx)));}
void main(){
  vec2 uv=(gl_FragCoord.xy-0.5*resolution)/min(resolution.x,resolution.y);
  vec3 origin=vec3(0.0,0.08,4.6),ray=normalize(vec3(uv*2.7,-4.2));
  float distance=0.0,closest=10.0;bool hit=false;vec3 p=origin;
  for(int i=0;i<72;i++){p=origin+ray*distance;float d=surface(p);closest=min(closest,d);if(d<0.002){hit=true;break;}distance+=d;if(distance>7.0)break;}
  vec3 color=vec3(0.0);float alpha=0.0;
  if(hit){
    vec3 n=normalAt(p);float light=max(dot(n,normalize(vec3(-1.0,1.5,2.0))),0.0);
    float facing=max(dot(n,-ray),0.0),fresnel=pow(1.0-facing,3.0);
    if(mode<0.5){
      vec3 reflected=reflect(ray,n);float top=smoothstep(-0.6,0.85,reflected.y);
      vec3 environment=mix(vec3(0.12,0.27,0.16),vec3(0.73,0.84,0.65),top);
      float ribbon=pow(max(0.0,1.0-abs(reflected.x*0.65+reflected.y*0.3+0.15)),18.0);
      color=mix(mix(vec3(0.19,0.34,0.20),vec3(0.51,0.66,0.40),light),environment,0.65)+ribbon*0.20;
      color=mix(color,vec3(0.76,0.85,0.64),fresnel*0.55);alpha=1.0;
    }else if(mode<1.5){
      float heat=0.5+0.5*sin(p.x*6.0+p.y*3.0-time*1.4)*sin(p.z*7.0-p.y*5.0+time*1.1);
      float veins=pow(heat,2.5);color=mix(vec3(0.69,0.08,0.035),vec3(1.0,0.53,0.13),heat*0.7+light*0.25);
      color+=veins*vec3(0.30,0.29,0.09);color=mix(color,vec3(1.0,0.68,0.28),fresnel*0.45);alpha=1.0;
    }else{
      vec3 w=p;w.xz=rotate(time*0.17+0.55)*w.xz;
      float azimuth=atan(w.z,w.x),polar=acos(clamp(w.y/max(length(w),0.001),-1.0,1.0));
      float grid=min(abs(sin(azimuth*10.0)),abs(sin(polar*14.0)));
      float line=1.0-smoothstep(0.035,0.11,grid),rim=smoothstep(0.7,0.94,fresnel);
      color=mix(vec3(0.12,0.29,0.54),vec3(0.28,0.52,0.79),light);
      alpha=max(line*(0.5+0.5*facing),rim*0.72);
    }
  }else if(mode>0.5&&mode<1.5){
    float glow=exp(-closest*14.0)*(0.6+0.2*sin(atan(uv.y,uv.x)*9.0-time));
    color=vec3(0.97,0.30,0.07);alpha=glow*0.35;
  }
  gl_FragColor=vec4(color,alpha);
}`;
const SILUETA='M136 184C103 121 169 72 228 93C294 54 337 99 341 151C409 174 415 263 363 295C368 372 293 413 235 371C168 399 108 349 131 287C91 250 99 211 136 184Z';
export default function FormaBalance({familia,pausado=false}:{familia:FamiliaBalance;pausado?:boolean}){
  const host=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null),elapsedRef=useRef(2.4),id=useId().replaceAll(':','');
  useEffect(()=>{
    const el=canvas.current,parent=host.current;if(!el||!parent)return;
    parent.dataset.ready='false';
    const gl=el.getContext('webgl',{alpha:true,antialias:false,premultipliedAlpha:false,powerPreference:'low-power'});if(!gl)return;
    const compile=(type:number,source:string)=>{const shader=gl.createShader(type);if(!shader)return null;gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){gl.deleteShader(shader);return null;}return shader;};
    const derivatives=gl.getExtension('OES_standard_derivatives');
    const fragmentSource=derivatives?`#extension GL_OES_standard_derivatives : enable\n${FRAGMENT.replace('1.0-smoothstep(0.035,0.11,grid)','1.0-smoothstep(0.025,0.025+max(fwidth(grid)*1.1,0.045),grid)')}`:FRAGMENT;
    const vertex=compile(gl.VERTEX_SHADER,VERTEX),fragment=compile(gl.FRAGMENT_SHADER,fragmentSource),program=gl.createProgram(),buffer=gl.createBuffer();
    const dispose=()=>{if(vertex)gl.deleteShader(vertex);if(fragment)gl.deleteShader(fragment);if(program)gl.deleteProgram(program);if(buffer)gl.deleteBuffer(buffer);};
    if(!vertex||!fragment||!program||!buffer){dispose();return;}
    gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS)){dispose();return;}
    gl.useProgram(program);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
    const position=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    const resolution=gl.getUniformLocation(program,'resolution'),time=gl.getUniformLocation(program,'time');gl.uniform1f(gl.getUniformLocation(program,'mode'),familia==='materia'?0:familia==='energia'?1:2);
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');let frame=0,last=0,visible=true,contextLost=false;
    const draw=(now:number)=>{frame=0;if(!visible||document.hidden||contextLost){last=0;return;}if(last&&now-last<42&&!pausado&&!reduced.matches){frame=requestAnimationFrame(draw);return;}
      if(last&&!pausado&&!reduced.matches)elapsedRef.current+=Math.min((now-last)/1000,.1);last=now;
      const ratio=Math.min(window.devicePixelRatio,1.25),width=Math.max(1,Math.round(el.clientWidth*ratio)),height=Math.max(1,Math.round(el.clientHeight*ratio));
      if(el.width!==width||el.height!==height){el.width=width;el.height=height;}gl.viewport(0,0,width,height);gl.uniform2f(resolution,width,height);gl.uniform1f(time,elapsedRef.current);gl.drawArrays(gl.TRIANGLES,0,6);parent.dataset.ready='true';
      if(!pausado&&!reduced.matches)frame=requestAnimationFrame(draw);
    };
    const wake=()=>{if(!frame)frame=requestAnimationFrame(draw);};
    const observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;wake();});observer.observe(el);
    const resize=new ResizeObserver(wake);resize.observe(el);
    const lost=(event:Event)=>{event.preventDefault();contextLost=true;parent.dataset.ready='false';cancelAnimationFrame(frame);frame=0;};el.addEventListener('webglcontextlost',lost);
    document.addEventListener('visibilitychange',wake);reduced.addEventListener('change',wake);wake();
    return()=>{cancelAnimationFrame(frame);observer.disconnect();resize.disconnect();el.removeEventListener('webglcontextlost',lost);document.removeEventListener('visibilitychange',wake);reduced.removeEventListener('change',wake);dispose();};
  },[familia,pausado]);
  return <div ref={host} className={styles.forma} data-pausado={pausado} aria-hidden="true">
    <svg className={styles.fallback} viewBox="0 0 500 500" fill="none"><defs><clipPath id={`masa-${id}`}><path d={SILUETA}/></clipPath><radialGradient id={`luz-${id}`} cx=".3" cy=".22" r=".8"><stop stopColor={familia==='energia'?'#ffc077':'#c6d8ba'}/><stop offset="1" stopColor="currentColor"/></radialGradient></defs><g className={styles.fallbackGrupo}>{familia==='momento'?<><path d={SILUETA} stroke="currentColor" strokeWidth="1.5"/><g clipPath={`url(#masa-${id})`} stroke="currentColor" strokeWidth="1.8">{Array.from({length:12},(_,i)=><ellipse key={i} cx="250" cy="235" rx={20+i*13} ry="152" transform={`rotate(${i*12-45} 250 235)`}/>)}</g></>:<><path d={SILUETA} fill={`url(#luz-${id})`}/><path d="M164 171C174 128 224 118 261 136C303 118 332 155 328 184" stroke={familia==='energia'?'#ffd49b':'#e2ead7'} strokeWidth="10" strokeLinecap="round" opacity=".6"/></>}</g></svg>
    <canvas ref={canvas}/>
  </div>;
}
