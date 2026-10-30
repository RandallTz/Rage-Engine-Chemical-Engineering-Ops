# Entrega siguiente para Claude: almacenamiento energético y fuentes reactivas

Trabaja solo en backend. No edites frontend ni despliegues. Este documento sustituye la primera tarea de INICIO_CLAUDE_MOTOR_ACOPLADO.md: esa tarea material YA está implementada y conectada. Inspecciona Git y no incluyas modificaciones ajenas en un commit.

## Estado actualizado

Entrega A implementada en backend y conectada al frontend, con energía habilitada por capacidades. La siguiente tarea es exclusivamente la entrega B. No repetir A ni alterar sus contratos material/energético existentes. Ver docs/ENTREGA_LABORATORIO_CODEX.md §14 además de §13.

## Lectura mínima

1. docs/ENTREGA_LABORATORIO_CODEX.md §13: contrato real de estudios y límites ODE/DAE.
2. backend/nucleo_estudios.py, backend/schemas_estudios.py y core/dinamica.py: inspeccionar responsabilidades actuales antes de decidir dónde ampliar.
3. tests/validar_estudios.py: conservar referencias analíticas independientes y contrato material.
4. INTEGRACION_ESTUDIOS_ACOPLADOS.md: estado del frontend. No necesitas el historial del chat.

## Entrega A: materia + energía, sin reacción

Dos volúmenes perfectamente mezclados conectados. La corriente intermedia tiene un estado compartido, sin almacenamiento propio. Un mismo montaje para temporal y estacionario; ensamblar balances y cierres, clasificar y resolver conjuntamente. No integrar energía aparte usando composiciones finales ni propagar estados finales bloque por bloque.

Variables de almacenamiento: n_i y energía interna total U (o una parametrización térmica equivalente cuya transformación sea declarada). Cierre termodinámico U=U(n_i,T,V) compatible con los modelos del proveedor y con la geometría. T no es automáticamente variable diferencial: puede ser algebraica determinada por este cierre. h de transporte incluye trabajo de flujo; no confundir h con u, energía molar con total, potencia con energía, ni caudal con inventario.

Balances de materia: dn_i/dt = flujos entrantes - salientes. Energía: dE_CV/dt = Q-Ws+sum(F h)_in-sum(F h)_out, bajo cambios cinéticos/potenciales despreciables y geometría fija apropiada. Si se permite frontera móvil, especificar explícitamente trabajo de frontera y convenciones sin duplicar trabajo de flujo. No ampliar esa geometría en la primera entrega si no está cerrada.

Cada volumen declara cierre de almacenamiento/salida y modelo de almacenamiento energético; ningún valor de densidad o capacidad térmica por omisión silenciosa. La base material admite densidad constante declarada: no sustituirla por densidad dependiente de T/x y seguir anunciando la misma reducción DAE. Cualquier combinación nueva requiere análisis y consistencia. Rechazar DAE no soportada con código específico.

Primera referencia: mezcla monofásica ideal/incompresible con rho y capacidad constantes DECLARADAS, elegida como caso de prueba, no impuesta al proveedor real. Después ampliar propiedades variables compatibles con un dominio monofásico explícito. Asegurar que U y h son coherentes con el mismo origen de energía y las hipótesis de presión/volumen. Si un proveedor no permite cerrar U, diagnosticarlo; no aproximar silenciosamente U por h.

Intercambios: Q impuesto constante/escalón, temperatura de alimentación constante/escalón. T de un volumen impuesta define otro estudio/control y puede excluir una ecuación dinámica o determinar Q: detectar sobreespecificación, no imponer T y Q a la vez. Adiabático significa Q=0, no ausencia de ecuación de energía. Trabajo de eje permanece no soportado hasta contar con definición física suficiente.

## Petición/respuesta: ampliar con versión y capacidad explícitas

Proponer el esquema exacto tras revisar el contrato vigente, sin romper solicitudes materiales. Almacenamiento pertenece a la definición física; estados iniciales por especie y U o T pertenecen al estudio. Si se aceptan U y T iniciales simultáneamente, verificar consistencia o declarar exclusión. Capacidades deben indicar físicas, cierres, pares de especificaciones, dominio de fase y transferencias disponibles.

