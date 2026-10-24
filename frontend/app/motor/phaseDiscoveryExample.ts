/** Editable input document. No flash, expected phases or stored solution. */
import type { HojaMotor } from './hojasMotor';
import type { SolicitudEnsamblajeV2 } from './contratoEnsamblajeV2';
import { nuevaHoja } from './hojasMotor';
import { iniciarRecorrido, recorridoMateria } from './recorridoMateria';
import { iniciarEnergia, operarEnergia, transformarEnergia, actualEnergia } from './recorridoEnergia';
import { emptyMaterialJournal, journalFromHistory } from './materialDerivation';
import { emptyEnergyJournal, energyJournalFromHistory } from './physicalDerivation';
import { deriveNetworkTemplateThermodynamics } from './materialNetworkTemplates';

export const PHASE_DISCOVERY_MODEL_ID='phase-discovery-rigid-vessel-v1';
export function createPhaseDiscoveryExamples():HojaMotor[]{
  let matter=iniciarRecorrido();
  const components=[
    {id:1,nombre:'Water',simbolo:'w',identidadQuimica:{cas:'7732-18-5'}},
    {id:2,nombre:'1-Butanol',simbolo:'b',identidadQuimica:{cas:'71-36-3'}},
  ];
  const applyMatter=(title:string,changes:Parameters<typeof recorridoMateria>[1]&{tipo:'cambiar'})=>{
    matter=recorridoMateria(matter,{...changes,titulo:title});
  };
  applyMatter('Declare component identities',{tipo:'cambiar',titulo:'',cambios:{componentes:components}});
  applyMatter('Integrate local conservation · Gauss and Reynolds',{tipo:'cambiar',titulo:'',cambios:{vista:'integral'}});
  applyMatter('Define component inventories',{tipo:'cambiar',titulo:'',cambios:{vista:'cantidad'}});
  applyMatter('No chemical generation or consumption',{tipo:'cambiar',titulo:'',cambios:{campo:{...matter.pasos[matter.activo].formulacion.campo,sinReaccion:true}}});
  applyMatter('Closed material boundary · no streams',{tipo:'cambiar',titulo:'',cambios:{restoImpermeable:true}});
  applyMatter('Rigid vessel · fixed boundary',{tipo:'cambiar',titulo:'',cambios:{fija:true}});
  let energy=iniciarEnergia({volumenId:'A',fija:true,restoCerrado:true,puertos:[],componentesIds:[1,2]});
  energy=transformarEnergia(energy,'integrada');
  energy=transformarEnergia(energy,'integral');
  energy=operarEnergia(energy,'Separate pressure and viscous stress',{separarPresion:true});
  energy=transformarEnergia(energy,'total');
  for(const [title,changes] of [
    ['Negligible kinetic energy',{sinCinetica:true}],
    ['Negligible viscous work',{sinTrabajoViscoso:true}],
    ['No body-force work',{sinFuerzasVolumen:true}],
    ['No volumetric energy source',{sinFuenteVolumetrica:true}],
    ['Uniform equilibrium state',{uniforme:true}],
  ] as const)energy=operarEnergia(energy,title,changes);
  const {componentes:_components,fronteras:_streams,...materialFormulation}=matter.pasos[matter.activo].formulacion;
  void _components;void _streams;
  const request:SolicitudEnsamblajeV2={
    revision:2,solicitudId:'configuration',componentes:components,
    paquetes:[{id:'properties',modelo:{id:'unifac-original-public',version:'1'}}],
    volumenes:[{id:'A',componenteIds:[1,2],balances:{materia:true,energia:true,momento:false},
      formulacionMateria:materialFormulation,formulacionEnergia:structuredClone(actualEnergia(energy).formulacion),
      paqueteId:'properties',politica:{cantidad:'sin_restriccion',cambioInterno:'permitido',evaluacion:'equilibrio_estable'},
      frontera:{tipo:'rigida',datoId:'volume.A.V'},
      inicial:{cantidades:{base:'molar',datoIds:{'1':'volume.A.n0.1','2':'volume.A.n0.2'}},energia:{tipo:'T',datoId:'volume.A.T0'}}}],
    corrientes:[],intercambiosTermicos:[{id:'heater',desde:null,hasta:'A',ley:{tipo:'impuesto',potenciaId:'heat.heater.Q'},temperaturaFronteraId:'heat.heater.T'}],
    datos:{
      'volume.A.n0.1':{magnitud:'cantidad',funcion:'inicial',declaracion:{texto:'0.8',unidad:'mol'},origen:{propietarioId:'volumen:A',ruta:'/datos/volume.A.n0.1'}},
      'volume.A.n0.2':{magnitud:'cantidad',funcion:'inicial',declaracion:{texto:'0.2',unidad:'mol'},origen:{propietarioId:'volumen:A',ruta:'/datos/volume.A.n0.2'}},
      'volume.A.T0':{magnitud:'temperatura',funcion:'inicial',declaracion:{texto:'298.15',unidad:'K'},origen:{propietarioId:'volumen:A',ruta:'/datos/volume.A.T0'}},
      'volume.A.V':{magnitud:'volumen',funcion:'geometria',declaracion:{texto:'10',unidad:'L'},origen:{propietarioId:'volumen:A',ruta:'/datos/volume.A.V'}},
      'heat.heater.Q':{magnitud:'potencia',funcion:'frontera',declaracion:{texto:'50',unidad:'W'},origen:{propietarioId:'calor:heater',ruta:'/datos/heat.heater.Q'}},
      'heat.heater.T':{magnitud:'temperatura',funcion:'frontera',declaracion:{texto:'600',unidad:'K'},origen:{propietarioId:'calor:heater',ruta:'/datos/heat.heater.T'}},
      'study.tf':{magnitud:'tiempo',funcion:'estudio',declaracion:{texto:'1000',unidad:'s'},origen:{propietarioId:'estudio',ruta:'/datos/study.tf'}},
    },
    estudio:{tipo:'temporal',tiempoId:'study.tf',metodoSolicitado:'rk45',muestras:11,rtol:1e-7,atol:{cantidad:1e-10,energia:1e-5}},
    derivacion:{materialDerivation:{...emptyMaterialJournal(),volumes:{A:journalFromHistory(matter)}},energyDerivation:{...emptyEnergyJournal(),volumes:{A:energyJournalFromHistory(energy)!}}},
  };
  deriveNetworkTemplateThermodynamics(request);
  return [{...nuevaHoja('Phase discovery · Water and 1-butanol in a rigid vessel',matter),id:PHASE_DISCOVERY_MODEL_ID,
    balances:{materia:true,energia:true,momento:false},
    workspaceNotes:{
      model:'A closed rigid vessel contains water and 1-butanol and receives heat. Open Matter, Energy and Thermodynamics to inspect every recorded deduction. The resulting balances conserve each component and give dU/dt = Q. UNIFAC original supplies constitutive properties; no phase count or equilibrium type is imposed.',
      transform:'Use the derived physical formulation directly. This uniform total model needs no spatial mesh. Scaling is optional; scaled equilibrium execution is not connected yet, so this example makes no scaling claim.',
      solve:'Editable inputs: 0.8 mol water, 0.2 mol 1-butanol, 298.15 K, a 10 L rigid volume, 50 W heating and a 1000 s horizon. The server computes the initial TV state, then recovers temperature, pressure and phases from n, U and V throughout the trajectory. Headspace is necessary because a completely liquid-filled incompressible package cannot determine pressure. The full run may take several minutes.',
      results:'Compare temperature, pressure, phase fractions and phase compositions. A phase may appear or vanish without changing the model or package. Inspect conservation, stability and certification alongside the plots. Duplicate the model and vary composition, heat or vessel volume to explore different predictions. These are model predictions, not experimental validation.',
    },
    redTermodinamica:{solicitud:request,nombres:{'volumen:A':'Rigid vessel','calor:heater':'External heating',estudio:'Time study'}}}];
}
