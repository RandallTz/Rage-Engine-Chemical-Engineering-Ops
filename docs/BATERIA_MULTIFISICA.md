# Batería multifísica del Engine

Generado por `frontend/verificar_bateria_multifisica.mjs` el 2026-10-19. No editar a mano.

Cada hoja de prueba del Engine recorre el camino común: ecuaciones fundamentales y supuestos de la hoja, modelo común, compilador común (`POST /modelo/resolver`). Se compara con el cálculo que hace hoy el Engine: el solver TS o el ensamblaje v2 en vivo.

Vía de cada hoja: **balances**, ecuaciones generadas en el servidor por el motor de balances (`core/balances`) desde los supuestos de la hoja; **red**, solicitud termodinámica v2 (compilador estructural con cierre de equilibrio); **materia**, ecuaciones escritas por el adaptador del cliente (las formas que el motor de balances todavía no genera).

**38 de 41 hojas resueltas por el camino común**, y 1 de diagnóstico rechazadas con su motivo, igual que el Engine actual. Todas las resueltas coinciden con el Engine actual (tolerancia 1e-4 relativa; en la práctica entre 1e-16 y 1e-7).

## Lo que falta, agrupado por motivo

- **2** · compilador: campos con coordenadas espaciales: corresponden al motor de discretización (paso 5.2)
  - Materia · 07 · Transporte por convección · 1D
  - Materia · 08 · Difusión de dos componentes · 1D

## Matriz

