import type { ReactNode } from 'react';
import ModelWorkspace from '../ModelWorkspace';
export default async function Layout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) { const { id } = await params; return <ModelWorkspace id={id}>{children}</ModelWorkspace>; }
