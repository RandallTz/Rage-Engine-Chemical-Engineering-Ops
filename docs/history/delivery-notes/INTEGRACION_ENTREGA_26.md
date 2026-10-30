# Integración de §26 · revisión 14

11 de octubre de 2026. Frontend integrado con el contrato de `docs/ENTREGA_LABORATORIO_CODEX.md` §26. No se cambió el motor, no hay commit ni push.

## Experiencia

- En Experimentar, «Al resolver, mostrar: Moles / Masa» declara la presentación del siguiente resultado. No cambia ningún dato existente ni convierte números en el cliente. La presentación en masa añade las variables que devuelve el servidor a gráficas y tablas; las gráficas personalizadas siguen pudiendo usar ambas bases.
- Cada cantidad inicial y cada caudal editable admitido puede darse en moles o masa. En un campo vacío se elige la base; en uno lleno se conserva la base y la unidad declaradas. Para cambiar de base se vacía el campo y se introduce un nuevo dato. No se interpreta 50 mol como 50 kg.
- Las peticiones importadas con `m` o `m_dot` muestran su valor y unidad originales. El balance general muestra una sola fila por variable física, conserva Dato/Calcular y utiliza la elegibilidad de su variable canónica. El alias no es otra incógnita. `F_salida` sigue siendo molar.
- El análisis dimensional real del servidor aparece mediante un botón, apagado por defecto, en la vista de ecuaciones y en las ecuaciones del resultado. Muestra estado, unidades de los términos y motivo cuando no se evaluó. Las respuestas anteriores conservan una leyenda de unidades sin fingir análisis dimensional.
- El modelo parcial se muestra como «Modelo formulado · datos pendientes». No se marca como ejecutado ni habilita Resolver: decide `recuento.puede_resolver`.
- Conversión por CAS, masas molares y dominio de la trayectoria se consultan en Detalles técnicos. Los nombres de las variables másicas identifican especie y sistema.

## Límites conservados

El ensamblaje y sus ecuaciones fundamentales se muestran tal como los entrega el servidor, en su base interna molar, junto con las relaciones de conversión publicadas. No se reescribe un balance molar como másico manipulando LaTeX. La entrada de fracciones másicas, el caudal másico con composición desconocida y la selección libre de variables térmicas siguen fuera del contrato ejecutable. Unidades, conversiones físicas y grados de libertad pertenecen al backend.

## Verificación

- `npm test`, TypeScript y ESLint de los archivos cambiados.
- `verificar_entrega_26.mjs`: 105 respuestas de estudios, 1.478 análisis dimensionales, edición en masa sin duplicación molar, referencias a campos canónicos, nombres de especies, modelos parciales y rechazo de estructuras dimensionales inválidas.
- `node verificar_entrega_26.mjs --api`: tanque real en kg/kg/h; presentación másica y molar con mismo modelo, indicador de recuento y series molares; variables adicionales en kg; modelo parcial real desde `/validar`.
- Navegador: mesa separada «UI · masa y dimensiones · entrega 26». Importar, resolver, activar análisis dimensional, retirar una condición inicial, visualizar el modelo parcial y restaurar el dato en kg. `test1` no se modificó.

## Observación para el seguimiento de backend

Con la misma petición del tanque, al cambiar solo `base_materia.presentacion`, el indicador y los grados de libertad son idénticos. Sin embargo, el desglose másico añade `derivadas_de_restriccion: {total: 3, cuentan: 0}` para las tres relaciones de base. No afecta al cierre ni al resultado. Sería más preciso identificarlas como relaciones de base auxiliares en el desglose. No se modificó ese diagnóstico desde el frontend.

Las ampliaciones propuestas en §26.3 siguen pendientes; esta integración no las declara implementadas.