| Conjunto | Hoja | Vía | Física | Modelo común | Estado | Detalle | s |
|---|---|---|---|---|---|---|---|
| Materia | 01 · Tanque que se llena | balances | materia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 6.5e-16 (resuelto); sin eventos | 0.5 |
| Materia | 02 · Tanque que se vacía | balances | materia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 2.8e-16 (resuelto); sin eventos | 0.0 |
| Materia | 03 · Llenado en litros | materia | materia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 7.9e-16 (resuelto); sin eventos | 0.0 |
| Materia | 04 · Entradas y salidas iguales | balances | materia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 1.4e-16 (resuelto); sin eventos | 0.0 |
| Materia | 05 · Vaciado hasta agotarse | balances | materia | 1 vol · 1 comp · 1 corr · 0 calor · estado supuesto | **parcial** | frente al Engine actual: 1.4e-15 (parcial); agotamiento 50.0000 | 0.0 |
| Materia | 06 · Conversión de A en B | balances | materia | 1 vol · 2 comp · 0 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 5.5e-12 (resuelto); sin eventos | 0.0 |
| Materia | 07 · Transporte por convección · 1D | materia | materia | 1 vol · 1 comp · 0 corr · 0 calor · estado supuesto | **no llega** | compilador: campos con coordenadas espaciales: corresponden al motor de discretización (paso 5.2) | 0.0 |
| Materia | 08 · Difusión de dos componentes · 1D | materia | materia | 1 vol · 2 comp · 0 corr · 0 calor · estado supuesto | **no llega** | compilador: campos con coordenadas espaciales: corresponden al motor de discretización (paso 5.2) | 0.0 |
| Energía | Energía · Recipiente cerrado calentado | balances | materia + energia | 1 vol · 1 comp · 0 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 7.8e-16 (resuelto); sin eventos | 0.0 |
| Energía | Energía · Enfriamiento por calor declarado | balances | materia + energia | 1 vol · 1 comp · 0 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 7.8e-16 (resuelto); sin eventos | 0.0 |
| Energía | Materia + energía · Entrada caliente y cantidad constante | balances | materia + energia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 1.1e-12 (resuelto); sin eventos | 0.0 |
| Energía | Materia + energía · Cantidad creciente y calor | balances | materia + energia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 2.7e-12 (resuelto); sin eventos | 0.0 |
| Energía | Materia + energía · Vaciado y entrada fría | balances | materia + energia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 2.3e-14 (resuelto); sin eventos | 0.0 |
| Energía | Materia + energía · Llenado con entrada caliente | balances | materia + energia | 1 vol · 1 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 4.0e-13 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 1 · Dos tanques en serie | balances | materia | 2 vol · 1 comp · 3 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 7.1e-16 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 2 · Cadena de tres con expresiones | balances | materia | 3 vol · 1 comp · 3 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 2.7e-12 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 3 · División y reunión de corrientes | balances | materia | 4 vol · 1 comp · 6 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 3.6e-16 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 4 · Recirculación cerrada | balances | materia | 3 vol · 1 comp · 3 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 5.6e-11 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 5 · Intercambio selectivo de A | balances | materia | 2 vol · 2 comp · 1 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 4.5e-12 (resuelto); sin eventos | 0.0 |
| Acoplamiento | Acoplado 6 · Conversión y transporte acoplados | balances | materia | 2 vol · 2 comp · 1 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 5.3e-11 (resuelto); sin eventos | 0.0 |
| Multicomponente | Multicomponente · Mezcla de tres componentes en serie | balances | materia | 2 vol · 3 comp · 3 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 8.9e-16 (resuelto); sin eventos | 0.0 |
| Multicomponente | Multicomponente · Intercambio selectivo de cuatro componentes | balances | materia | 2 vol · 4 comp · 1 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 8.1e-12 (resuelto); sin eventos | 0.0 |
| Multicomponente | Multicomponente · Conversión A → B → C e inerte D | balances | materia | 3 vol · 4 comp · 2 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 5.7e-11 (resuelto); sin eventos | 0.0 |
| Multicomponente | Multicomponente · Ocho componentes y trazas | balances | materia | 2 vol · 8 comp · 1 corr · 0 calor · estado supuesto | **resuelto** | frente al Engine actual: 1.0e-11 (resuelto); sin eventos | 0.0 |
| Multifásico | Mezcla · Calentamiento de etanol y agua | red | materia + energia | 1 vol · 2 comp · 0 corr · 1 calor · nrtl-chemsep | **resuelto** | frente al Engine actual: 2.7e-11 (resuelto); aparicion_fase 21.2407, desaparicion_fase 431.891 | 9.7 |
| Multifásico | Red · Contacto térmico de dos volúmenes de agua | red | materia + energia | 2 vol · 1 comp · 0 corr · 1 calor · agua-iapws95 | **resuelto** | frente al Engine actual: 5.7e-9 (resuelto); sin eventos | 1.7 |
| Multifásico | Red · Mezcla y transferencia entre volúmenes | red | materia + energia | 2 vol · 2 comp · 1 corr · 1 calor · nrtl-chemsep | **resuelto** | frente al Engine actual: 3.1e-9 (resuelto); sin eventos | 0.9 |
| Multifásico | Separación · Dos líquidos de agua y butanol | red | materia + energia | 1 vol · 2 comp · 1 corr · 0 calor · nrtl-lle-agua-butanol | **resuelto** | frente al Engine actual: 5.7e-16 (resuelto); sin eventos | 1.2 |
| N componentes | Mezcla ideal · Calentamiento de 5 componentes | red | materia + energia | 1 vol · 5 comp · 0 corr · 1 calor · mezcla-ideal | **resuelto** | frente al Engine actual: 2.5e-11 (resuelto); aparicion_fase 27.6163 | 7.2 |
| N componentes | NRTL · Calentamiento de 4 componentes | red | materia + energia | 1 vol · 4 comp · 0 corr · 1 calor · nrtl-chemsep | **resuelto** | frente al Engine actual: 3.3e-12 (resuelto); aparicion_fase 12.0228 | 13.7 |
| N componentes | Mezcla ideal · Calentamiento de 7 componentes | red | materia + energia | 1 vol · 7 comp · 0 corr · 1 calor · mezcla-ideal | **resuelto** | frente al Engine actual: 2.2e-11 (resuelto); aparicion_fase 36.6474 | 18.7 |
| N componentes | Red · 5 componentes con especie entrante | red | materia + energia | 2 vol · 5 comp · 1 corr · 1 calor · mezcla-ideal | **resuelto** | frente al Engine actual: 1.4e-9 (resuelto); sin eventos | 0.8 |
| N componentes | Diagnóstico · NRTL con parámetro ausente | red | materia + energia | 1 vol · 4 comp · 0 corr · 0 calor · nrtl-chemsep | **rechazada, como el Engine actual** | paquete nrtl-chemsep en el volumen A: No hay parámetros NRTL ChemSep para el par 7732-18-5 / 71-43-2; no se completan con cero. (Engine actual: no_soportado) | 0.0 |
| UNIFAC | UNIFAC original · Calentamiento de 2 componentes | red | materia + energia | 1 vol · 2 comp · 0 corr · 1 calor · unifac-original-public | **resuelto** | frente al Engine actual: 2.2e-12 (resuelto); aparicion_fase 21.9481 | 7.9 |
| UNIFAC | UNIFAC original · Calentamiento de 4 componentes | red | materia + energia | 1 vol · 4 comp · 0 corr · 1 calor · unifac-original-public | **resuelto** | frente al Engine actual: 1.0e-11 (resuelto); aparicion_fase 13.2875 | 18.4 |
| UNIFAC | UNIFAC original · Red de 5 componentes e inversión | red | materia + energia | 2 vol · 5 comp · 1 corr · 1 calor · unifac-original-public | **resuelto** | frente al Engine actual: 3.2e-7 (resuelto); aparicion_fase 113.586 | 272.0 |
| UNIFAC | UNIFAC original · Detención por política de fase | red | materia + energia | 1 vol · 2 comp · 0 corr · 1 calor · unifac-original-public | **parcial** | frente al Engine actual: 2.5e-10 (parcial); aparicion_fase 21.9481, politica_incumplida 21.9481 | 4.7 |
| UNIFAC | UNIFAC Dortmund · Calentamiento de 4 componentes | red | materia + energia | 1 vol · 4 comp · 0 corr · 1 calor · unifac-dortmund-public | **resuelto** | frente al Engine actual: 3.7e-11 (resuelto); aparicion_fase 13.7835 | 9.5 |
| UNIFAC | UNIFAC ELL · Mezcla adiabática y separación líquida | red | materia + energia | 2 vol · 2 comp · 1 corr · 0 calor · unifac-original-lle-public | **resuelto** | frente al Engine actual: 4.2e-13 (resuelto); aparicion_fase 17.7950 | 5.8 |
| Demostración | Demostración · Agua y 1-butanol: dos líquidos, heteroazeótropo y vapor | red | materia + energia | 1 vol · 2 comp · 0 corr · 1 calor · unifac-original-public | **resuelto** | frente al Engine actual: 4.2e-11 (resuelto); aparicion_fase 70.4819, desaparicion_fase 479.758, desaparicion_fase 498.944 | 113.9 |
| Demostración | Demostración · Destilación diferencial etanol–agua (Rayleigh) | red | materia + energia | 1 vol · 2 comp · 1 corr · 1 calor · nrtl-chemsep | **resuelto** | frente al Engine actual: 8.3e-11 (resuelto); sin eventos | 3.6 |
