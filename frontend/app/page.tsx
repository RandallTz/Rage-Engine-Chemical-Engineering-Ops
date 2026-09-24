"use client";

import { useEffect, useState } from "react";
import DiagramaMcCabeThiele, { type DatosDiagramaMT } from "./components/DiagramaMcCabeThiele";
import EsperaCalculo from "./components/EsperaCalculo";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Metodo = "mccabe_thiele" | "ponchon_savarit" | "fug";

interface CorrienteFeed {
  composicion: number[];
  flujo_molar: number;
  T: number | null;
  P: number;
}

interface EjemploPreset {
  id: string;
  titulo: string;
  descripcion: string;
  metodo: Metodo;
  nombres: string[];
  feed: CorrienteFeed;
  parametros: Record<string, number>;
  indice_LK: number | null;
  indice_HK: number | null;
}

interface CorrienteSalida {
  nombres: string[];
  composicion: number[];
  flujo_molar: number;
  T: number;
  P: number;
}

interface ResolverColumnaResponse {
  completo: boolean;
  incognitas_restantes: string[];
  escalares: Record<string, number>;
  T_feed_usada: number;
  D: CorrienteSalida | null;
  B: CorrienteSalida | null;
  diagrama: DatosDiagramaMT | null;
}

function TablaCorriente({ titulo, corriente }: { titulo: string; corriente: CorrienteSalida | null }) {
  if (!corriente) {
    return (
      <div className="rounded border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-500">
        {titulo}: no se pudo resolver con los datos dados.
      </div>
    );
  }
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
      <h3 className="mb-2 font-semibold">{titulo}</h3>
      <p className="text-sm">Flujo molar: {corriente.flujo_molar.toFixed(4)} mol/s</p>
      <p className="text-sm">T: {corriente.T.toFixed(2)} K</p>
      <p className="text-sm">P: {corriente.P.toFixed(0)} Pa</p>
      <table className="mt-2 w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-500">
            <th>Componente</th>
            <th>Fracción molar</th>
          </tr>
        </thead>
        <tbody>
          {corriente.nombres.map((nombre, i) => (
            <tr key={nombre}>
              <td>{nombre}</td>
              <td>{corriente.composicion[i].toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Home() {
  const [ejemplos, setEjemplos] = useState<EjemploPreset[]>([]);
  const [ejemploId, setEjemploId] = useState<string>("");
  const [metodo, setMetodo] = useState<Metodo>("mccabe_thiele");
  const [nombres, setNombres] = useState<string[]>([]);
  const [composicion, setComposicion] = useState<number[]>([]);
  const [flujoMolar, setFlujoMolar] = useState<number>(100);
  const [temperaturaTexto, setTemperaturaTexto] = useState<string>("");
  const [presion, setPresion] = useState<number>(101325);
  const [parametros, setParametros] = useState<Record<string, number>>({});
  const [indiceLK, setIndiceLK] = useState<number | null>(null);
  const [indiceHK, setIndiceHK] = useState<number | null>(null);

  const [resultado, setResultado] = useState<ResolverColumnaResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/ejemplos`)
      .then((r) => r.json())
      .then((datos: EjemploPreset[]) => {
        setEjemplos(datos);
        if (datos.length > 0) aplicarEjemplo(datos[0]);
      })
      .catch(() => setError("No se pudo conectar con el backend. ¿Está corriendo en " + API_URL + "?"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function aplicarEjemplo(ejemplo: EjemploPreset) {
    setEjemploId(ejemplo.id);
    setMetodo(ejemplo.metodo);
    setNombres(ejemplo.nombres);
    setComposicion(ejemplo.feed.composicion);
    setFlujoMolar(ejemplo.feed.flujo_molar);
    setTemperaturaTexto(ejemplo.feed.T === null ? "" : String(ejemplo.feed.T));
    setPresion(ejemplo.feed.P);
    setParametros(ejemplo.parametros);
    setIndiceLK(ejemplo.indice_LK);
    setIndiceHK(ejemplo.indice_HK);
    setResultado(null);
    setError(null);
  }

  function actualizarComposicion(indice: number, valor: string) {
    const nueva = [...composicion];
    nueva[indice] = Number(valor);
    setComposicion(nueva);
  }

  function actualizarParametro(clave: string, valor: string) {
    setParametros({ ...parametros, [clave]: Number(valor) });
  }

  async function resolver() {
    setCargando(true);
    setError(null);
    setResultado(null);
    try {
      const payload = {
        metodo,
        nombres,
        feed: {
          composicion,
          flujo_molar: flujoMolar,
          T: temperaturaTexto === "" ? null : Number(temperaturaTexto),
          P: presion,
        },
        parametros,
        indice_LK: indiceLK,
        indice_HK: indiceHK,
      };
      const resp = await fetch(`${API_URL}/columna/resolver`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const detalle = await resp.json().catch(() => null);
        throw new Error(detalle?.detail ?? `Error HTTP ${resp.status}`);
      }
      setResultado(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCargando(false);
    }
  }

  const sumaComposicion = composicion.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-xl font-bold">Columna suelta</h1>
      <p className="mt-1 text-sm text-zinc-500">
        McCabe-Thiele, Ponchon-Savarit y FUG (Fenske-Underwood-Gilliland), sobre el núcleo termodinámico real
        (UNIFAC + thermo).
      </p>

      <section className="mt-6">
        <label className="block text-sm font-medium">Caso de ejemplo</label>
        <select
          className="mt-1 w-full rounded border border-zinc-700 bg-zinc-800 p-2"
          value={ejemploId}
          onChange={(e) => {
            const ejemplo = ejemplos.find((x) => x.id === e.target.value);
            if (ejemplo) aplicarEjemplo(ejemplo);
          }}
        >
          {ejemplos.map((ej) => (
            <option key={ej.id} value={ej.id}>
              {ej.titulo}
            </option>
          ))}
        </select>
        {ejemploId && (
          <p className="mt-1 text-sm text-zinc-500">
            {ejemplos.find((e) => e.id === ejemploId)?.descripcion}
          </p>
        )}
      </section>

      <section className="mt-6 grid gap-4">
        <div>
          <h2 className="font-semibold">Alimentación</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {nombres.map((nombre, i) => (
              <div key={nombre}>
                <label className="block text-xs text-zinc-500">{nombre}</label>
                <input
                  type="number"
                  step="0.001"
                  className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                  value={composicion[i] ?? 0}
                  onChange={(e) => actualizarComposicion(i, e.target.value)}
                />
              </div>
            ))}
          </div>
          <p className={`mt-1 text-xs ${Math.abs(sumaComposicion - 1) < 1e-3 ? "text-zinc-500" : "text-red-600"}`}>
            Suma de fracciones molares: {sumaComposicion.toFixed(4)} (debe ser 1.0)
          </p>

          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs text-zinc-500">Flujo molar [mol/s]</label>
              <input
                type="number"
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                value={flujoMolar}
                onChange={(e) => setFlujoMolar(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500">T [K] (vacío = punto de burbuja)</label>
              <input
                type="number"
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                value={temperaturaTexto}
                placeholder="auto"
                onChange={(e) => setTemperaturaTexto(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500">P [Pa]</label>
              <input
                type="number"
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                value={presion}
                onChange={(e) => setPresion(Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        <div>
          <h2 className="font-semibold">Parámetros del método ({metodo})</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(parametros).map(([clave, valor]) => (
              <div key={clave}>
                <label className="block text-xs text-zinc-500">{clave}</label>
                <input
                  type="number"
                  step="0.0001"
                  className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                  value={valor}
                  onChange={(e) => actualizarParametro(clave, e.target.value)}
                />
              </div>
            ))}
          </div>
          {metodo === "fug" && (
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div>
                <label className="block text-xs text-zinc-500">Índice clave ligero (0-based)</label>
                <input
                  type="number"
                  className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                  value={indiceLK ?? 0}
                  onChange={(e) => setIndiceLK(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Índice clave pesado (0-based)</label>
                <input
                  type="number"
                  className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5"
                  value={indiceHK ?? 0}
                  onChange={(e) => setIndiceHK(Number(e.target.value))}
                />
              </div>
            </div>
          )}
        </div>

        <button
          onClick={resolver}
          disabled={cargando}
          className="w-fit rounded bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {cargando ? "Resolviendo..." : "Resolver"}
        </button>

        <EsperaCalculo
          activa={cargando}
          titulo="Resolviendo la columna"
          detalle="Curva de equilibrio con UNIFAC y escalonamiento etapa a etapa."
          segundosEsperados={10}
        />

        {error && <p className="text-sm text-red-600">{error}</p>}
      </section>

      {resultado && (
        <section className="mt-8">
          <h2 className="font-semibold">Resultado</h2>
          <p className="mt-1 text-sm">
            Completo: <strong>{resultado.completo ? "sí" : "no"}</strong>
            {!resultado.completo && (
              <> — faltan: {resultado.incognitas_restantes.join(", ")}</>
            )}
          </p>
          <p className="text-sm text-zinc-500">T de alimentación usada: {resultado.T_feed_usada.toFixed(2)} K</p>

          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(resultado.escalares).map(([clave, valor]) => (
              <div key={clave} className="rounded border border-zinc-700 bg-zinc-800 p-2 text-sm">
                <div className="text-xs text-zinc-500">{clave}</div>
                <div className="font-mono">{valor.toFixed(4)}</div>
              </div>
            ))}
          </div>

          {resultado.diagrama && (
            <div className="mt-4">
              <DiagramaMcCabeThiele datos={resultado.diagrama} nombreLigero={nombres[0] ?? "ligero"} />
            </div>
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <TablaCorriente titulo="Destilado (D)" corriente={resultado.D} />
            <TablaCorriente titulo="Fondos (B)" corriente={resultado.B} />
          </div>
        </section>
      )}
    </div>
  );
}
