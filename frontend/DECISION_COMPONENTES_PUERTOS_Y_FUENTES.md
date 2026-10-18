# Volúmenes, fronteras, conexiones y equipos

Fecha: 12 de octubre de 2026. Destinatario: siguiente revisión de Astra y posterior implementación coordinada con Claude.

**Encargo ejecutable para Claude:** [ENCARGO_CLAUDE_TOPOLOGIA_FRONTERAS_Y_FUENTES.md](./ENCARGO_CLAUDE_TOPOLOGIA_FRONTERAS_Y_FUENTES.md). Este documento conserva el contexto de arquitectura; el alcance backend que debe ejecutar está en ese encargo separado.

## Estado y alcance

**Implementado en esta revisión:** crear un volumen o reactor crea únicamente esa pieza. No crea alimentación, salida ni conexiones. Aplica al botón inicial, a la paleta, al arrastre y a la creación de una copia de volumen. Se quitaron las reservas de tres plazas que acompañaban ese comportamiento. Las mesas guardadas y las plantillas explícitas conservan sus elementos.

**Actualización del editor:** también se entregaron la inserción mediante acción contextual y la conexión de volúmenes sin borrar fronteras. Evidencia y límites en [INTEGRACION_INSERCION_MESA.md](./INTEGRACION_INSERCION_MESA.md). El resto de este documento conserva las decisiones de arquitectura propuestas. No se modificó el motor ni se habilitaron nuevas combinaciones físicas. Referencia de partida: §26 de `docs/ENTREGA_LABORATORIO_CODEX.md`, revisión 14.

Objetivo: poder construir el modelo que el usuario pretende, ver sus intercambios y completar sus datos, sin obligarlo a pensar en la estructura interna del serializador ni llenar el lienzo de detalles.

## 1. Decisión central

La unidad común es un **componente matemático con variables, ecuaciones y puertos**. Un volumen de control es una clase de componente; no todos los componentes necesitan almacenar materia o energía.

| Papel | Qué representa | Ejemplo | Qué no debe inventarse |
|---|---|---|---|
| Dominio con almacenamiento | Región cuyo estado evoluciona mediante balances | Agua del tanque; pared con capacidad térmica | Capacidad, mezcla perfecta, geometría o propiedades sin declarar |
| Frontera | Interacción con una parte del entorno que no se modela internamente | Alimentación; descarga; calor conocido | Un volumen ficticio o la dinámica de la fuente |
| Conexión o relación de intercambio | Transporte entre componentes; puede incluir una ley constitutiva | Corriente compartida; contacto térmico con conductancia | Almacenamiento propio en una línea ideal |
| Equipo | Componente especializado o agrupación de componentes con puertos exteriores | Bomba; calentador; intercambiador | Que su icono determine silenciosamente toda su física |

Una pared sin almacenamiento puede ser algebraica. Una tubería puede ser una conexión ideal, un elemento de pérdida o varios volúmenes discretizados: son diferentes modelos de esa tubería. Agrupar un modelo existente como equipo solo cambia su presentación; añadir almacenamiento o pérdidas cambia sus ecuaciones y exige nuevos datos.

No exigir tres balances ejecutados a cada símbolo: una pared térmica no requiere un balance de especies ficticio; una frontera de calor no requiere inventario propio. Materia, energía y momento se conservan en los dominios correspondientes, con reducciones y aproximaciones explícitas. El motor debe declarar qué familias realmente formula y resuelve.

## 2. Calentar un tanque: elegir cuánto se modela

### A. Se conoce la potencia que recibe el agua

Declarar una aportación exterior `Q(t)` al tanque, por ejemplo 1000 W. La ecuación del tanque incluye `+Q`. No se calcula cómo el calentador produce esa potencia ni qué temperatura tiene.

UI recomendada: seleccionar tanque → Energía → Añadir calor exterior. Un marcador térmico compacto junto al borde indica la aportación; seleccionarlo permite editarla. Debe poder mostrarse como símbolo separado si el usuario quiere organizarlo así.

**El marcador, el campo del panel y el símbolo separado son vistas del mismo objeto con un único identificador.** No crear a la vez una especificación local independiente y otra fuente conectada que sumen dos veces el calor. El cambio de vista no modifica el modelo ni su recuento.

