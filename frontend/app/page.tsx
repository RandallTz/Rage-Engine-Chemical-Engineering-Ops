"use client";

import Link from "next/link";
import MateriaFluida from "./components/MateriaFluida";

export default function Portada() {
  return (
    <div className="minimal-home">
      <section className="minimal-hero" aria-labelledby="hero-title">
        <MateriaFluida />
        <div className="minimal-hero-copy">
          <p className="minimal-kicker">Un laboratorio para tus ideas.</p>
          <h1 id="hero-title">Simula<br /><span>ingeniería</span><br /><span>química.</span></h1>
          <p className="minimal-intro">De una mezcla a un proceso.<br />Explora, conecta y entiende lo que ocurre.</p>
          <div className="minimal-actions">
            <Link href="/models" className="minimal-primary">Create a model<span aria-hidden="true">↗</span></Link>
            <Link href="/checklist" className="minimal-text-link">What the Engine can do <span aria-hidden="true">→</span></Link>
          </div>
          <p className="minimal-note">En tu navegador. Sin registro.</p>
        </div>
      </section>
      <section className="minimal-tools" aria-label="Herramientas de simulación">
        <p>Una idea. Distintas formas de explorarla.</p>
        <div className="minimal-tool-links">
          <Link href="/models">Models <span aria-hidden="true">↗</span></Link>
          <Link href="/checklist">Checklist <span aria-hidden="true">↗</span></Link>
        </div>
      </section>
      <footer className="minimal-footer">
        <span>Equation-oriented chemical engineering models.</span>
        <details className="minimal-methods">
          <summary>Métodos y alcance <span aria-hidden="true">+</span></summary>
          <div>
            <p>Models start from the fundamental balances and reach the needed model through recorded assumptions: Model, Transform, Solve and Results.</p>
            <p>The Checklist lists the verified scope, the pending extensions and the deferred work.</p>
            <a href="https://github.com/RandallTz/Rage-Engine-Chemical-Engineering-Ops/blob/main/docs/12-validacion.md" target="_blank" rel="noopener noreferrer">Consultar validación y límites ↗</a>
          </div>
        </details>
      </footer>
    </div>
  );
}
