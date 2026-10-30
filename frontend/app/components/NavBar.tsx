"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import EstadoConexion from "./ConexionProvider";

export default function NavBar() {
  const ruta = usePathname();
  const portada = ruta === "/";
  return (
    <nav className={`site-nav ${portada || ruta.startsWith("/models") ? "site-nav--light" : ""}`} aria-label="Main navigation">
      <Link href="/" className="site-wordmark" aria-label="Rage — Simulation engine, home">rage<span className="wordmark-dot" aria-hidden="true">.</span></Link>
      <div className="site-nav-links max-sm:flex-wrap max-sm:justify-end max-sm:gap-y-3">
        {!portada && <EstadoConexion />}
        {!portada && <Link href="/" className="site-nav-link">Home</Link>}
        <Link href="/models" className={`site-nav-link ${(ruta === "/models" || ruta.startsWith("/models/") || ruta === "/motor") ? "is-active" : ""}`} aria-current={(ruta === "/models" || ruta.startsWith("/models/") || ruta === "/motor") ? "page" : undefined}>Engine</Link>
        <Link href="/checklist" className={`site-nav-link ${ruta === "/checklist" ? "is-active" : ""}`} aria-current={ruta === "/checklist" ? "page" : undefined}>Checklist</Link>
      </div>
    </nav>
  );
}