Primera implementación: reutilizar la pieza `calor` y su conexión actuales mediante una proyección visual; no crear un segundo contrato de fuentes. Los valores se asignan en Experimentar; desde el diagrama se define que existe esta interacción y se accede a sus variables.

### B. Se conoce la temperatura del entorno caliente

Declarar una frontera térmica `T_ext` y una relación, por ejemplo `Q = G(T_ext - T_tanque)`. Aquí Q se calcula. No equivale a fijar T del tanque ni a imponer además un Q independiente.

Antes de ofrecer esta opción, verificar que existe una combinación backend que la ensamble. No reinterpretar la actual «T impuesta al volumen» como temperatura exterior. Una nueva frontera térmica requiere contrato, referencias y validación propios.

### C. Se quiere calcular el enfriamiento del circuito caliente

Modelar el fluido caliente como otro dominio con balance de energía y conectarlo térmicamente al agua del tanque. El intercambio aparece con signos opuestos en ambos balances y se cancela en el balance global. Las corrientes de los dos circuitos no se mezclan.

La pared se añade cuando interesa su resistencia o almacenamiento térmico. No exigir siempre tres volúmenes de fluido: agua del tanque y fluido del serpentín son dos dominios materiales; la pared es un dominio sólido si se representa explícitamente. Una resistencia sin almacenamiento no necesita una condición inicial de temperatura propia.

La cámara de vapor disponible es el régimen acotado documentado en §24: no presentarla como un volumen bifásico transitorio general.

### Cambiar de nivel de detalle

Pasar de Q impuesto a un circuito caliente modelado es **sustituir la hipótesis de frontera por otro modelo**, no desplegar una tarjeta. Mostrar la sustitución, retirar la imposición anterior para esa misma interacción, pedir los datos nuevos y volver a validar. Mantener otras fuentes independientes que el usuario haya añadido expresamente.

## 3. La bomba no es simplemente una «fuente de momento»

Una bomba representa conversión de trabajo mecánico en energía del fluido y aumento de presión, con sus pérdidas. Debe tener puertos de fluido, una relación hidráulica y una representación del trabajo; puede incluir almacenamiento si ese nivel de detalle se declara.

Una descripción reducida puede ser algebraica: continuidad, relación entre caudal y salto de presión, balance de energía y relación de potencia o eficiencia. En el caso estacionario e incompresible ideal, la potencia hidráulica es `Δp · caudal_volumétrico`; no usar esa expresión como ley universal de toda máquina. Tampoco identificar presión con cantidad de movimiento ni trabajo de eje con calor.

Una bomba ideal de presión impuesta y una bomba con curva propia son cierres diferentes. No imponer simultáneamente caudal, salto de presión y potencia como datos independientes sin analizar compatibilidad y grados de libertad.

**No implementar una bomba en este encargo.** El balance de momento/hidráulica aún requiere contrato y validación. La pieza de trabajo actual no convierte al motor en un simulador de bombas. El criterio sirve para diseñar la abstracción sin prometer capacidades inexistentes.

## 4. La conexión debe conservar el significado físico

- Una corriente material entre dos sistemas es una sola corriente compartida: salida de uno y entrada del otro. Transporta especies y energía; no duplicar el caudal como dos datos independientes.
- Una interfaz térmica intercambia calor. No transporta masa ni introduce una entalpía advectiva adicional.
- Una fuente exterior aparece en el balance global; un intercambio interior se cancela. Una reacción transforma especies dentro del dominio y no se convierte por ello en una corriente exterior.
- Los puertos tienen identidad semántica estable. Mover el punto sobre el borde o cambiar el trazado ortogonal de la línea no cambia las ecuaciones.
- La flecha define una orientación. Admitir inversión de flujo depende del modelo y de sus leyes; no habilitarla solo porque el editor permite invertir el dibujo.
- Igualar temperaturas a través de un contacto ideal no es lo mismo que conectar dos temperaturas mediante una conductancia finita. El ensamblador debe distinguir la unión de la ley de intercambio.
- Un volumen recién creado es un borrador. No concluir automáticamente que está cerrado o que sus intercambios faltantes valen cero. Cuando el usuario elija un sistema cerrado, registrar esa decisión explícitamente.

