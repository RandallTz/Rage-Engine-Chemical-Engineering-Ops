# Prioridad: firma estable tras un roundtrip JSON en JavaScript

## Estado actual · resuelta
Corrección de Claude en §17.11 verificada por Codex el 2026-10-09 contra el servicio local reiniciado. Estados nuevos obtenidos por /transferir, serializados con JavaScript y enviados a /validar y /resolver: energía, escalón, reacción y rama encendida terminan resueltos. Las advertencias de contraste se conservan. Los objetos anteriores requieren volver a solicitar /transferir; el cliente no modifica firmas. La reproducción histórica de abajo queda como registro, no como tarea pendiente.

## Estado histórico
Frontend de §17 conectado: solicita /transferir, permite elegir rama y lleva condicion_inicial sin conversiones a estudio.condicion_inicial_transferida; retira iniciales manuales y exige revalidar. NO recalcula firmas. La integración real está bloqueada por esta incidencia del backend. No ampliar otras físicas antes de corregirla. Solo backend; sin editar frontend, cambios ajenos, commit ni publicación.

## Reproducción comprobada contra el servicio local
1. Leer como texto docs/ejemplos/estudio-transferencia-energia-temporal-peticion.json y enviarlo a POST /laboratorio/estudios/validar: estado valido.
2. Hacer JSON.stringify(JSON.parse(texto)) y enviar exactamente el mismo contenido semántico: estado invalido, LAB_DIN_TRANSFERENCIA_ALTERADA.
3. También sucede solicitando un estado NUEVO por /transferir y mandándolo directamente desde JavaScript al temporal: no es un problema de ejemplos antiguos.

Ejemplo visible: la respuesta contiene valor: 3887500.0; JavaScript lo vuelve a serializar como valor: 3887500. No hubo edición ni conversión física. La firma utiliza backend/nucleo_estudios.py firma(objeto), delegada a trazabilidad.huella. Revisar allí la canonicalización numérica. Los inventarios y temperaturas mantienen sus valores, pero JSON no garantiza conservar el tipo Python int/float ni la escritura original del número.

## Corrección requerida
El servidor debe firmar una representación numérica canónica compatible con el roundtrip JSON de un navegador. Resolver de manera consistente int/float equivalentes, exponentes y cero negativo. No redondear tolerancias, truncar precisión, ignorar valores ni relajar la detección de alteraciones. No pedir al frontend conservar lexemas JSON, convertir números a strings o recalcular la firma. Si cambia la firma, documentar migración/regeneración de objetos anteriores. Conservar controles de huellas, restricciones y vigencia del estacionario: la firma sigue siendo integridad, no autenticación.

## Aceptación
- Solicitud nueva /transferir → JSON.parse → JSON.stringify → /validar y /resolver, usando JavaScript real (Node vale), para energía, reacción y ambas ramas.
- El mismo objeto sobrevive persistencia/importación JSON del navegador.
- Cambio de inventario/U/origen detectado; estado alterado y re-firmado sigue rechazado como obsoleto.
- Cambio de modelo, sustancias, cierre, referencia o especificación base conserva diagnóstico por elemento.
- Mantener las 26 suites y añadir esta prueba entre lenguajes; generar ejemplos nuevos con la firma corregida.

## Lo que Codex ya verificó
Los seis pares de contrato son admitidos. El helper conserva por referencia el objeto recibido, no cambia su JSON ni la petición origen, no duplica iniciales, no convierte F/h a n/U. Temporal importado con escalones sin forma explícita se acepta estructuralmente (el backend da su valor por omisión). UI muestra los estados transferidos en lectura y bloquea resolver hasta validar. El fallo es reproducible fuera de React, con fetch de Node.
