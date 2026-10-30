# Próxima integración con el backend — propuesta para Claude

Los cambios de interfaz no requieren modificar el solver. Para avanzar hacia trazabilidad reproducible y diagnósticos físicos fiables, la siguiente etapa sí necesita información del backend.

Ampliar la respuesta de `/diagrama/resolver` con campos opcionales, conservando el contrato actual:

- `calculo`: identificador, fecha UTC del servidor, versión o commit del motor, identificador y versión del proveedor termodinámico, e identificador determinista de las entradas físicas normalizadas.
- `diagnosticos`: código estable, severidad, identificador de equipo, claves de variables implicadas, mensaje y estado del bloque. Separar falta de especificación, redundancia, incompatibilidad física y fallo numérico; no deducir estas categorías solo del texto.
- `convergencia`: por bloque, método, estado, iteraciones, tolerancias, norma y unidades/escala de los residuos cuando el algoritmo realmente los evalúa. No fabricar residuos para construcciones gráficas o correlaciones.
- Opcional posterior: catálogo versionado de ecuaciones y supuestos por operación/método/opciones para sustituir documentación duplicada en el frontend.

Definir las unidades (SI), la normalización y qué resultados son parciales antes de integrar. La interfaz podrá ocultar campos ausentes durante la migración. No etiquetar un resultado como físicamente validado solo por `completo=true`.

Prueba de integración que conviene revisar: bomba ideal con `s1.P=101325 Pa`, `factor_P=3` y `s2.P=100000 Pa` fijados. Durante esta revisión el servicio respondió completo sin una incidencia y conservó la presión de salida fijada. Revisar si el orquestador omite el cierre al estar dados ambos extremos y hacer explícita esa política, o detectar su incompatibilidad cuando las tres condiciones deban cumplirse. El frontend no ha alterado esa lógica.

El reporte actual registra la fecha local de la interfaz y documenta el modelo; todavía no certifica versiones del motor ni residuos de ejecución.
