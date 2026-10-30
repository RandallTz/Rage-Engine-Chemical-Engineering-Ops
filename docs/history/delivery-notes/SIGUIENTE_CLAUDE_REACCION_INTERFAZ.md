# Estado: entregado por Claude en §18

Integrado en frontend: habilitación por combinación y tipo de estudio; correcciones de redondeo visibles sin cambiar el objeto; parcial antes de muestras sin gráfica ficticia. Este documento queda como registro de aceptación, no como tarea nueva. La cola de transferencia de materia, momento, frontera móvil, fase y control sigue separada.

# Siguiente entrega: reacción + interfaz térmica

## Contexto y alcance
Solo backend. No modificar frontend, cambios ajenos, publicar ni hacer commit. Revisar Git: thermodynamics/proveedor.py es un cambio ajeno. Leer docs/ENTREGA_LABORATORIO_CODEX.md §§15–17.11. La transferencia y su firma compatible con JavaScript están entregadas: no repetirlas.

La combinación reacción + interfaz térmica sigue rechazada. Habilitarla únicamente tras verificarla sobre el mismo ensamblaje acoplado de materia y energía. No construir otro motor cinético ni otro integrador; reutilizar las leyes, propiedades y términos existentes. No ampliar a momento, transferencia de materia, frontera móvil, cambio de fase o control en esta entrega.

## Comportamiento requerido
- Evaluar composición, temperatura, tasas y Q12 = G(T1 − T2) al mismo instante para los dos volúmenes.
- Mantener generación y consumo brutos separados del neto, y la referencia sensible con fuente química explícita. Evitar doble conteo de calor químico.
- La interfaz resta en el volumen origen y suma en el destino; no tiene inventario propio. Adiabático sigue significando sin calor exterior.
- Ensamblar LaTeX y verificaciones globales desde terminos[], incluyendo cancelaciones internas, procedencia y residuo_terminos. No escribir una fórmula global paralela a mano.
- Mantener rechazo explícito de dominios, fases y topologías no soportadas. Ninguna aproximación silenciosa.
- Declarar método real, restricciones, arranques, estabilidad local, eventos y límites de búsqueda de ramas. No prometer exhaustividad.
- Actualizar capacidades.combinaciones para el montaje efectivamente comprobado. Permitir transferencia estacionario → temporal solo si se validan todas las restricciones de esta combinación.

## Validación independiente
1. G = 0 recupera la solución reactiva existente; reacción desactivada recupera interfaz térmica existente.
2. Invertir orientación y signo conserva la evolución física.
3. Una formulación independiente verifica energía química, sensible e intercambio sin doble conteo.
4. Conservación global cancela la interfaz; conserva elementos y masa aun si cambian los moles.
5. Un caso térmicamente rígido comprueba integradores apropiados, eventos y tolerancias.
6. Estado estacionario transferido permanece sin perturbación; un escalón produce trayectoria consistente. Probar JSON.parse/stringify con Node real.
7. Verificar brutas positivas con neto cero cuando corresponda, agotamiento, límites térmicos y rechazos por pieza/conexión.

## Entrega para Codex
Actualizar la entrega principal con esquema exacto, migración, campos añadidos y capacidades por combinación. Generar pares petición/respuesta ejecutando endpoints. Conservar suites actuales y añadir referencias independientes. Explicar diferencias de resultados y limitaciones. El frontend leerá términos y capacidades del servidor: no mover resolución física al cliente.
