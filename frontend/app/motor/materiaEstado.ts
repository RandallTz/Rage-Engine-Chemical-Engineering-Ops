/** Shared data contracts only. No property evaluator, flash or phase detector. */
export type DatoMateria={texto:string;unidad:string};
export type CantidadMateria={valor:number;unidad:string};
export type Componente={id:number;nombre:string;simbolo:string;identidadQuimica?:{cas?:string;proveedorId?:string};masaMolar?:{cantidad:CantidadMateria;fuente:string}};
export type BaseMateria='masica'|'molar';
export type TipoFase='liquido'|'vapor'|'solido';
export type ComposicionMateria={base:BaseMateria;fracciones:Record<number,number>};
export type EspecificacionMateria=
  |{modo:'por_componente';base:BaseMateria;caudales:Partial<Record<number,DatoMateria>>}
  |{modo:'total_y_composicion';base:BaseMateria;caudalTotal:DatoMateria;composicion:ComposicionMateria};
export type DatosCorriente={materia:EspecificacionMateria;T?:DatoMateria;P?:DatoMateria;fasesPermitidas?:TipoFase[]};
export type ResultadoCorriente={
  T?:CantidadMateria;P?:CantidadMateria;composicionGlobal?:ComposicionMateria;
  caudales?:{masico?:{total:number;porComponente:Record<number,number>};molar?:{total:number;porComponente:Record<number,number>}};
  fases?:{base:BaseMateria;valores:{id:string;tipo:TipoFase;fraccion:number;composicion:ComposicionMateria}[];origen:'calculado'|'verificado';validacion:'valido'|'incompatible'|'fuera_de_dominio';modeloId:string};
  firmaEstado:string;
};
export type ReglasEstadoMateria={
  fases?:{cantidad:'sin_restriccion'|'monofasico';cambioInterno:'sin_restriccion'|'sin_cambio_de_fase';evaluacion:'no_solicitada'|'termodinamica'};
  densidades?:{variableId:string;fuente:'dato'|'propiedades';constanciaTemporal:'sin_restriccion'|'asumida'|'a_verificar'}[];
};
export type EvaluacionRegla={reglaId:string;aplicadaEnEcuaciones:boolean;verificacion:'no_solicitada'|'pendiente'|'cumple'|'no_cumple'|'no_evaluable';motivo?:string;evidencia?:{alcance:'estado'|'trayectoria'|'dominio';firmaEstado:string;modeloId:string}};
/** Flat vector descriptors: neither a chemical species nor its unit defines its bounds. */
export type VariableNumerica={id:string;propietarioId:string;magnitud:string;unidad:string;componenteId?:number;faseId?:string;rol:'diferencial'|'algebraica'|'dato';restriccion:'no_negativo'|'libre';toleranciaAbsoluta:number};

export function masaMolarKg(s:Componente):number{
  const q=s.masaMolar?.cantidad,f=q?.unidad==='kg/mol'?1:q?.unidad==='g/mol'?0.001:undefined;
  if(!q||f===undefined||!Number.isFinite(q.valor)||q.valor<=0||!s.masaMolar?.fuente.trim())throw new Error(`${s.nombre}: declara masa molar positiva, unidad y fuente para usar caudales molares.`);
  return q.valor*f;
}