## 5. Incidencia concreta al prolongar una cadena

La sustitución automática de `conectar()` eliminaba las salidas terminales del primero y las entradas terminales del segundo, además de sus especificaciones. **Ya se retiró:** conectar conserva las fronteras existentes. Es una corrección distinta de la creación de volúmenes sin extremos automáticos.

Separar dos acciones:

1. **Conectar sistemas:** añadir una corriente compartida sin borrar fronteras ni datos existentes. Si resulta una bifurcación no admitida, conservar el dibujo y señalar la limitación; no corregir la física borrando una rama.
2. **Insertar sistema en una corriente:** acción explícita sobre la línea o arrastre con previsualización. Para `alimentación → V1 → salida`, insertar V2 produce `alimentación → V1 → V2 → salida`. Conserva alimentación, salida y sus datos identificados; añade una corriente interna y un volumen con sus datos pendientes.

La inserción debe ser una sola operación reversible. Antes de implementarla, fijar una tabla de migración de identidades y especificaciones:

- La alimentación exterior conserva su identidad y condiciones declaradas.
- La salida exterior conserva su identidad. Sus datos de caudal se mantienen como especificaciones del destino final y se revalidan; no confundirlos con un dato que pertenecía al antiguo volumen.
- Condiciones ligadas a la antigua conexión, al estado de salida de V1 o a una ley hidráulica no deben trasladarse sin correspondencia explícita. Marcar lo que requiera revisión.
- Los datos y condiciones iniciales de V1 se conservan. V2 requiere los suyos; no copiarlos para aparentar completitud.
- La corriente compartida tiene una identidad única, que aparece en ambos balances y en el catálogo.
- Toda edición invalida la validación vigente y mantiene el resultado anterior únicamente como histórico.

No resolver este problema obligando a borrar y recrear la salida ni agregando un asistente largo. Una acción contextual «Insertar sistema» y una previsualización bastan.

## 6. Ensamblaje y grados de libertad

Cada componente aporta variables, ecuaciones, relaciones constitutivas, condiciones de dominio y puertos al mismo residual `R(t, z, dz/dt, a, p) = 0`. Las conexiones aportan relaciones y términos compartidos. Esta es la arquitectura objetivo; el motor actual admite un conjunto acotado de combinaciones y todavía no es un ensamblador DAE arbitrario.

Para buscar un estacionario, anular las derivadas de los estados que forman parte de ese mismo modelo y aplicar fronteras estacionarias compatibles. No crear balances físicos alternativos para ese estudio. No asumir unicidad, estabilidad ni que todo temporal convergerá a una solución estacionaria.

El recuento del backend sigue siendo la autoridad. Añadir una línea, una fuente o almacenamiento puede cambiar las incógnitas y relaciones necesarias. El frontend no obtiene grados de libertad restando campos visibles ni promete que cualquier combinación dibujable sea resoluble.

La selección Dato/Calcular se ofrece únicamente donde el contrato indique que puede cambiarse el papel de la variable. Un parámetro constitutivo no se convierte automáticamente en incógnita de identificación por dejarlo vacío.

## 7. Orden de implementación propuesto

### Fase 1: edición de topología sin pérdida de datos

Prioridad siguiente. Extraer operaciones puras del editor para conectar e insertar; conservar identidades; deshacer/rehacer atómico; actualizar referencias y limpiar únicamente elementos retirados explícitamente. Añadir regresiones con datos no triviales en las fronteras. No requiere ampliar la física de la cadena ya soportada.

Revisar también el límite local de ocho piezas: actualmente cuenta nodos internos, incluidas corrientes. No elevarlo a ciegas; separar límite del editor, límite del contrato y capacidades por combinación. No presentar el número como una limitación universal del motor.

### Fase 2: una sola edición para las aportaciones exteriores

Proyección compacta de la pieza `calor`, enlazada a su identificador actual. Edición desde el tanque o desde el símbolo; selección resalta su único término en energía. Al apagar energía o declarar adiabático, indicar la contradicción con la fuente existente y permitir resolverla explícitamente; no ocultarla ni borrarla.

