# Edición y resolución de redes · 16 de octubre de 2026

## Cambios

- Deshacer y Rehacer en las vistas de ecuaciones, estado y resolución del ensamblaje v2.
- Se recuperan configuración, componentes locales, conexiones, datos y unidades. Retirar un volumen y deshacer recupera también sus conexiones y declaraciones.
- Las pulsaciones consecutivas en un mismo campo forman una edición; cambiar de foco termina el grupo.
- Historial de hasta 30 cambios por hoja, conservado al navegar entre esas vistas durante la sesión. Recargar la página lo reinicia. No se guardan trayectorias en el historial.
- Deshacer una edición física exige volver a resolver; no restaura una referencia antigua de resultados.
- Los IDs de componentes, volúmenes, corrientes y contactos térmicos retirados quedan reservados, incluso al deshacer y crear una rama nueva. Los contadores son metadatos locales, fuera de la solicitud física.
- El paquete compartido por dos volúmenes deja de ser un alias editable: cambiar el modelo de uno crea una referencia propia y conserva el modelo del otro.
- Un volumen nuevo conserva la base másica/molar y la elección de inicialización T/U del volumen del que se parte. Cantidades, energía y geometría/presión nuevas quedan pendientes. No se crean corrientes automáticamente.
- Editar, deshacer, salir de la pantalla o cancelar aborta la espera de la resolución. Una respuesta anterior no puede publicar resultados ni retirar el indicador de una petición posterior.
- El guardado en IndexedDB admite cancelación antes de confirmar la transacción. Los errores de clonación también abortan y cierran el almacenamiento.
- El estado de cálculo se vincula a la firma física: una configuración distinta no queda bloqueada por el indicador de la anterior.

Cancelar la petición HTTP no garantiza detener el cálculo Python que ya esté ejecutándose. Una transacción de IndexedDB ya confirmada tampoco puede revertirse; se comprueba de nuevo la firma y la operación vigente antes de publicar su referencia o navegar.

## Verificación

| Comprobación | Resultado |
|---|---|
| `npm run test:motor-fundamental` | Pasa, incluido el nuevo verificador de edición |
| `npm run test:edicion-red` | 70 comprobaciones deterministas |
| `node verificar_edicion_y_operaciones_red.mjs --servicio` | 89 comprobaciones, incluidas las anteriores |
| `node verificar_edicion_y_operaciones_red.mjs --ui` | 74 comprobaciones, incluida la ejecución original exportada del navegador |
| TypeScript y ESLint de los archivos modificados | Pasan |
| Paquete independiente, quitar/deshacer/rehacer un volumen, identidad nueva tras borrar | Comprobados en navegador durante esta sesión de trabajo |

La prueba del servicio parte de la solicitud real exportada de la copia de QA `a1e138bf-512b-4d24-9881-e3c1c7b361fb`: cuatro especies en el catálogo global, dos por volumen, un contacto térmico. Añade un volumen sin inventar sus valores, comprueba que el recuento queda incompleto, deshace y vuelve a validar/resolver.

El sistema restaurado queda `listo` y devuelve `resuelto` con certificación `cumple`. Las temperaturas reproducen exactamente la trayectoria anterior, las cantidades se conservan y el intercambio interno se cancela en la entalpía total. El volumen retirado no aparece en los estados evaluados.

Evidencias HTTP: `frontend/qa_edicion_red_2026_10_16/`:

- `volumen-nuevo-pendiente.json`
- `restaurado-validar.json`
- `restaurado-resolver.json`
- `ejecucion-ui.json`: solicitud y respuesta originales del navegador después de agregar un volumen, navegar a Resolver y deshacer.
- `resultados-restaurados.png`: captura de resultados con certificación `cumple`.

Comprobación visual cerrada después de que el usuario recargase el navegador: el volumen nuevo dejó cuatro datos pendientes, Resolver deshabilitado y campos vacíos con sus unidades. Deshacer recuperó los dos volúmenes, los datos y GL = 0; Resolver publicó la trayectoria con certificación `cumple`. También se comprobó la secuencia 2 → 20 → Deshacer (2) → Rehacer (20) → Deshacer (2) para el tiempo final. El lector acepta la respuesta sin modificaciones y todas las series coinciden exactamente con la ejecución anterior. Las solicitudes coinciden salvo por el identificador de petición.

Estas pruebas no certifican nuevos flashes de N componentes ni sustituyen los contrastes físicos de Claude.

Incidencia observada al reconectar: la primera carga mostró `Failed to fetch`; Reintentar recuperó las capacidades y permitió completar el recorrido. En el log del servicio había un `KeyError: 'ChemSep NRTL'` en `_pares_nrtl`, al consultar `IPDB.metadata`. No se cambió el backend ni se atribuye todavía una causa; conviene que Claude revise la inicialización de los parámetros y su posible concurrencia en un arranque en frío.

## Archivos

Nuevos: `app/motor/topologiaRed.ts`, `historialEdicionRed.ts`, `operacionRed.ts`, `verificar_edicion_y_operaciones_red.mjs`, este informe y las evidencias.

Integración: `EspacioRedTermodinamica.tsx`, `EditorComponentesRed.tsx`, `redTermodinamica.ts`, `resultadosMotor.ts`, `trabajoMotor.module.css` y `package.json`. El verificador nuevo forma parte de `test:motor-fundamental` y tiene el acceso directo `test:edicion-red`.

Backend, núcleo físico, `/laboratorio` y `thermodynamics/proveedor.py` sin editar. Se iniciaron los servidores locales después del reinicio del equipo. Sin commit ni push.
