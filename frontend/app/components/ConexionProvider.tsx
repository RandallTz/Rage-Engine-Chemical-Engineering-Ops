"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Estado = "comprobando" | "conectado" | "desconectado";
const Context = createContext<{ estado: Estado; comprobar: () => Promise<void> } | null>(null);

export function ConexionProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>("comprobando");
  const anterior = useRef<Estado>("comprobando");
  const solicitud = useRef<AbortController | null>(null);
  const comprobar = useCallback(async () => {
    if (solicitud.current) return;
    const controller = new AbortController();
    solicitud.current = controller;
    if (anterior.current !== "conectado") setEstado("comprobando");
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const respuesta = await fetch(`${API_URL}/salud`, { signal: controller.signal, cache: "no-store" });
      const dato = respuesta.ok ? await respuesta.json() : null;
      if (dato?.estado !== "ok") throw new Error("Servicio no disponible");
      setEstado("conectado");
      if (anterior.current === "desconectado") window.dispatchEvent(new Event("api-reconectada"));
      anterior.current = "conectado";
    } catch {
      setEstado("desconectado");
      anterior.current = "desconectado";
    } finally { clearTimeout(timeout); solicitud.current = null; }
  }, []);
  useEffect(() => {
    const inicial = setTimeout(() => void comprobar(), 0);
    const intervalo = setInterval(() => { if (!document.hidden) void comprobar(); }, 20000);
    const alVolver = () => { if (!document.hidden) void comprobar(); };
    window.addEventListener("online", alVolver);
    document.addEventListener("visibilitychange", alVolver);
    return () => { clearTimeout(inicial); clearInterval(intervalo); window.removeEventListener("online", alVolver); document.removeEventListener("visibilitychange", alVolver); solicitud.current?.abort(); };
  }, [comprobar]);
  return <Context.Provider value={{ estado, comprobar }}>{children}</Context.Provider>;
}

export function useConexion() {
  const context = useContext(Context);
  if (!context) throw new Error("ConexionProvider no disponible");
  return context;
}

export default function EstadoConexion() {
  const { estado, comprobar } = useConexion();
  return <div className="connection-state" role="status"><span className={`connection-dot ${estado}`} /><span>{estado === "conectado" ? "Connected" : estado === "comprobando" ? "Connecting" : "Offline"}</span>{estado === "desconectado" && <button onClick={() => void comprobar()}>Retry</button>}</div>;
}
