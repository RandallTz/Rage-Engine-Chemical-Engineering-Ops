"use client";
import { useReducer, useState } from 'react';
import BarraHojaMotor from './BarraHojaMotor';
import FormulaLatex from './FormulaMateria';
import ProgresoMateria from './ProgresoMateria';
import DiagramaCoordenadas from './DiagramaCoordenadas';
import GestorComponentesMateria from './GestorComponentesMateria';
import VariablesMateria from './VariablesMateria';
import { FORMAS_MATERIA, iniciarRecorrido, recorridoMateria, acumulacionTotalNula, fuenteUniforme, campoEfectivo } from './recorridoMateria';
import type { AccionMateria, FormaMateria, FormulacionMateria, RecorridoMateria } from './recorridoMateria';
import { COORDENADAS, fuentesActivas } from './operadores';
import type { Coordenadas, LeyDifusion } from './operadores';
import styles from './motor.module.css';

export default function MateriaFundamental({hojaId,nombreHoja='Nueva hoja',historialInicial,onHistorial,onNombre,enEnsamblaje=false,integrado=false}:{hojaId?:string;nombreHoja?:string;historialInicial?:RecorridoMateria;onHistorial?:(h:RecorridoMateria)=>void;onNombre?:(n:string)=>void;enEnsamblaje?:boolean;integrado?:boolean}={}) {
  const [historial, dispatchReducer] = useReducer(recorridoMateria, historialInicial, h=>h??iniciarRecorrido());
  const dispatch=(accion:AccionMateria)=>{dispatchReducer(accion);onHistorial?.(recorridoMateria(historial,accion));};
  const f = historial.pasos[historial.activo].formulacion;
  const { campo, coordenadas, vista, fronteras } = f;
  const [coordenadaPendiente, setCoordenadaPendiente] = useState<Coordenadas | null>(null);
  const cambiar = (titulo: string, cambios: Partial<FormulacionMateria>) => dispatch({ tipo: 'cambiar', titulo, cambios });
  const activas = fuentesActivas(campo);
  const difusionDeducida = f.componentes?.length === 1;
  const difusionActiva = !campoEfectivo(f).sinDifusion;
  const acumulacionDeducida = acumulacionTotalNula({ ...f, sinAcumulacion: false });
  function cambiarCoordenadas(tipo: Coordenadas) {
    if (tipo === coordenadas) return;
    if (f.invariantes.some(Boolean)) setCoordenadaPendiente(tipo);
    else cambiar(`Coordenadas: ${COORDENADAS[tipo].nombre}`, { coordenadas: tipo });
  }
  function agregar(sentido: 'entrada' | 'salida') {
    cambiar(`Declarar ${sentido}`, { fronteras: [...fronteras, { id: Math.max(0, ...fronteras.map(p => p.id)) + 1, sentido, constante: false }] });
  }
  function fuente(rol: 'generacion' | 'consumo', activa: boolean) {
    cambiar(`${activa ? 'Restaurar' : 'Eliminar'} ${rol === 'generacion' ? 'generación' : 'consumo'}`, { campo: { ...campo, sinReaccion: false, sinGeneracion: !activas.generacion, sinConsumo: !activas.consumo, [rol === 'generacion' ? 'sinGeneracion' : 'sinConsumo']: !activa }, ...(!activa ? { [rol === 'generacion' ? 'generacionUniforme' : 'consumoUniforme']: false } : {}) });
  }
  function seleccionPaso(indice: number) { setCoordenadaPendiente(null); dispatch({ tipo: 'ir', indice }); }
  return <div className={styles.page}>
    {!enEnsamblaje&&!integrado&&<BarraHojaMotor id={hojaId} nombre={nombreHoja} historial={historial} onNombre={onNombre}/>}
    <header className={styles.header}><span className={styles.eyebrow}>Engine / Ecuaciones fundamentales</span>{integrado?<h2 className={styles.tituloBalance}>Balance de materia</h2>:<h1>Balance de materia</h1>}<span className={styles.scope}>Hoja de derivación simbólica · por componente · base másica</span></header>
    <div className={styles.layout}>
      <section className={styles.equations} aria-label="Ecuaciones de materia">
        <article className={styles.equation}><header><h2>Balance fundamental</h2></header><div className={styles.wordBalance} aria-label="Acumulación = Entrada − Salida + Generación − Consumo"><span>Acumulación</span><b>=</b><span>Entrada</span><b>−</b><span>Salida</span><b>+</b><span>Generación</span><b>−</b><span>Consumo</span></div></article>
        <ProgresoMateria historial={historial} onIr={seleccionPaso} onRehacer={() => { setCoordenadaPendiente(null); dispatch({ tipo: 'rehacer' }); }} onNueva={() => { setCoordenadaPendiente(null); dispatch({ tipo: 'reiniciar' }); requestAnimationFrame(() => document.getElementById('workspace')?.scrollTo({ top: 0 })); }} />
      </section>
      <aside className={`${styles.assumptions} ${styles.operationsPanel}`} aria-label="Operaciones sobre la ecuación">
        <header><div><span className={styles.eyebrow}>Editar desde el paso {historial.activo + 1}</span><h2>Operaciones</h2></div></header>
        <GestorComponentesMateria historial={historial} onCambiar={cambiar} />
        <fieldset className={styles.operationGroup}><legend>Forma de la ecuación</legend><div className={styles.formChoices}>{(Object.keys(FORMAS_MATERIA) as FormaMateria[]).map(forma => <button aria-pressed={vista === forma} key={forma} onClick={() => cambiar(`Expresar en forma ${FORMAS_MATERIA[forma].toLowerCase()}`, { vista: forma })}>{FORMAS_MATERIA[forma]}</button>)}</div></fieldset>
        <fieldset className={styles.operationGroup}><legend>Transporte</legend>{(f.componentes?.length ?? 0) > 1 && <span className={styles.groupHint}>Operaciones para todos los componentes</span>}<div className={styles.twoOptions}>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Convección" checked={!campo.sinConveccion} onChange={e => cambiar(`${e.target.checked ? 'Restaurar' : 'Eliminar'} convección`, { campo: { ...campo, sinConveccion: !e.target.checked } })} /><span>Convección</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Difusión" checked={difusionActiva} disabled={difusionDeducida} title={difusionDeducida ? "Una especie: su velocidad coincide con la velocidad media en masa; j = 0" : undefined} onChange={e => cambiar(`${e.target.checked ? 'Restaurar' : 'Eliminar'} difusión`, { campo: { ...campo, sinDifusion: !e.target.checked } })} /><span>Difusión{difusionDeducida && <small>Cero · una sola especie</small>}</span></label>
        </div>{difusionActiva && <label className={styles.diffusionChoice}>Relación difusiva<select value={campo.difusion} onChange={e => cambiar(`Aplicar: ${e.target.selectedOptions[0].text}`, { campo: { ...campo, difusion: e.target.value as LeyDifusion } })}><option value="flujo">Flujo general · jᵢ</option><option value="fick">Fick · ρ y D variables</option><option value="laplaciano">Fick · ρ y D uniformes en espacio</option></select></label>}
          <button className={styles.textOperation} disabled={vista !== 'campo'} title={vista !== 'campo' ? 'Expansión disponible en la forma diferencial' : undefined} aria-pressed={f.expandida} onClick={() => cambiar(f.expandida ? 'Contraer operadores' : 'Expandir operadores', { expandida: !f.expandida })}>{f.expandida ? 'Contraer operadores' : 'Expandir operadores'}</button>
        </fieldset>
        <fieldset className={styles.operationGroup}><legend>Generación y consumo</legend><div className={styles.sourceOptions}>
          {(['generacion','consumo'] as const).map(rol => <div key={rol}><label className={styles.smallOption}><input type="checkbox" aria-label={rol === 'generacion' ? 'Generación' : 'Consumo'} checked={activas[rol]} onChange={e => fuente(rol, e.target.checked)} /><span>{rol === 'generacion' ? 'Generación' : 'Consumo'}</span></label><label className={styles.smallOption}><input type="checkbox" aria-label={`${rol === 'generacion' ? 'Generación' : 'Consumo'} uniforme en el espacio`} checked={activas[rol] && fuenteUniforme(f, rol)} disabled={!activas[rol] || f.invariantes.every(Boolean)} title={f.invariantes.every(Boolean) ? 'Deducida de las restricciones espaciales' : undefined} onChange={e => cambiar(`${rol === 'generacion' ? 'Generación' : 'Consumo'} ${e.target.checked ? 'uniforme en el espacio' : 'variable en el espacio'}`, { [rol === 'generacion' ? 'generacionUniforme' : 'consumoUniforme']: e.target.checked })} /><span>Uniforme en espacio</span></label></div>)}
        </div></fieldset>
        <fieldset className={styles.operationGroup}><legend>Espacio y acumulación</legend>
          <div className={`${styles.coordinateChoices} ${styles.smallCoordinates}`} role="group" aria-label="Coordenadas">{(Object.keys(COORDENADAS) as Coordenadas[]).map(tipo => <button aria-pressed={coordenadas === tipo} aria-label={COORDENADAS[tipo].nombre} key={tipo} onClick={() => cambiarCoordenadas(tipo)}><DiagramaCoordenadas tipo={tipo} /><span>{tipo === 'cartesianas' ? 'Cartesianas' : tipo === 'cilindricas' ? 'Cilíndricas' : 'Esféricas'}</span></button>)}</div>
          {coordenadaPendiente && <section className={styles.coordinateReview} aria-label="Cambio de coordenadas"><span>Se retirarán las restricciones direccionales.</span><button onClick={() => { cambiar(`Coordenadas: ${COORDENADAS[coordenadaPendiente].nombre} · retirar restricciones`, { coordenadas: coordenadaPendiente, invariantes: [false,false,false] }); setCoordenadaPendiente(null); }}>Cambiar</button><button onClick={() => setCoordenadaPendiente(null)}>Cancelar</button></section>}
          <span className={styles.groupHint}>Sin variación en:</span><div className={styles.axisToggles}>{COORDENADAS[coordenadas].ejes.map((eje, a) => <label key={eje} data-active={f.invariantes[a]}><input type="checkbox" aria-label={`Sin variación en ${eje.endsWith('theta') ? 'θ' : eje.endsWith('varphi') ? 'φ' : eje}`} checked={f.invariantes[a]} onChange={e => cambiar(`${e.target.checked ? 'Sin variación' : 'Restaurar variación'} en ${eje.endsWith('theta') ? 'θ' : eje.endsWith('varphi') ? 'φ' : eje}`, { invariantes: f.invariantes.map((x, i) => a === i ? e.target.checked : x), expandida: true })} /><FormulaLatex latex={eje} lectura={eje} /></label>)}</div>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Frontera fija" checked={f.fija} onChange={e => cambiar(e.target.checked ? 'Fijar el dominio' : 'Permitir dominio móvil', { fija: e.target.checked })} /><span>Frontera fija</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Sin acumulación local" checked={campo.estacionario} onChange={e => cambiar(e.target.checked ? 'Anular acumulación local' : 'Restaurar acumulación local', { campo: { ...campo, estacionario: e.target.checked } })} /><span>Sin acumulación local</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Sin acumulación total" checked={acumulacionTotalNula(f)} disabled={acumulacionDeducida} onChange={e => cambiar(e.target.checked ? 'Anular acumulación total' : 'Restaurar acumulación total', { sinAcumulacion: e.target.checked })} /><span>Sin acumulación total{acumulacionDeducida && <small>Deducida de las relaciones activas</small>}</span></label>
        </fieldset>
        <fieldset className={styles.operationGroup}><legend>Cantidad y volumen</legend>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Sustituir cantidad por densidad media por volumen" checked={f.cantidadVolumen} onChange={e => cambiar(e.target.checked ? 'Sustituir cantidad por densidad media × volumen' : 'Restaurar cantidad como variable', { cantidadVolumen: e.target.checked, ...(!e.target.checked ? { densidadMediaConstante: false, densidadComunPuertos: false, expandirProducto: false } : {}) })} /><span><FormulaLatex latex={String.raw`m_i=\bar\rho_i V`} lectura="Masa del componente igual a densidad media por volumen" /></span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Expandir derivada del producto" checked={f.expandirProducto} disabled={!f.cantidadVolumen || f.densidadMediaConstante || f.fija} onChange={e => cambiar(e.target.checked ? 'Aplicar regla del producto' : 'Agrupar derivada del producto', { expandirProducto: e.target.checked })} /><span>Expandir derivada del producto</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Densidad media constante en el tiempo" checked={f.densidadMediaConstante} disabled={!f.cantidadVolumen} onChange={e => cambiar(e.target.checked ? 'Densidad media constante en el tiempo' : 'Densidad media variable en el tiempo', { densidadMediaConstante: e.target.checked, ...(!e.target.checked ? { densidadComunPuertos: false } : {}) })} /><span>Densidad media constante en tiempo</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Puertos convectivos con densidad común" checked={f.densidadComunPuertos} disabled={!f.cantidadVolumen || !f.densidadMediaConstante} onChange={e => cambiar(e.target.checked ? 'Puertos convectivos y densidad común' : 'Retirar conversión de caudales', { densidadComunPuertos: e.target.checked })} /><span>Puertos convectivos, densidad común</span></label>
        </fieldset>
        {!enEnsamblaje&&<fieldset className={styles.operationGroup}><legend>Fronteras</legend><div className={styles.boundaryActions}><button onClick={() => agregar('entrada')}>+ Entrada</button><button onClick={() => agregar('salida')}>+ Salida</button></div>
          {fronteras.map(p => <div className={styles.portControl} key={p.id}><header><span>{p.sentido === 'entrada' ? 'Entrada' : 'Salida'} {p.id}</span><button aria-label={`Quitar frontera ${p.id}`} onClick={() => cambiar(`Retirar ${p.sentido} ${p.id}`, { fronteras: fronteras.filter(x => x.id !== p.id) })}>×</button></header><label className={styles.smallOption}><input type="checkbox" aria-label={`Caudal constante en frontera ${p.id}`} checked={p.constante !== false} onChange={e => cambiar(`Caudal ${p.id}: ${e.target.checked ? 'constante' : 'variable en el tiempo'}`, { fronteras: fronteras.map(x => x.id === p.id ? { ...x, constante: e.target.checked } : x) })} /><span>Caudal constante</span></label></div>)}
          <label className={styles.smallOption}><input type="checkbox" aria-label="Resto de la frontera sin flujo" checked={f.restoImpermeable} onChange={e => cambiar(e.target.checked ? 'Anular flujo en el resto de la frontera' : 'Restaurar flujo en el resto de la frontera', { restoImpermeable: e.target.checked })} /><span>Resto de la frontera sin flujo<small>Toda superficie fuera de los puertos declarados.</small></span></label>
          <details className={styles.boundaryHelp}><summary>Qué representa Φᵢ,resto</summary><span>Materia que cruza esas otras superficies, incluidas corrientes aún sin declarar. Positivo hacia fuera; negativo hacia dentro.</span><span>Sin puertos declarados, este término cubre toda la frontera. Una pared impermeable aporta cero. No es generación ni consumo.</span></details>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Flujo uniforme en los puertos" checked={f.uniforme} disabled={!fronteras.length} onChange={e => cambiar(e.target.checked ? 'Flujo uniforme por puerto' : 'Retirar uniformidad por puerto', { uniforme: e.target.checked })} /><span>Flujo uniforme por puerto</span></label>
        </fieldset>}
        {enEnsamblaje&&<fieldset className={styles.operationGroup}><legend>Frontera restante</legend><label className={styles.smallOption}><input type="checkbox" aria-label="Resto de la frontera sin flujo" checked={f.restoImpermeable} onChange={e=>cambiar(e.target.checked?'Anular flujo por la frontera restante':'Restaurar flujo por la frontera restante',{restoImpermeable:e.target.checked})}/><span>Resto sin flujo</span></label><div className={styles.groupHint}>{fronteras.map(p=>`S${p.id}: ${p.sentido}`).join(' · ')}</div></fieldset>}
        <details className={styles.details}><summary>Alcance matemático</summary><ul><li>ρᵢ, γᵢ y χᵢ son campos escalares; v y jᵢ son vectoriales.</li><li>Integrar una tasa variable no la hace uniforme. Gᵢ y Cᵢ son cantidades agregadas.</li><li>Las restricciones direccionales conservan la geometría.</li><li>La densidad media constante no supone que la densidad local sea uniforme.</li><li>V pertenece a la mezcla completa. Cada componente tiene su propia masa; no se asignan volúmenes aditivos por componente.</li><li>La velocidad es media en masa: los flujos difusivos de una mezcla completa suman cero. Las leyes escalares de Fick requieren un cierre compatible; no son un modelo multicomponente general.</li><li>Esta referencia se verifica aquí para materia, energía y momento antes de compararla con el laboratorio. La vista Resolver ejecuta materia temporal y 1D cartesiano. Energía, momento y otras discretizaciones siguen pendientes.</li></ul><a href="https://www.comsol.com/multiphysics/diffusion-equation" target="_blank" rel="noreferrer">Transporte de especies · COMSOL</a></details>
      </aside>
      <VariablesMateria formulacion={f} />
    </div>
  </div>;
}
