import EstadoSistema from '../../../EstadoSistema';
import {leerEnfoqueRed} from '../../../destinoDiagnosticoRed';
export default async function Pagina({params,searchParams}:{params:Promise<{id:string}>;searchParams:Promise<Record<string,string|string[]|undefined>>}){
  const {id}=await params,enfoque=leerEnfoqueRed(await searchParams);
  return <EstadoSistema id={id} enfoque={enfoque}/>;
}
