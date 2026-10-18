'use client';
import {useSyncExternalStore} from 'react';
import {escucharHojas,hojasServidor,leerHojas} from './hojasMotor';
export function useHojasMotor(){return useSyncExternalStore(escucharHojas,leerHojas,()=>hojasServidor);}