Respuesta: variables y ecuaciones con IDs/clase/unidad/origen, clasificación y razonamiento de reducción, método REAL, tolerancias por escala, condiciones iniciales utilizadas, eventos y dominio. Series n_i, U, T, propiedades necesarias y Q, en unidades declaradas. Residuos de energía locales/globales integrados e instantáneos, invariantes de almacenamiento y terminación completa/parcial/fallida. La cancelación de transporte energético interno debe medirse, no asumirse. La energía total no es una suma de temperaturas.

Detectar agotamiento, imposibilidad de invertir U(T), salida de dominio y frontera de fase. No continuar con una interpolación monofásica fuera de su dominio; declarar evento o física de fase realmente soportada. Estabilidad lineal LOCAL del modelo acoplado, con restricciones consideradas. Rango estructural no equivale a rango numérico verificado.

## Aceptación A

- Un volumen ideal: perturbación de T de entrada y Q, solución analítica térmica y material independiente.
- Dos volúmenes: constantes de tiempo iguales y distintas, con referencia analítica externa; ambos inventarios térmicos avanzan conjuntamente.
- Temporal y estacionario del mismo montaje, mismo modelo_id, ecuaciones y fuentes compatibles; Newton/no lineal debe declarar método realmente utilizado.
- Adiabático y sin perturbación: estado inicial estacionario permanece constante dentro de tolerancias.
- Propiedades variables: comprobación independiente de propiedades y conservación; no vender conservación como prueba de precisión.
- Restricciones e iniciales inconsistentes, energía/temperatura sobreespecificada, cierres faltantes y cambios de fase fuera de alcance: diagnósticos con IDs.
- Mantener las 22 suites actuales; nuevos ejemplos petición/respuesta generados ejecutando endpoints.

## Entrega B: fuentes reactivas sobre la misma base

Solo después de A. Asociar a cada volumen definiciones reactivas multicomponente reutilizando balanceo, identidades, tasas y termodinámica existentes. Fuentes de materia sum(nu_i,r r_r) evaluadas con el estado del MISMO instante y volumen. No reconstruir un motor cinético diferente ni duplicar datos del proveedor. Preservar generación y consumo brutos: con solo neto no inventarlos; equilibrio dinámico no significa reacción detenida.

Cerrar energía con referencias de formación y transporte compatibles. Si U/h incluyen energía química, no sumar otra vez un calor de reacción completo. Si se adopta energía sensible con fuente química explícita, documentar transformación y referencias. Hess/Kirchhoff y tasas deben coincidir con el módulo reactivo existente. Composición/T afectan cinética y energía simultáneamente; no resolver primero una conversión y luego una T sin justificación del algoritmo acoplado.

Aceptación B: reacción isotérmica validada contra el motor existente, exotérmica adiabática con conservación elemental/masa/energía y contraste independiente, reacción reversible consistente con equilibrio, dos volúmenes reactivos con fuente propia y transporte compartido. Dominio, positividad, rigidez y eventual falta de estacionario estable se diagnostican.

## Transferencia estacionario → temporal

No habilitar en frontend ni en capacidades hasta implementarla. Generar candidato de condiciones iniciales desde inventarios/energía realmente resueltos, verificar cierres y consistencia, registrar cálculo/versión origen. No copiar F a n ni h a U. Mantener el contraste temporal → estacionario independiente del criterio de integración completada.

## Alcance y devolución a Codex

Sin CFD, mallado ni operaciones complejas. Momento sigue pendiente de fuerzas, áreas y cierres. Entregar A antes de B como hitos verificables; si B no queda implementada, capacidades y documentación deben decirlo. Actualizar docs/ENTREGA_LABORATORIO_CODEX.md con esquema exacto, migración, ejemplos, códigos y limitaciones. No interpretar LaTeX enviado. El frontend añadirá campos solo después de este contrato, no simulará energía localmente.