Las fuentes, líneas y equipos deben ser distinguibles por forma e icono; el color solo es apoyo. La información detallada aparece al seleccionar. No añadir párrafos permanentes al lienzo ni paneles nuevos abiertos por defecto.

### Fase 3: contrato de componentes y equipos reutilizables

Inventariar primero lo que ya soporta el motor: volúmenes, pared, cámara, corrientes y contactos. Definir roles y puertos comunes como una capa sobre el ensamblaje existente. El esquema definitivo debe acordarse con backend; los nombres conceptuales de este documento no son campos nuevos autorizados a enviar a endpoints.

Agrupar un submodelo debe conservar sus ecuaciones, parámetros, referencias y resultados. Abrir el equipo muestra esos mismos componentes. Introducir una frontera térmica exterior o una bomba requiere entregas físicas independientes; no bloquear las dos primeras fases por ello.

## 8. Criterios de aceptación

1. Crear un volumen, reactor o copia no crea fronteras. Guardar/reabrir no las vuelve a añadir.
2. Conectar V1 y V2 no elimina alimentación ni salida existentes. Una topología no soportada conserva lo dibujado y explica su bloqueo al validar.
3. Insertar V2 antes de una salida conserva el identificador y datos de esa salida, identifica los nuevos pendientes y se deshace en un paso.
4. Tras completar los datos, resolver → insertar → completar → resolver funciona; una respuesta tardía del montaje anterior no sustituye la nueva.
5. Calor desde el panel y calor desde el símbolo editan el mismo objeto. Cambiar solo la representación conserva petición física, recuento y `modelo_id`.
6. En un tanque cerrado de capacidad térmica constante con Q impuesto, la referencia independiente es `T(t)=T0+Q·t/C` dentro de su dominio. En un modelo con capacidades variables se utiliza una referencia apropiada, no esta fórmula por conveniencia.
7. Dos dominios con contacto térmico conservan energía; el intercambio interno se cancela y ambas temperaturas se evalúan en el mismo instante.
8. Fuente exterior más interfaz interior se cuentan una sola vez cada una. La vista de ecuaciones identifica su origen y signos.
9. Una nueva representación no activa física no soportada. La bomba no se ofrece como ejecutable hasta completar su entrega.

## 9. Evidencia y referencias

Verificaciones ejecutadas para el cambio pequeño ya implementado: `npm test`, `npx tsc --noEmit` y ESLint sobre los dos archivos de aplicación modificados. La prueba de contenedores cubre volumen y reactor sin extremos; mantiene las comprobaciones de proyección de corrientes explícitas. La prueba de recorrido de agua se adaptó para crear explícitamente sus fronteras.

La ejecución adicional de `node verificar_recorrido_agua.mjs` alcanzó la llamada HTTP pero no pudo conectarse por EACCES del entorno restringido. La revisión automática de la ejecución con acceso al servicio falló por límite de solicitudes (429); no se ejecutó esa prueba contra el motor en esta revisión. No atribuirle un resultado físico verificado hoy.

Revisión en navegador: mesa nueva vacía → añadir primer volumen → añadir segundo volumen desde la paleta. Aparecen dos volúmenes y ninguna corriente o frontera creada automáticamente. La verificación de arrastre comparte la misma función de creación y fue revisada en código; no se afirma una prueba manual de ese gesto.

Observación de la primera revisión: «Ordenar piezas» superponía parcialmente dos volúmenes aislados. En aquella evidencia se separaron manualmente. **Corregido en la entrega de inserción:** el ordenamiento considera la altura declarada y la separación habitual de los volúmenes. Evidencia histórica: `preview-volumenes-sin-fronteras.jpg`.

Referencias de diseño consultadas, como precedentes y no como requisito de adoptar Modelica:

- [Modelica: fuentes térmicas](https://doc.modelica.org/om/Modelica.Thermal.HeatTransfer.Sources.html): distingue fronteras de temperatura y de flujo de calor.
- [Modelica: bomba con conexión mecánica](https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Fluid.Machines.Pump.html): combina puertos de fluido y de eje, relaciones de máquina y opciones de dinámica de masa y energía.

Estas referencias respaldan separar funciones físicas. La UI compacta, la inserción de sistemas y el plan incremental son propuestas específicas para este proyecto.
