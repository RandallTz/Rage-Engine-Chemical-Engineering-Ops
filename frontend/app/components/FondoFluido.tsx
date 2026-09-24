"use client";

import { useEffect, useRef } from "react";

/**
 * Fondo animado tipo fluido, en WebGL, para los HUECOS de la pantalla de
 * simulaciones.
 *
 * Por que no hace falta recortar alrededor de los botones: las tarjetas
 * de esa pantalla son opacas (bg-zinc-900 sobre bg-zinc-950), asi que
 * basta con pintar ESTO DEBAJO y el contenido lo tapa solo. El efecto
 * aparece unicamente donde de verdad no hay nada.
 *
 * Reglas que cumple, en orden de importancia:
 *
 *   1. No se puede tocar        -> pointer-events: none. Nunca intercepta
 *                                  un click ni un hover de un boton.
 *   2. Solo con el raton        -> la intensidad sube al mover el raton y
 *                                  decae sola. Cuando llega a cero se
 *                                  CANCELA el bucle de animacion: con el
 *                                  raton quieto no consume GPU ni CPU.
 *   3. Discreto                 -> opacidad 0.28 y colores desaturados,
 *                                  en la gama del verde de la interfaz.
 *   4. Respeta al usuario       -> si pide menos movimiento
 *                                  (prefers-reduced-motion) no se dibuja
 *                                  nada en absoluto.
 *
 * Sin dependencias: WebGL a pelo, un quad y un fragment shader.
 */

const VERTEX = `
attribute vec2 posicion;
void main() {
  gl_Position = vec4(posicion, 0.0, 1.0);
}
`;

/**
 * Ruido fractal con "domain warping": el truco barato para que un campo
 * escalar parezca fluido en movimiento en vez de nubes estaticas. Tres
 * octavas bastan a esta opacidad; mas seria gastar GPU en algo que no se
 * ve.
 */
const FRAGMENT = `
precision mediump float;

uniform vec2  u_resolucion;
uniform float u_tiempo;
uniform vec2  u_raton;
uniform float u_intensidad;
uniform float u_claro;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float ruido(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 3; i++) {
    v += a * ruido(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolucion.xy;
  float aspecto = u_resolucion.x / max(u_resolucion.y, 1.0);
  vec2 p = vec2(uv.x * aspecto, uv.y);

  vec2 raton = vec2(u_raton.x * aspecto, u_raton.y);
  float distanciaRaton = distance(p, raton);

  // El raton empuja el campo: cuanto mas cerca, mas se deforma.
  float empuje = u_intensidad * exp(-distanciaRaton * distanciaRaton * 6.0);

  float t = u_tiempo * 0.06;
  vec2 q = vec2(fbm(p * 1.6 + vec2(t, -t * 0.7)),
                fbm(p * 1.6 + vec2(4.2 - t * 0.5, 1.3 + t)));
  vec2 r = vec2(fbm(p * 1.9 + 3.0 * q + vec2(1.7, 9.2) + empuje * 1.2),
                fbm(p * 1.9 + 3.0 * q + vec2(8.3, 2.8) - empuje * 1.2));
  float f = fbm(p * 2.2 + 2.4 * r);

  // Paleta desaturada en la gama del verde/teal de la interfaz.
  vec3 fondo  = mix(vec3(0.04, 0.05, 0.06), vec3(0.93, 0.95, 0.95), u_claro);
  vec3 frio   = mix(vec3(0.10, 0.26, 0.24), vec3(0.62, 0.78, 0.74), u_claro);
  vec3 calido = mix(vec3(0.16, 0.34, 0.28), vec3(0.70, 0.84, 0.76), u_claro);

  vec3 color = mix(fondo, frio, clamp(f * 1.35, 0.0, 1.0));
  color = mix(color, calido, clamp(length(r) * 0.55 + empuje * 0.45, 0.0, 1.0));

  // Se apaga hacia los bordes para que no aparezca un recuadro con
  // costuras: el efecto tiene que morir, no cortarse.
  float vineta = smoothstep(1.05, 0.25, distance(uv, vec2(0.5)));

  float alfa = (0.30 + 0.70 * u_intensidad) * vineta;
  gl_FragColor = vec4(color, alfa * f);
}
`;

function compilar(gl: WebGLRenderingContext, tipo: number, fuente: string) {
  const sh = gl.createShader(tipo);
  if (!sh) return null;
  gl.shaderSource(sh, fuente);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    gl.deleteShader(sh);
    return null;
  }
  return sh;
}

