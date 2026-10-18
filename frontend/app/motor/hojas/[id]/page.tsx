import HojaGuardada from '../../HojaGuardada';
export default async function PaginaHoja({params}:{params:Promise<{id:string}>}){const {id}=await params;return <HojaGuardada id={id}/>;}
