import { configuredClosure, emptyThermodynamicJournal, thermodynamicJournalMatches, replayThermodynamics } from './physicalDerivation';
import { iniciarEnergia, operarEnergia, transformarEnergia } from './recorridoEnergia';
import type { FormulacionEnergia } from './recorridoEnergia';
import { emptyEnergyJournal, energyJournalFromHistory, energyJournalMatches, energyState } from './physicalDerivation';
/** Authored material deductions for NEW template documents, never a legacy migration. */
import type { SolicitudEnsamblajeV2 } from './contratoEnsamblajeV2';
import { iniciarRecorrido, recorridoMateria } from './recorridoMateria';
import { emptyMaterialJournal, journalFromHistory, journalMatches } from './materialDerivation';

export function deriveNetworkTemplateMatter(request: SolicitudEnsamblajeV2): void {
  const journal = emptyMaterialJournal();
  for (const volume of request.volumenes) {
    // This recipe explicitly declares the physical scope of these templates.
    // It must fail if a future example needs a law/assumption not expressed here.
    let history = iniciarRecorrido();
    const apply = (title: string, changes: Parameters<typeof recorridoMateria>[1] & { tipo: 'cambiar' }) => {
      history = recorridoMateria(history, { ...changes, titulo: title });
    };
    apply('Integrate local conservation · Gauss and Reynolds', { tipo: 'cambiar', titulo: '', cambios: { vista: 'integral' } });
    apply('Define component inventories and stream boundary partition', { tipo: 'cambiar', titulo: '', cambios: { vista: 'cantidad' } });
    apply('No chemical generation or consumption', { tipo: 'cambiar', titulo: '', cambios: { campo: { ...history.pasos[history.activo].formulacion.campo, sinReaccion: true } } });
    apply('Impermeable boundary outside the declared streams', { tipo: 'cambiar', titulo: '', cambios: { restoImpermeable: true } });
    if (volume.frontera.tipo === 'rigida') apply('Fixed control-volume boundary', { tipo: 'cambiar', titulo: '', cambios: { fija: true } });
    const entry = journalFromHistory(history);
    if (!journalMatches(entry, volume.formulacionMateria)) throw new Error(`Template volume ${volume.id} needs an explicit material deduction recipe.`);
    const { componentes: _components, fronteras: _ports, ...formulation } = history.pasos[history.activo].formulacion;
    void _components; void _ports;
    volume.formulacionMateria = { ...formulation, ...(volume.formulacionMateria.reglasEstado ? { reglasEstado: volume.formulacionMateria.reglasEstado } : {}) };
    journal.volumes[volume.id] = entry;
  }
  request.derivacion = { ...(request.derivacion && typeof request.derivacion === 'object' ? request.derivacion : {}), materialDerivation: journal };
}

/** First-law recipe for the supported uniform equilibrium examples. */
export function deriveNetworkTemplateEnergy(request: SolicitudEnsamblajeV2, adiabaticVolumes: string[] = []): void {
  const journal = emptyEnergyJournal();
  for (const volume of request.volumenes) {
    const context = {volumenId:volume.id, fija:volume.frontera.tipo==='rigida', restoCerrado:true, puertos:[], componentesIds:volume.componenteIds};
    let history = iniciarEnergia(context);
    const apply = (title:string, changes:Partial<FormulacionEnergia>) => {history=operarEnergia(history,title,changes);};
    history=transformarEnergia(history,'integrada');
    history=transformarEnergia(history,'integral');
    apply('Separate pressure and viscous stress',{separarPresion:true});
    apply('Collect flow work into enthalpy',{entalpia:true});
    history=transformarEnergia(history,'total');
    apply('Negligible kinetic energy',{sinCinetica:true});
    apply('Negligible viscous work',{sinTrabajoViscoso:true});
    apply('No body-force work',{sinFuerzasVolumen:true});
    apply('No volumetric energy source',{sinFuenteVolumetrica:true});
    apply('Uniform temperature and specific internal energy',{uniforme:true});
    if(volume.frontera.tipo==='presion_prescrita'||volume.frontera.tipo==='rigida'&&!!volume.frontera.presionRestriccionId)apply('Prescribed spatially uniform pressure',{presionUniforme:true,presionPrescrita:true});
    if(adiabaticVolumes.includes(volume.id))apply('Adiabatic boundary',{adiabatico:true});
    const entry=energyJournalFromHistory(history)!;
    if(!energyJournalMatches(entry,volume.formulacionEnergia))throw new Error(`Template volume ${volume.id} needs an explicit first-law deduction recipe.`);
    volume.formulacionEnergia={...volume.formulacionEnergia,...energyState(history.pasos.at(-1)!.formulacion)};
    journal.volumes[volume.id]=entry;
  }
  request.derivacion={...(request.derivacion as Record<string,unknown>??{}),energyDerivation:journal};
}

/** Explicit constitutive selection, rather than a claimed derivation of empirical data. */
export function deriveNetworkTemplateThermodynamics(request:SolicitudEnsamblajeV2):void {
  const journal=emptyThermodynamicJournal();
  for(const volume of request.volumenes){
    const closure=configuredClosure(request,volume);
    const entry={origin:'recorded' as const,operations:[{id:'select-equilibrium-closure',title:'Select equilibrium package, version and phase policy from the declared physical specification',changes:{closure,monofasico:closure.policy.cantidad==='monofasico',sinCambioFase:closure.policy.cambioInterno==='prohibido'}}]};
    if(!thermodynamicJournalMatches(entry,volume.formulacionEnergia,closure))throw new Error(`Template volume ${volume.id} needs an explicit thermodynamic assumption recipe.`);
    const {closure:_closure,...assumptions}=replayThermodynamics(entry);void _closure;
    volume.formulacionEnergia={...volume.formulacionEnergia,...assumptions};
    journal.volumes[volume.id]=entry;
  }
  request.derivacion={...(request.derivacion as Record<string,unknown>??{}),thermodynamicDerivation:journal};
}
