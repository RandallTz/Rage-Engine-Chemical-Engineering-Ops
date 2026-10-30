# Inicio del nuevo chat de Claude

> Estado actualizado: primera tarea material implementada por Claude y conectada en frontend. No repetirla. Ver docs/ENTREGA_LABORATORIO_CODEX.md §13 e INTEGRACION_ESTUDIOS_ACOPLADOS.md. El resto de este documento conserva el alcance de la entrega inicial.

Trabaja SOLO en backend. No edites frontend ni despliegues. No necesitas el historial del chat: lee esta entrega y los archivos pertinentes. Inspecciona primero el estado de Git y respeta cambios ajenos.

## Estado real

El backend ya tiene laboratorio térmico estacionario y servicios reactivos (balanceo exacto, Hess/Kirchhoff, cinética, equilibrio y lote). Verifica su estado en docs/ENTREGA_LABORATORIO_CODEX.md; no supongas que todos los pendientes anteriores siguen vigentes. El frontend tiene una mesa con corrientes compartidas, balances explicativos, respuesta trazable y selector estacionario/temporal. La preparación temporal local guarda n total, T, V e intervalo: NO es una solicitud ejecutable ni una definición completa de condiciones iniciales.

## Primera tarea acotada

Ensamblar y resolver un modelo material dinámico de DOS volúmenes perfectamente mezclados conectados, sin reacción inicialmente, con cierres físicos explícitos. Usar el mismo montaje para estacionario y temporal. Validar contra referencia analítica independiente (incluye caso de constantes de tiempo iguales y desiguales), conservación global e inventarios por especie. No ejecutar cada pieza por separado pasando resultados finales. No añadir CFD, malla ni operaciones complejas.

## Lectura mínima y autoridad

1. CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md: contrato propuesto, detalles y criterios; la actualización final exige dos volúmenes desde la primera aceptación.
2. docs/ENTREGA_LABORATORIO_CODEX.md: implementación real actual y limitaciones.
3. Backend del laboratorio y tests/validar_laboratorio.py: descubre rutas, modelos y convenciones antes de editar.
4. PENDIENTES_BACKEND_CLAUDE.md solo como inventario para contrastar; no implementar todos sus históricos en esta entrega.

Las rutas nuevas son propuestas, no existentes. Acordar estructura de request/response en documentación ejecutable y generar pares de ejemplo reales. Identificar cambios incompatibles y capacidad temporal explícita para que Codex conecte el frontend después.

## Arquitectura requerida

Cada pieza aporta variables, balances y cierres; cada conexión une estados/transporte. Ensamblaje común con IDs estables, clasificación de variables diferenciales/algebraicas, ecuaciones independientes y restricciones. Contar ecuaciones no certifica rango ni consistencia. Resolver ODE reducida cuando sea justificable; si hay DAE no soportada, diagnóstico específico. Declarar método realmente utilizado, tolerancias, dominio, condiciones iniciales utilizadas, eventos, conservación y residuo. Un estacionario no implica estabilidad; neto químico cero no implica reacción detenida. La corriente sin almacenamiento no añade inventarios ni igualdades duplicadas.

## Siguiente entrega, no mezclar con la primera

Almacenamiento térmico y energía acoplada; asociación de definiciones reactivas multicomponente por volumen; transferencia validada de estacionario a condición inicial; perfiles temporales. Momento requiere antes fuerzas, geometría y cierres. Mantener el lote independiente como régimen propio.

## Qué devolver a Codex

Contrato versionado, capacidades, ejemplos ejecutados, pruebas analíticas, limitaciones ODE/DAE y migración. No interpretar LaTeX recibido: el motor genera las ecuaciones a partir del modelo. Dejar docs/ENTREGA_LABORATORIO_CODEX.md actualizado con endpoints y esquema precisos. No habilitar capacidad no probada.
