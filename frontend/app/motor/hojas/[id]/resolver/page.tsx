import ResolverHoja from '../../../ResolverHoja';
import {leerEnfoqueRed} from '../../../destinoDiagnosticoRed';
export default async function Pagina({params,searchParams}:{params:Promise<{id:string}>;searchParams:Promise<Record<string,string|string[]|undefined>>}){
  const {id}=await params,enfoque=leerEnfoqueRed(await searchParams);
  return <ResolverHoja id={id} enfoque={enfoque}/>;
}
