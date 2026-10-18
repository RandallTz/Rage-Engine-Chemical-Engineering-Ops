# Entrega única para Claude: ensamblaje y resolución dinámica del motor

**Referencia histórica:** E0–E3 entregados e integrados con el alcance y límites publicados. La continuidad se mantiene en el [roadmap principal](ROADMAP_MOTOR_MULTIFISICO.md); no se encarga repetir la entrega.

14 de octubre de 2026. Complementa `CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md` §C y la entrega H3. Claude implementa backend; Codex mantiene frontend. No modificar laboratorio, proveedor anterior ni resultados manuales. Sin commit/push.

## Encargo único y resultado esperado

**Documento único de la entrega E0–E3.** Este archivo reúne el encargo inicial de ensamblaje y su actualización posterior a H3. Los dos enlaces que recibió el usuario apuntaban a este mismo archivo. Esta versión sustituyó las indicaciones anteriores de entregar solamente E0 o pedir otro encargo antes de E1–E3; no altera el plan actual.

**H0/H1 y H3 ya están entregados.** Usar su evaluación de agua real TP/PH/UP/UV como base, conservar su regresión y sus límites. El trabajo pendiente es implementar el ensamblador y coordinador dinámico independiente, desde validación e inicialización hasta trayectorias de materia y energía con y sin cambio de fase.

**Una sola entrega final:** API de capacidades/validar/resolver, ecuaciones y variables trazables, recuento, inicialización compatible, dinámica de un volumen rígido o a presión prescrita, tratamiento de fases/eventos, ejemplos reales, pruebas y documentación para integrar el frontend. E0–E3 son fases internas de trabajo y verificación, no entregas que necesiten nuevas autorizaciones entre sí. No dar el encargo por terminado después de producir solo un borrador o un endpoint validar.

Los tipos y el adaptador de preparación están en `app/motor/contratoEnsamblajeTermodinamico.ts` y `prepararEnsamblajeTermodinamico.ts`, relativos a `frontend/`. Revisarlos y formalizar el contrato en E0 antes de escribir el coordinador. Hoy son preparación, no una API disponible: el cliente no llama a rutas nuevas ni activa un cierre real en el solver manual. Mantener el esquema compatible; documentar ajustes aditivos necesarios para que Codex los integre, sin modificar el frontend desde este encargo.

Primera ejecución: un volumen, agua pura identificada por CAS, balances totales temporales de materia y energía, estado uniforme, equilibrio macroscópico simple compresible, sin reacción ni transferencia selectiva. Los caudales son fronteras declaradas, no una ley de salida k·m fabricada. La arquitectura se basa en componentes/puertos/relaciones, no en nombres de hojas, ejemplos o equipos.

Implementar en este orden dentro del mismo encargo:

1. **E0:** formalizar el contrato, ensamblar ecuaciones y catálogo, validar datos y preparar una inicialización compatible. El endpoint validar no integra, aunque el encargo completo sí incluye resolver.
2. **E1 / H2:** volumen rígido monofásico con cierre UV, cerrado y abierto dentro del alcance declarado.
3. **E2 / H2:** frontera móvil a presión exterior prescrita, con trabajo completo y volumen variable.
4. **E3 / H4:** equilibrio bifásico durante la trayectoria, extracción declarada, aparición/desaparición de fases y eventos. No publicar E3 como disponible porque el flash estático H3 exista.

Completar las pruebas de cada fase antes de avanzar a la siguiente y publicar únicamente capacidades verificadas. Resolver decisiones rutinarias con este contrato y la física documentada, sin detenerse para pedir autorización por cada fase. Si aparece una incompatibilidad fundamental o una limitación física real, documentar su reproducción, alcance y propuesta compatible; no ocultarla mediante valores por omisión, un contrato paralelo o capacidades ficticias. La entrega final debe indicar qué requisitos se completaron y cualquier bloqueo real; una fase no implementada no se presenta como cumplida.

Quedan fuera de esta entrega: varios volúmenes dinámicos, mezclas, reacción, transferencia selectiva, momento/CFD, nuevos equipos, sólidos y ampliación del dominio crítico. El ensamblador debe organizarse por componentes, relaciones y puertos para extenderlo posteriormente; las pruebas de tanques no justifican ramas de código por nombre de escenario.