export default function FondoFluido() {
  const refLienzo = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const lienzo = refLienzo.current;
    if (!lienzo) return;

    // Si el usuario pidio menos movimiento, no se dibuja NADA. No es una
    // version suave: es no ejecutar el efecto.
    const menosMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (menosMovimiento.matches) return;

    const gl =
      (lienzo.getContext("webgl", { alpha: true, antialias: false, depth: false }) as
        | WebGLRenderingContext
        | null) ?? null;
    if (!gl) return; // sin WebGL simplemente no hay fondo; la pagina funciona igual

    const vs = compilar(gl, gl.VERTEX_SHADER, VERTEX);
    const fs = compilar(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    if (!vs || !fs) return;

    const programa = gl.createProgram();
    if (!programa) return;
    gl.attachShader(programa, vs);
    gl.attachShader(programa, fs);
    gl.linkProgram(programa);
    if (!gl.getProgramParameter(programa, gl.LINK_STATUS)) return;
    gl.useProgram(programa);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const attr = gl.getAttribLocation(programa, "posicion");
    gl.enableVertexAttribArray(attr);
    gl.vertexAttribPointer(attr, 2, gl.FLOAT, false, 0, 0);

    const uResolucion = gl.getUniformLocation(programa, "u_resolucion");
    const uTiempo = gl.getUniformLocation(programa, "u_tiempo");
    const uRaton = gl.getUniformLocation(programa, "u_raton");
    const uIntensidad = gl.getUniformLocation(programa, "u_intensidad");
    const uClaro = gl.getUniformLocation(programa, "u_claro");

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    const esquemaClaro = window.matchMedia("(prefers-color-scheme: light)");

    let intensidad = 0;
    let objetivo = 0;
    const raton = { x: 0.5, y: 0.5 };
    let animacion = 0;
    let vivo = true;
    const inicio = performance.now();

    function ajustarTamano() {
      if (!lienzo || !gl) return;
      // Se limita a 1x aunque la pantalla sea retina: es un fondo
      // difuso, y a 2x se pagaria el cuadruple de pixeles por una
      // diferencia que nadie ve a opacidad 0.28.
      const ancho = Math.floor(lienzo.clientWidth);
      const alto = Math.floor(lienzo.clientHeight);
      if (lienzo.width !== ancho || lienzo.height !== alto) {
        lienzo.width = ancho;
        lienzo.height = alto;
        gl.viewport(0, 0, ancho, alto);
      }
    }

    function dibujar(ahora: number) {
      if (!vivo || !gl) return;
      ajustarTamano();

      // La intensidad persigue al objetivo: sube rapido al mover el
      // raton y baja despacio, para que no de un tiron al parar.
      intensidad += (objetivo - intensidad) * (objetivo > intensidad ? 0.12 : 0.02);
      objetivo *= 0.94;

      gl.uniform2f(uResolucion, lienzo!.width, lienzo!.height);
      gl.uniform1f(uTiempo, (ahora - inicio) / 1000);
      gl.uniform2f(uRaton, raton.x, raton.y);
      gl.uniform1f(uIntensidad, intensidad);
      gl.uniform1f(uClaro, esquemaClaro.matches ? 1 : 0);
      gl.drawArrays(gl.TRIANGLES, 0, 6);

      if (intensidad < 0.004 && objetivo < 0.004) {
        // Quieto de verdad: se deja de pedir frames. Esto es lo que hace
        // que el efecto no consuma GPU con el raton parado.
        animacion = 0;
        gl.clear(gl.COLOR_BUFFER_BIT);
        return;
      }
      animacion = requestAnimationFrame(dibujar);
    }

    function despertar() {
      if (!animacion) animacion = requestAnimationFrame(dibujar);
    }

    function alMover(e: PointerEvent) {
      if (!lienzo) return;
      const caja = lienzo.getBoundingClientRect();
      raton.x = (e.clientX - caja.left) / Math.max(caja.width, 1);
      raton.y = 1 - (e.clientY - caja.top) / Math.max(caja.height, 1);
      objetivo = 1;
      despertar();
    }

    window.addEventListener("pointermove", alMover, { passive: true });
    window.addEventListener("resize", despertar, { passive: true });

    return () => {
      vivo = false;
      if (animacion) cancelAnimationFrame(animacion);
      window.removeEventListener("pointermove", alMover);
      window.removeEventListener("resize", despertar);
      gl.deleteProgram(programa);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buffer);
    };
  }, []);

  return (
    // sticky + h-0 mantiene el lienzo pegado arriba del contenedor con
    // scroll sin ocupar espacio ni desplazarse con el contenido, y sin
    // usar 'fixed' (que se colaria por encima de la barra de navegacion).
    <div aria-hidden className="pointer-events-none sticky top-0 z-0 h-0 select-none">
      <canvas
        ref={refLienzo}
        className="absolute left-0 top-0 h-screen w-full opacity-[0.28]"
      />
    </div>
  );
}
