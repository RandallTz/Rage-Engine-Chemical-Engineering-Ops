import { notFound, redirect } from 'next/navigation';
import ModelDefinition from '../../ModelDefinition';
import TransformWorkspace from '../../TransformWorkspace';
import ResolverHoja from '../../../motor/ResolverHoja';
import ResultadosHoja from '../../../motor/ResultadosHoja';
import { leerEnfoqueRed } from '../../../motor/destinoDiagnosticoRed';
import { modelUrl } from '../../workflow';
import CompilationPanel from '../../CompilationPanel';

export default async function Page({ params, searchParams }: { params: Promise<{ id: string; workspace?: string[] }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id, workspace = [] } = await params;
  const query = await searchParams;
  if (!workspace.length) redirect(modelUrl(id));
  if (workspace.join('/') === 'model') return <ModelDefinition id={id}/>;
  if (workspace.join('/') === 'model/state') return <ModelDefinition id={id} state focus={leerEnfoqueRed(query)}/>;
  if (workspace.join('/') === 'transform') return <TransformWorkspace id={id}/>;
  if (workspace.join('/') === 'solve') return <><CompilationPanel id={id}/><ResolverHoja id={id} enfoque={leerEnfoqueRed(query)}/></>;
  if (workspace.join('/') === 'results') return <ResultadosHoja id={id}/>;
  notFound();
}
