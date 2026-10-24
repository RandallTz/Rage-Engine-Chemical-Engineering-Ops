'use client';
import {useMemo,useSyncExternalStore} from 'react';
import {escucharHojas,hojasServidor,leerHojas} from './hojasMotor';
export function useHojasMotor(includeRemoved=false){const models=useSyncExternalStore(escucharHojas,leerHojas,()=>hojasServidor);return useMemo(()=>includeRemoved?models:models.filter(model=>!model.removedAt),[models,includeRemoved]);}
