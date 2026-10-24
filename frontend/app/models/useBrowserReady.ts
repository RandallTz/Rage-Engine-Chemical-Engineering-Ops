'use client';
import { useSyncExternalStore } from 'react';
const subscribe = () => () => {};
const clientSnapshot = () => true;
const serverSnapshot = () => false;
/** Browser persistence is unavailable during server rendering. */
export function useBrowserReady() { return useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot); }
