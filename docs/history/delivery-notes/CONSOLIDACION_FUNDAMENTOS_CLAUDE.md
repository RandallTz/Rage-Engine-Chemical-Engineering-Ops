# Consolidar fundamentos antes de ampliar operaciones

## Dirección

El laboratorio debe componer conservación, propiedades, transformaciones y cierres. No ampliar todavía columnas, intercambiadores, bombas, CFD ni mallado. La existencia de una pantalla no prueba que un modelo sea validado o reutilizable.

## Ya preparado en frontend

- Biblioteca independiente /laboratorio/fundamentos con dependencias, convenciones y límites. Separa servicios disponibles de consulta pendiente.
- Sistema reactivo → condiciones → resultados. Lote/equilibrio comparten el borrador: especies, coeficientes, inventarios, temperatura y leyes.
- Equilibrio envía solo estequiometría; conserva las leyes en el borrador para volver a lote. Inventarios son mol y nunca se obtienen convirtiendo caudales sin tiempo/base.
- El editor general envía la misma red a equilibrio o a la configuración estacionaria. Inicializar inventarios en cero obliga a especificarlos; 400 K es una propuesta visible, no un estado validado.
- Datos modificados invalidan resultados. Recuperar cuadernos restaura parámetros y exige recalcular; la ejecución histórica se conserva.
- Fórmulas explicativas no son instrucciones ejecutables. Métodos, propiedades, estabilidad y residuos proceden del backend.

## Auditoría requerida en motor: antes de pedir funciones nuevas

Documentar y comprobar si laboratorio y módulos existentes comparten las implementaciones de identidad/capacidades de sustancias, propiedades y referencias, estequiometría, leyes cinéticas, fuentes brutas/netas y conservación. Reutilizar implementaciones existentes; no asumir que endpoints parecidos tienen una base común. Mantener adaptadores separados para cantidad [mol] y caudal [mol/s].

Una definición reutilizable de sistema debe conservar IDs estables de especies y reacciones, coeficientes, leyes/base/unidades y referencias; cada problema añade régimen, condiciones iniciales/frontera y especificaciones. No convertir una definición en un resultado ni transferir indiscriminadamente inventarios a caudales.

## Entrega de consolidación propuesta

1. Capacidad declarada por régimen: restricciones de fase, sustancias, base, referencias y métodos. El frontend no debe inferir soporte desde una ecuación de consulta.
2. Si falta en los servicios independientes, exponer trazabilidad del sistema: variables, ecuaciones independientes, especificaciones, origen por reacción y condiciones; LaTeX generado desde el modelo. No sustituir esta traza por un sistema construido en frontend.
3. Versionar definición y resultados; detectar cambios incompatibles o de referencia, conservando ejecuciones originales. No afirmar equivalencia entre resultados de distintas versiones automáticamente.
4. Casos cruzados sobre la misma definición: cinética consistente que llega a equilibrio, caso inconsistente que no llega, conservación exacta y residuos energéticos; errores con IDs locales útiles.

No repetir balanceo, lote isotérmico, equilibrio o Hess/Kirchhoff ya entregados. Estas solicitudes son transversales y deben concretarse tras revisar qué existe.

## Fundamentos siguientes, por entregas pequeñas

### Energía, segunda ley y exergía

Ampliar balances de entropía y exergía física, temperatura de frontera y ambiente T0,p0; propiedades con referencias compatibles. No confundir la entropía estándar de reacción ya disponible con un balance de entropía del sistema. Lote adiabático requiere un problema dinámico energético acoplado; no es el estacionario adiabático ya resuelto.

### Transporte de calor

Primero resistencias en capas planas/contactos, conducción estacionaria 1D y luego capacidad concentrada transitoria. Definir signos, áreas, unidades, propiedades y condiciones de frontera. Validar con soluciones analíticas y conservación. No mallado ni geometrías arbitrarias.

### Transporte de materia

Difusión binaria y película/interfase con bases de flujo explícitas, propiedades y equilibrio compatible. Distinguir flujo total y difusivo, y casos equimolares frente a especie estancada. Acoplamiento con reacción solo cuando ambas bases estén definidas.

### Momento

Balance integral, leyes constitutivas y pérdidas en dominios definidos. Correlaciones con rangos, presión absoluta/manométrica y unidades explícitas. No priorizar máquinas ni CFD.

## Criterio de terminado por fundamento

Contrato y límites → prueba independiente → diagnóstico de casos no soportados → traza de ecuaciones/método → composición con otra pieza sin copiar física. Registrar cada estado con evidencia, no un único indicador de “terminado”.
