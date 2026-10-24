import { redirect } from 'next/navigation';
import { legacyModelUrl } from '../../../../models/workflow';
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) { const { id } = await params; redirect(legacyModelUrl(id, 'resolver', await searchParams)); }
