"use client";

import { useEffect, useRef, useState } from "react";

const VERTEX = `attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }`;

// A decorative, slowly deforming material study. It is not a process model.
const FRAGMENT = `precision highp float;
uniform vec2 resolution;
uniform float time;
mat2 rotate(float a) { float c=cos(a), s=sin(a); return mat2(c,-s,s,c); }
float merge(float a,float b,float k) { float h=max(k-abs(a-b),0.0)/k; return min(a,b)-h*h*k*0.25; }
float surface(vec3 p) {
  p.xz=rotate(time*0.12+0.55)*p.xz;
  p.xy=rotate(0.15*sin(time*0.17))*p.xy;
  float a=length(p/vec3(0.85,1.08,0.85))-0.88;
  float b=length((p-vec3(0.62,0.32,0.1))/vec3(0.75,0.84,0.8))-0.68;
  float c=length((p-vec3(-0.48,-0.52,0.19))/vec3(0.82,0.8,0.88))-0.66;
  float d=merge(merge(a,b,0.62),c,0.5);
  d+=0.05*sin(p.x*4.0+time*0.45)*sin(p.y*3.2-time*0.3)*sin(p.z*3.5+0.4);
  return d*0.72;
}
vec3 normalAt(vec3 p) {
  vec2 e=vec2(0.002,0.0);
  return normalize(vec3(surface(p+e.xyy)-surface(p-e.xyy),surface(p+e.yxy)-surface(p-e.yxy),surface(p+e.yyx)-surface(p-e.yyx)));
}
void main() {
  vec2 uv=(gl_FragCoord.xy-0.5*resolution)/min(resolution.x,resolution.y);
  vec3 bg=vec3(0.965,0.957,0.937);
  float shadow=exp(-dot((uv-vec2(0.03,-0.66))*vec2(1.6,6.0),(uv-vec2(0.03,-0.66))*vec2(1.6,6.0))*3.0);
  bg-=shadow*0.045;
  vec3 origin=vec3(0.0,0.08,4.6);
  vec3 ray=normalize(vec3(uv*2.9,-4.2));
  float distance=0.0;
  bool hit=false;
  vec3 p;
  for(int i=0;i<72;i++) {
    p=origin+ray*distance;
    float d=surface(p);
    if(d<0.002) { hit=true; break; }
    distance+=d;
    if(distance>7.0) break;
  }
  vec3 color=bg;
  if(hit) {
    vec3 n=normalAt(p);
    vec3 reflected=reflect(ray,n);
    float light=max(dot(n,normalize(vec3(-1.0,1.5,2.0))),0.0);
    float fresnel=pow(1.0-max(dot(n,-ray),0.0),3.0);
    float top=smoothstep(-0.6,0.85,reflected.y);
    vec3 environment=mix(vec3(0.25,0.32,0.29),vec3(0.95,0.98,0.94),top);
    float ribbon=pow(max(0.0,1.0-abs(reflected.x*0.65+reflected.y*0.3+0.15)),18.0);
    vec3 base=mix(vec3(0.37,0.46,0.4),vec3(0.79,0.84,0.76),light);
    color=mix(base,environment,0.72)+ribbon*0.22;
    color=mix(color,vec3(0.89,0.91,0.84),fresnel*0.65);
    color*=0.9+0.1*smoothstep(-1.2,0.8,p.y);
  }
  gl_FragColor=vec4(color,1.0);
}`;

export default function MateriaFluida() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const elapsedRef = useRef(2.4);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power" });
    if (!gl) return;
    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { gl.deleteShader(shader); return null; }
      return shader;
    };
    const vertex = compile(gl.VERTEX_SHADER, VERTEX);
    const fragment = compile(gl.FRAGMENT_SHADER, FRAGMENT);
    const program = gl.createProgram();
    const buffer = gl.createBuffer();
    if (!vertex || !fragment || !program || !buffer) {
      if (vertex) gl.deleteShader(vertex);
      if (fragment) gl.deleteShader(fragment);
      if (program) gl.deleteProgram(program);
      if (buffer) gl.deleteBuffer(buffer);
      return;
    }
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    const dispose = () => { gl.deleteBuffer(buffer); gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); };
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { dispose(); return; }
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const size = gl.getUniformLocation(program, "resolution");
    const time = gl.getUniformLocation(program, "time");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let visible = true;
    let last = 0;
    let elapsed = elapsedRef.current;
    const draw = (now: number) => {
      frame = 0;
      if (!visible || document.hidden) { last = 0; return; }
      if (now - last < 33 && !paused && !reduced.matches) { frame = requestAnimationFrame(draw); return; }
      if (last) elapsed += Math.min((now - last) / 1000, 0.1);
      last = now;
      elapsedRef.current = elapsed;
      const ratio = Math.min(window.devicePixelRatio, 1.4);
      const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
      const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      gl.viewport(0, 0, width, height);
      gl.uniform2f(size, width, height);
      gl.uniform1f(time, elapsed);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      canvas.style.opacity = "1";
      if (!paused && !reduced.matches) frame = requestAnimationFrame(draw);
    };
    const wake = () => { if (!frame) frame = requestAnimationFrame(draw); };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) wake(); });
    observer.observe(canvas);
    const resize = new ResizeObserver(wake);
    resize.observe(canvas);
    document.addEventListener("visibilitychange", wake);
    reduced.addEventListener("change", wake);
    wake();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); resize.disconnect(); document.removeEventListener("visibilitychange", wake); reduced.removeEventListener("change", wake); dispose(); };
  }, [paused]);

  return (
    <div className="matter-study">
      <div className="matter-art" aria-hidden="true">
        <svg className="matter-fallback" viewBox="0 0 500 500" fill="none"><path d="M136 184C103 121 169 72 228 93C294 54 337 99 341 151C409 174 415 263 363 295C368 372 293 413 235 371C168 399 108 349 131 287C91 250 99 211 136 184Z" fill="#bbc4b6"/><path d="M170 167C167 125 221 112 256 134C307 109 345 162 321 199C365 247 314 300 278 294C273 352 204 350 192 303" stroke="#e9ecdf" strokeWidth="20" strokeLinecap="round"/></svg>
        <canvas ref={canvasRef} className="matter-canvas" />
      </div>
      <div className="matter-caption"><span>Matter in motion</span><button type="button" onClick={() => setPaused(p => !p)} aria-pressed={paused} aria-label={paused ? "Resume animation" : "Pause animation"}>{paused ? "Resume" : "Pause"}<span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span></button></div>
    </div>
  );
}