Referencias de fundamento: [conservación en un volumen de control y trabajo de flujo, MIT](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node19.html) y [potenciales de equilibrio y mínimo de Helmholtz a T,V constantes, MIT](https://ocw.mit.edu/courses/3-00-thermodynamics-of-materials-fall-2002/d3e9629df5ebc6f89d0cc15c6e24db88_lecture_19_oneside.PDF). Las decisiones específicas de EOS, dominio y coexistencia siguen la entrega física IAPWS de Claude.

## 1. Primera ley y estados

Conservar las ecuaciones generales y sus reducciones declaradas. Para el primer régimen, con flujos orientados por corriente:

```
dm_i/dt = sum(entradas por componente) - sum(salidas por componente)
J_E = sum(F_entrada h_donante) - sum(F_salida h_donante) + Q
dU/dt = J_E - P_ext dV/dt
U = m u_estado
V = m v_estado
```

El flujo transporta entalpía, o energía interna más trabajo de flujo si el usuario conserva esa separación. Se puede normalizar internamente a h para resolver, pero publicar la identidad aplicada y mantener la derivación original; no cambiar la física de la agrupación. Calor positivo entra. El trabajo de frontera positivo se resta de U. Cantidades, entalpía y energía deben compartir las referencias del modelo IAPWS seleccionado.

**Volumen rígido:** V=V_geom y dV/dt=0; estados diferenciales m_i y U. T/P/fases salen del cierre UV. La presión puede cambiar al calentarse; no imponer densidad constante ni copiar una P de la consulta puntual. Una P prescrita adicional es una restricción que requiere análisis de compatibilidad: el borrador la conserva y diagnostica, no la borra para resolver.

**Presión exterior prescrita:** primera reducción cuasiestática con P=P_ext(t), presión uniforme y equilibrio mecánico en la frontera. Con m_i,U,P se evalúa UP, obteniendo T,V/fases. El trabajo es P_ext dV/dt con la derivada total. Para una fase, V=m v(T,P) contiene términos composicionales/temporales que no se sustituyen por dm/dt/ρ constante.

Puede usarse H=U+PV como coordenada numérica si se deriva y verifica:

```
dH/dt = J_E + V dP_ext/dt
U = H - P_ext V
```

Entonces H es diferencial y U es reconstruida; no contar/integrar U y H como dos estados independientes. Conservar U en la salida física y declarar la transformación. P con escalones requiere una regla física de trabajo/impulso y reinicialización; no tratar una discontinuidad como derivada cero. La primera capacidad puede limitarse a P constante y luego a funciones suaves verificadas.

La EOS recupera equilibrio mecánico de un estado concentrado. No representa un balance distribuido de momento ni predice hidráulicamente el caudal. Una bomba, pérdida de carga o trabajo adicional requieren su relación y balance; no aparecen por elegir presión prescrita.

## 2. Datos y fuente única

El tipo `SolicitudEnsamblajeDinamico` es la referencia exacta de campos de este borrador:

- `componentes`: único catálogo con IDs, identidad y masa molar opcional/fuente. El volumen y corrientes referencian IDs. El agua simbólica por nombre no identifica la EOS.
- `volumen`: balances activos, formulaciones estructuradas efectivas, contexto/puertos, elección del cierre, frontera e iniciales referenciadas.
- `corrientes`: extremos, mecanismo, especificación de materia y estado exterior cuando puede ser donante. Una corriente tiene una variable compartida, no una copia de entrada y otra de salida.
- `datos`: registro único por variable ID. Cada entrada trae magnitud, función, texto/unidad declarados y `origen` con propietario/ruta para volver al campo. Una referencia no duplica el valor.
- `transferencias`: referencias a Q u otras leyes admitidas. Adiabático efectivo retira Q del ensamblaje; no interpreta un Q vacío como cero.
- `estudio`: tiempo con unidad, muestreo, método solicitado y tolerancias separadas.
- `derivacion`: pasos matemáticos reales del usuario para auditar. El backend ejecuta la formulación estructurada, nunca interpreta LaTeX ni convierte los títulos en leyes físicas.

No se envían los resultados guardados de una consulta, parámetros inactivos de u(T) ni valores deducidos de una gráfica. `cierresDinamicos` guarda únicamente elecciones (modelo/versión/política, extracción y continuidad de presión); los valores siguen en sus declaraciones originales. Una declaración explícita de masa molar contradictoria no se elimina para aceptar la petición.

Los dos modos de materia son exclusivos: caudales por componente, o caudal total más composición. La base del caudal y la de composición se preservan por separado. Un total molar no implica una composición molar si fue declarada másica. Masa↔moles necesita masas molares verificadas; no hay conversión universal ni composición inventada.

Declaraciones ausentes/blancas significan pendiente, nunca cero. Cero explícito conserva su papel de dato. El backend valida sintaxis, unidades, dimensiones, valores finitos y límites físicos. Para E1 pueden admitirse constantes y funciones temporales suaves verificadas; otras expresiones deben recibir diagnóstico con su ruta si aún no están implementadas. No ejecutar texto arbitrario ni deducir relaciones del nombre de una variable. Una función dependiente de estados aporta una relación al ensamblaje; no contar su valor calculado como especificación independiente.

La preparación local detecta algunos datos pendientes, duplicados e incompatibilidades, pero **no calcula grados de libertad ni certifica que la física esté lista**. Conflictos/inválidos/no soportados locales impiden envío automático de esa petición. Un documento incompleto puede llegar a validar para que el backend publique su análisis. La revisión HTTP del ensamblaje es independiente de la revisión 1 de la API estática, que no se modifica.

## 3. Inicialización: dato frente a resultado

Solo una elección inicial de energía está activa: U(0) o T(0), junto con m_i(0) y la frontera. Datos conservados del modo inactivo no se convierten en restricciones adicionales. Nunca convertir T inicial a U con el `c_u` manual cuando se solicita IAPWS.

| Frontera | Datos iniciales | Operación necesaria |
|---|---|---|
| Rígida | m_i(0), U(0), V_geom | UV; recuperar T/P/fases y verificar restricciones. |
| Presión dada | m_i(0), U(0), P_ext(0) | UP; recuperar T/V/fases. |
| Presión dada | m_i(0), T(0), P_ext(0) | TP cuando determine el estado; en saturación falta una especificación de energía/reparto. |
| Rígida | m_i(0), T(0), V_geom | Inicialización TV con cantidades: minimizar A en el conjunto correspondiente o invertir UV de forma consistente. H3 no publica TV; entregar/verificar esa operación local o diagnosticar que falta soporte. |

Recuento e inicialización son dos partes distintas. Un sistema diferencial cerrado con iniciales faltantes o incompatibles no está listo. Inicializar puede requerir un flash/búsqueda de raíces, pero calcular el recuento no debe integrar ni ejecutar el problema temporal para inferir qué falta. No usar el estado de la última consulta como semilla que imponga propiedades o resuelva una ambigüedad física.

## 4. Corrientes, presión y extracción

El donante depende del signo actual del flujo, no solamente del nombre Entrada/Salida. Una salida constante demostrablemente positiva puede usar el estado del volumen sin un estado exterior ficticio. Una entrada, flujo negativo o ley que pueda invertir necesita un donante exterior declarado. Un cero constante no transporta energía ni exige un donante numérico inventado. En varios componentes, no convertir flujos brutos opuestos en un neto que pierda energía; ese caso queda fuera de E1.

El estado exterior TP describe el estado en el plano de transporte, no automáticamente el de un depósito lejano antes de una válvula/bomba. Su presión es una de estas alternativas explícitas:

- `tipo:dato`: dato de presión propio, con unidad y origen.
- `tipo:continuidad`: relación de presión con el volumen, seleccionada explícitamente. Es una ecuación, no copiar un valor evaluado a un campo.

Si la reducción mecánica exige igualdad de presión en el puerto y el dato no es compatible, diagnosticarlo. No introducir una válvula isentálpica, compresión ni pérdida de carga invisibles para justificar la diferencia. Dato más continuidad crea una restricción adicional: se conserva y se analiza o se rechaza con referencia a ambos.

La temperatura exterior sigue siendo independiente de T del volumen. El coordinador invoca propiedades localmente con el estado correcto del donante en cada evaluación; no hace peticiones HTTP por etapa.

En varias fases, la salida especifica fase o extracción homogénea de la mezcla. Esta es una relación de transporte, no una etiqueta de fase del componente. Extraer líquido necesita composición/entalpía del líquido; no usar la global como si fuera esa fase. Una fase no presente se diagnostica/eventa, no se inventa. La preparación exige una política de extracción cuando se permite multifase, incluso para puertos que podrían invertir; una implementación puede demostrar que una corriente nunca extrae y declarar ese alcance.

## 5. Hipótesis, ecuaciones y recuento

Materia, energía y cierre deben resolver conjuntamente sus restricciones. No aplicar OR entre hipótesis incompatibles, ni convertir una densidad constante declarada en una propiedad de EOS variable. No ignorar un balance desactivado y afirmar que se ejecutó; primera entrega solo admite materia y energía activas, momento desactivado.

El backend devuelve catálogo de variables, ecuaciones con IDs/familias y referencias, recuento y diagnósticos. Diferenciar estados diferenciales, variables algebraicas, datos y parámetros. Concentración de componente m_i/V, densidad global m/V y densidad de fase son variables diferentes. La condición sum(x)=1 no añade otro balance independiente.

`RecuentoDinamico` distingue completo, incompleto, conflicto, redundancia compatible y no evaluable; declara análisis estructural o rango numérico con escala/tolerancia. Números no certificables van como null con motivo. Grados de libertad, datos faltantes e iniciales faltantes no se calculan en frontend mediante una resta universal. Pendientes se refieren a variable/propietario/ruta, incluidos falta de una relación o necesidad de elegir una especificación entre alternativas.

Para E0 publicar relaciones de estado como ecuaciones y soporte parcial antes de resolver. No completar con cifras por omisión una ecuación sin datos. `inicializacion` indica pendiente/compatible/incompatible/no soportada y publica T/P/fases solo cuando existe una inicialización certificada. No contar el diagnóstico de dominio ni la comprobación global de conservación como una ecuación independiente nueva.

## 6. Rutas y respuesta propuestas

Propuesta separada del laboratorio y del servicio puntual:

```
GET  /motor/ensamblajes/capacidades
POST /motor/ensamblajes/validar
POST /motor/ensamblajes/resolver
```

Confirmar nombres y esquema durante E0. Capacidades debe identificar modelos/versiones, número de volúmenes/componentes, formas y balances admitidos, fronteras, inicializaciones, tipos de extracción, expresiones e integradores verificados. `dinamica:false` en la API puntual no se cambia hasta que el modelo tenga soporte dinámico auditado; leer una nueva especificación PH/UV no habilita Resolver por sí solo.

Tipos de respuestas están en `contratoEnsamblajeTermodinamico.ts`. Validar devuelve `recuento`, catálogo/ecuaciones, diagnósticos e inicialización. Resolver incluye la misma validación y estado del cálculo separado. Rechazos no conservan un resultado antiguo; resultados ausentes son null. Publicar método real, tolerancias, referencias y alcance de certificación en la documentación/respuesta acordada de E0.

`modeloId` físico se obtiene del ensamblaje normalizado, unidades equivalentes, modelos/referencias y restricciones activas. Una consulta, títulos del cuaderno y resultados calculados no forman parte de esa identidad física. `solicitudId` identifica la petición para descartar respuestas tardías; no es el modelo. Cambiar balances, componentes, frontera, expresión o cierre invalida la resolución previa.

## 7. Dominio, integración y H4

El coordinador evalúa EOS/flashes dentro del backend, comparte cantidades y energía entre relaciones y usa escalas por magnitud. m puede tener una cota física; U es libre de signo según su referencia. No aplicar universalmente «negativo=agotamiento», una sola tolerancia absoluta ni recorte de fases/cantidades.

Rechazar estado inicial inválido antes de integrar. Durante etapas/iteraciones no reutilizar propiedades de una etapa anterior si falla el flash. Control de pasos, reinicialización y eventos deben distinguir fallo numérico de salida del dominio. Si E1 es monofásico, localizar la entrada a coexistencia y detener o diagnosticar según capacidad; no extrapolar el Cp monofásico dentro de la campana.

H4 usa fases estables y reconstrucción en cada estado necesario. Cambio de fase no añade una fuente de calor latente: las propiedades lo contienen. `sinCambioFase` necesita comprobación de trayectoria, no una fase inicial marcada estable. Trazas, conjuntos activos y aparición/desaparición requieren residuos/tolerancias explícitos. Verificar cada muestra y declarar qué evento vigila desigualdades entre muestras; no afirmar certificación continua por haber visto solo puntos válidos.

## 8. Pruebas de aceptación de la entrega única

1. Petición incompleta: ecuaciones/catalogo/recuento con rutas, sin integración, números inventados ni consulta reutilizada.
2. Un volumen cerrado rígido: calentamiento con masa constante, P variable real, energía y volumen reconstruidos. No validar comparándolo con el `u(T)` afín como si fuera IAPWS.
3. Inicial U y alternativas T compatibles/incompatibles; TP en saturación incompleto; TV sin soporte diagnosticado. Ninguna inicial se fabrica.
4. Volumen abierto: acumulación y desacumulación conservan primera ley; corriente exterior independiente y continuidad explícita de presión. Casos de inversión con donante correcto y fronteras faltantes.
5. Presión constante/suave: equivalencia de U con trabajo y H transformada; derivadas completas de V. Presión discontinua sin modelo de salto rechazada.
6. Restricciones y duplicados: u(T) manual+EOS, V y P adicionales, densidad constante incompatible, políticas de fase discrepantes, bases/unidades; referencias exactas de ambos datos cuando proceda.
7. Métodos/tolerancias, referencias energéticas equivalentes, conservación, residuos, convergencia temporal e identidad normalizada. Las pruebas de intercambio global no sustituyen residuos locales.
8. H4: calentamiento/condensación, fase ausente, trazas, extracción por fase/homogénea y prohibición de cambio; sin doble calor latente.
9. Rechazos/agotamiento/dominio en t=0 y durante trayectoria; resultados parciales certificados sin muestras inválidas ni fallback.
10. Ejemplos desde endpoints y lector TypeScript sobre respuestas reales; regresión backend y `npm run test:motor-fundamental`. Los tests estructurales del frontend no certifican esta física.

## 9. Entrega final para Codex y el usuario

Entregar conjuntamente:

1. Las tres rutas implementadas y su esquema exacto, con revisión, capacidades reales, códigos, rutas por variable y decisiones de compatibilidad con los tipos frontend.
2. Ensamblaje e inicialización de E0, integración rígida de E1, presión prescrita de E2 y tratamiento de fases de E3, con métodos, referencias, derivadas, escalas y eventos documentados.
3. Una única documentación de entrega, por ejemplo `docs/MOTOR_ENSAMBLAJE_DINAMICO.md`, con una tabla de requisitos cumplidos, límites y pendientes reales. Los documentos H0/H1/H3 quedan como referencias de física ya entregada.
4. Peticiones/respuestas generadas desde endpoints: validación incompleta, conflicto, inicialización compatible, calentamiento rígido, llenado/vaciado con energía, presión constante/suave, cambio de fase y extracción. Son pruebas del ensamblador genérico, no escenarios programados dentro del motor.
5. Evidencia de residuos locales/globales, reconstrucción termodinámica, convergencia/refinamiento, eventos y toda la regresión, incluidas las pruebas del lector TypeScript y `npm run test:motor-fundamental`.
6. Lista de archivos modificados, necesidades de recarga y guía de integración: selección de cierre, campos únicos, validar, resolver y resultados. No hacer commit ni push.

Codex conectará la interfaz compacta a esta entrega comprobada. Claude no añade pantallas ni formularios paralelos, no modifica el laboratorio y no sustituye el motor manual que hoy funciona. Durante el desarrollo puede dejar avances documentados, pero el encargo del usuario requiere una sola entrega final de este conjunto.
