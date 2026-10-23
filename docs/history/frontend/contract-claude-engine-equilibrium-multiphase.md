# Entrega para Claude: equilibrio multifásico integrado en el motor

**Estado histórico:** entrega M0–M6 recibida e integrada dentro del alcance publicado. Los límites de fases, datos y operaciones permanecen en sus informes. El [roadmap principal](../../engine/multiphysics-roadmap.md) determina la continuidad; no repetir este encargo ni tratar su frase “siguiente trabajo” como una nueva prioridad.

15 de octubre de 2026. Encargo autorizado por el usuario: ampliar los fundamentos y el ensamblaje del motor independiente, incluyendo mezclas, equilibrio y sistemas acoplados. Este documento es el encargo vigente para el siguiente trabajo de backend. Los contratos H0/H1, H3 y E0–E3 describen entregas ya realizadas; no se encarga repetirlas.

Claude conserva backend, propiedades, equilibrio, integración numérica y pruebas físicas. Codex conserva frontend, adaptación de hojas, lectores y experiencia de `/motor`. No modificar `/laboratorio`, el frontend ni el cambio ajeno de `thermodynamics/proveedor.py`. No hacer commit ni push, ni descartar cambios de otros colaboradores.

## 1. Resultado que se pide

**Prueba de aceptación añadida por el usuario el 15 de octubre:** [docs/history/frontend/pot-tests-without-imposed-result.md](pot-tests-without-imposed-result.md). Comparar olla con tapa normal y recipiente hermético con agua, aire inicial y calor constante, sin imponer el resultado final. La revisión de Codex detecta ausencia de gases no condensables e imposibilidad actual de calcular el caudal de salida. Integrar los requisitos con esta entrega; no sustituir el aire por vacío ni introducir un caudal arbitrario. Las dos hojas guardadas son borradores bloqueados, no resultados verificados.

Construir una capa termodinámica que aporte relaciones constitutivas, ecuaciones algebraicas de equilibrio y verificaciones al MISMO ensamblaje de conservación. Los flashes puntuales son operaciones del paquete, reutilizadas por la inicialización y la dinámica; no constituyen por sí solos la entrega.

La disponibilidad de un cálculo puntual no habilita automáticamente una combinación dinámica. Ningún nombre de ejemplo, tanque, sustancia o equipo selecciona una ecuación especial fuera del paquete constitutivo correspondiente. Los ejemplos sirven para verificar el ensamblador genérico.

La entrega es progresiva, en el orden de §7. Completar y documentar cada hito antes de publicar su capacidad; continuar al siguiente sin pedir autorizaciones rutinarias. Un bloqueo real de datos/modelo/dominio se documenta con una reproducción, no se sustituye por parámetros inventados. Los hitos no completados siguen figurando como pendientes.

## 2. Punto de partida y compatibilidad

- H0/H1 + H3: agua pura IAPWS-95; TP, PH, UP, UV, saturación y estabilidad, dentro de su dominio publicado. TV existe para inicialización rígida.
- E0–E3: un volumen, una especie (agua), frontera rígida o presión prescrita suave, materia/energía, cambio de fase y extracción; RK45. Fuera de ese alcance no afirmar soporte.
- La corrección de q ya está integrada: suma de fracciones másicas de fases de tipo vapor. No reintroducir la rama sintética de fixtures. Para fases `fluido`, q no implica un título de saturación.
- Los contratos HTTP actuales siguen en revisión 1. Mantenerlos funcionales; no cambiar silenciosamente el significado de campos ni presentar el nuevo contrato como una revisión ya desplegada.
- El recuento, la inicialización, los residuos ejecutados y las capacidades vienen del backend. El cliente no certifica rango o GL contando fórmulas ilustrativas.

### Preparación existente en Codex

`app/motor/estructuraTermodinamica.ts` construye una representación simbólica de incidencia: balances de masa por componente y de U por volumen, transferencias compartidas, cancelación global, requisitos del cierre y topología de fases pendiente. No evalúa propiedades ni es un segundo solver.

`estructuraSolicitudDinamica()` conecta esa representación con la petición v1 sin alterar el JSON HTTP. La estructura local lleva `ejecutable: false` y `recuento: null`: no es una capacidad del servidor ni una solicitud numérica v2. `relacionesTermodinamicas.ts` contiene el marco de potenciales y restricciones, distinto de las ecuaciones ejecutadas publicadas por backend.

Reutilizar los IDs, signos y separación de responsabilidades, no interpretar su LaTeX como código ni exigir que ese grafo ilustrativo sea el residuo termodinámico completo. El backend ensambla sus términos tipados y publica su procedencia.

## 3. Fundamento y estado canónico

Para sistemas simples compresibles macroscópicos, sin términos de superficie, eléctricos, magnéticos o gravitacionales diferenciales:

```
dU = T dS - P dV + Σ μ_i dn_i
H = U + PV; G = H - TS; A = U - TS
μ_i = (∂G/∂n_i)_(T,P,n_j≠i)
```

El paquete debe declarar qué potencial/modelo fundamental usa y qué propiedades/derivadas obtiene coherentemente. No mezclar Cp, h, s, densidad y actividades de fuentes incompatibles sin una construcción termodinámica documentada. Las referencias de energía y entropía deben ser explícitas por especie y compatibles entre fases y paquetes conectados. Un cambio de referencia consistente no cambia la evolución física en los sistemas sin reacción.

Estado conservado por volumen: cantidades totales por componente y energía total (m_i o n_i y U; H puede ser coordenada numérica equivalente). Bajo equilibrio local, el reparto entre fases es algebraico; no integrar a la vez cantidades totales y todas las cantidades de fase como estados independientes.

```
n_i = Σα n_i^α; n^α = Σi n_i^α; x_i^α = n_i^α/n^α
U = Σα n^α ū^α; V = Σα n^α v̄^α
β_α = n^α/n; χ_α = m^α/m; ε_α = V^α/V
```

Una fase ausente no tiene composición física determinada. Cada fase presente necesita ID propio, separado de su tipo: `liquido-a` y `liquido-b` pueden tener el mismo tipo. El tipo no es una clave única. El componente tampoco tiene una fase fija. El conjunto activo se calcula y no se deduce de `tiposPermitidos`.

Separar concentración de componente m_i/V, densidad de mezcla m/V y densidad de fase m^α/V^α. En mezclas, β, χ y ε NO son intercambiables. Las masas molares de fase dependen de su composición. Los moles totales no se conservan en una reacción arbitraria; la masa requiere estequiometría compatible cuando se implemente reacción.

### Equilibrio y estabilidad

- En fases presentes que pueden intercambiar la especie: igualdad de T, P y μ_i (o fugacidades con estado estándar común).
- Fases/especies ausentes: restricciones de no negatividad, condiciones de estabilidad/complementariedad adecuadas; no evaluar log(0) ni imponer una igualdad a una fase ficticia.
- TP con cantidades fijadas: mínimo global admisible de G. UV con cantidades fijadas: máximo de S. TV con cantidades fijadas: mínimo de A.
- PH y UP: reconstrucción de energía y estado con estabilidad a la T/P obtenidas. No etiquetar una búsqueda de raíces como mínimo de Gibbs a U/P fijos.
- Una raíz convergida no certifica estabilidad. Publicar fases candidatas realmente exploradas, método, residuos, tolerancias, limitaciones de búsqueda y diagnóstico de ambigüedad/no convergencia.
- El modelo debe admitir una fase líquida homogénea, LV, LL y LLV cuando el paquete y dominio estén verificados. No forzar LV si una separación LL/LLV reduce el potencial pertinente.
- La regla de fases describe libertad intensiva de equilibrio; no reemplaza el recuento completo de cantidades, iniciales, corrientes, relaciones mecánicas y datos del estudio.

## 4. Paquetes constitutivos y datos

Un paquete tiene identidad y versión, especies verificadas por ID/CAS, modelos por fase, parámetros de interacción y su procedencia, referencias, dominio y operaciones admitidas. La configuración participa en la identidad/caché física. No seleccionar un modelo únicamente por el nombre del compuesto ni completar parámetros binarios ausentes con cero.

Empezar con una mezcla ideal verificable como referencia analítica. Después elegir y justificar un primer paquete no ideal y un binario con datos públicos suficientes. Evaluar los adaptadores ya instalados antes de añadir dependencias. La elección de un modelo no acredita toda combinación de sustancias, presiones o fases.

Para modelos basados en energía de Gibbs de exceso, comprobar las contribuciones térmicas y composicionales necesarias; por ejemplo, a composición/P constantes:

```
h^E = g^E - T (∂g^E/∂T)
s^E = -(∂g^E/∂T)
```

No usar γ solamente para equilibrio y luego omitir calor/entropía de mezcla al cerrar energía. No estimar densidad de mezcla sumando densidades puras: se necesita un modelo de volumen y su dominio declarado. Modelos cúbicos, de actividad o multiparamétricos se habilitan según sus capacidades reales, sin promesa universal.

Los overrides futuros deben modificar parámetros o relaciones identificadas de un paquete y volver a validar sus dependencias; no aceptar h, Cp y densidad arbitrarios como funciones independientes a la vez. El frontend no ofrecerá esos overrides por existir un campo sin soporte.

## 5. Ensamblaje conservativo y transporte

Cada corriente interna tiene UN ID y UNA transferencia por componente y energía; su contribución aparece con signos opuestos. El donante depende del signo del caudal. La extracción identifica mezcla homogénea o fase del donante, diferenciando dos líquidos si existen.

Para una corriente convectiva, la composición transportada procede de la fase/mezcla extraída. Especificar caudales por componente incompatibles con esa composición aporta restricciones contradictorias; no convertir la corriente en selectiva ni ajustar el estado para aceptarlas. Una corriente exterior puede declarar su composición. Una transferencia selectiva requiere una ley y energía propias; queda rechazada hasta formularlas.

```
dm_(v,i)/dt = Σs B_(v,s) m_dot_(s,i)
dU_v/dt = Σs B_(v,s) E_dot_s + Σq B_(v,q) Q_dot_q - W_dot_v
E_dot_s = m_dot_s h_donante        [convectivo, sin cinética/potencial]
```

La cancelación interna debe ser algebraica por identidad, no dos cálculos aproximados de una misma transferencia. Si los paquetes de los extremos tienen referencias distintas, convertir explícitamente las referencias o rechazar la conexión; no reutilizar valores de h incompatibles.

Conectar volúmenes no impone igualdad de presión ni determina el caudal. Conservar las relaciones mecánicas/leyes declaradas; diagnosticar las ausentes. Sin hidráulica/momento implementados, un caudal impuesto es un dato legítimo, no una ley deducida de ΔP.

Un contacto térmico comparte Q con signos opuestos. Una ley por conductancia necesita G con unidad y fuente; es una relación opcional, no un coeficiente automático. Una pared con almacenamiento tiene su balance propio y capacidades declaradas; no contar simultáneamente el almacenamiento en pared y en fluido.

Frontera rígida: dV/dt=0. Frontera cuasiestática con P prescrita: conservar trabajo y la transformación H=U+PV, dH/dt=J_E+V dP/dt. No introducir P fija por uniformidad espacial. Resolver la incoherencia actual: si `formulacionEnergia.presionPrescrita` está presente debe concordar con la frontera; si falta, preservar compatibilidad v1. No ignorar declaraciones incompatibles.

### Evolución y estado de fase

En cada evaluación del RHS/residuo, el coordinador obtiene el estado termodinámico a partir de las cantidades/energía actuales. El paquete no modifica inventarios ni caudales para converger. No sustituirlo por una consulta guardada ni por interpolación sin control de error/dominio.

El equilibrio instantáneo es una hipótesis explícita. La dinámica de nucleación, difusión o transferencia interfacial finita requiere otro modelo con estados/leyes propios; queda fuera del primer equilibrio local. No afirmar que este motor describe esas velocidades por admitir dos fases.

## 6. Contrato e integración, antes del nuevo solver

Preparar una revisión aditiva y discriminada de los contratos, documentada con tipos compartibles y ejemplos compilables, antes de cambiar respuestas. Mantener revisión 1 sin cambios obligatorios. No enviar campos nuevos desde frontend a una API antigua suponiendo que se ejecutan.

La ampliación de ensamblajes debe representar:

1. Catálogo central de componentes, registro único de datos con unidades/rutas/origen y paquetes configurados por ID.
2. `volumenes[]`: balances activos, formulaciones efectivas DE CADA volumen, paquete/política, frontera e iniciales por referencia. La energía actual de la hoja no se puede copiar a todos los volúmenes.
3. `corrientes[]`: extremos, mecanismo, modo exclusivo de materia, estado exterior cuando puede ser donante y extracción por extremo/donante. Las selecciones por tipo que sean ambiguas ante dos líquidos deben diagnosticarse y pedir identificación de fase.
4. `intercambiosTermicos[]`: extremos y ley/datos referenciados; las fuentes exteriores y contactos internos no tienen dos valores independientes.
5. Modelo ensamblado: variables con propietario/componente/fase; ecuaciones con incidencia, dimensiones, procedencia y relación constitutiva aplicada; restricciones y verificaciones separadas de balances independientes.
6. Inicialización conjunta, recuento del mismo ensamblaje y diagnósticos del campo que falta. Parámetros de modelo no se convierten en incógnitas por ocultar un campo.
7. Resultados por volumen y fase, IDs estables durante la trayectoria, eventos y residuos locales/globales. No renombrar fases solo por ordenar densidades entre muestras ni atribuir composición a una ausente.
8. Evidencia de estabilidad y potenciales: definición/base/unidad de G/A/S/μ, estado estándar, alcance de búsqueda, reconstrucción y residuos. μ_i es molar; las propiedades u/h/s actuales son específicas másicas. No cambiar su base silenciosamente.

Publicar capacidades por paquete/operación/combinación: TP no implica UV, LV no implica LLV, estático no implica dinámico. Registrar no soportado y motivo. Diagramas de fases usarán el mismo paquete y algoritmo de equilibrio, con sus residuos, sin fórmulas paralelas del frontend.

Codex integrará la nueva revisión cuando se entregue su esquema. La estructura simbólica local sirve para auditar incidencia, no para certificar que el backend ha implementado la ampliación. No introducir rutas de laboratorio en esta integración.

## 7. Hitos y aceptación

### M0 — Coherencia, referencias y contrato

Corregir la guarda `presionPrescrita`; documentar referencias, potenciales, fuentes de datos y modelo de fases. Entregar contrato versionado de paquetes/ensamblajes y ejemplos tipados. Las peticiones v1, `modeloId` y resultados anteriores permanecen compatibles salvo una corrección física demostrada con caso mínimo.

### M1 — Mezcla ideal, potenciales y estabilidad

Modelo de referencia con dos componentes, identidades/derivadas, composiciones y potenciales químicos. Equilibrio TP y límites de componente puro, composición simétrica/asimétrica, trazas y reordenación por ID. Comparación con solución analítica donde exista. No simular LLE con un modelo ideal que no la predice.

Integrarlo como relación algebraica del ensamblaje: inicialización, datos faltantes, variables/equaciones y capacidades. Una API puntual aislada no completa M1.

### M2 — Binario no ideal y energía

Un primer paquete real y binario justificados por datos disponibles. LV, burbuja/rocío y estabilidad; posteriormente PH/UV/UP que admita el paquete. Reconstruir cantidades, energía y volumen; comprobar calor de mezcla, referencias y derivadas. Los límites de presión/datos/volumen se declaran, no se inventan.

Cerrar primero un volumen con mezcla y composición cambiante; comprobar términos composicionales, extracción y ausencia de doble conteo de calor latente. Si TP está verificado y UV no, publicar esa distinción.

### M3 — Acoplamiento de volúmenes con propiedades reales

Primero dos volúmenes de agua con corriente compartida, después contacto térmico, después el paquete binario habilitado. Un vector de estado/residuo y conservación global. Modelo ensamblado genérico que pueda diagnosticar más volúmenes aunque el primer alcance verificado sea dos.

Pruebas: aislado, fuente exterior, circulación/inversión, acumulación/desacumulación, energía a distintas referencias compatibles, extracción por fase y cambio de fase. Un contacto térmico cerrado debe evolucionar de forma compatible con la segunda ley; no exigir que la entropía de cada volumen abierto crezca por separado.

### M4 — LL y LLV

Buscar separación en dos líquidos y líquido–líquido–vapor con el mismo marco de equilibrio/estabilidad. Datos y parámetros adecuados al equilibrio verificado. Múltiples inicializaciones/búsqueda de estabilidad y caso que rechace una raíz LV inestable frente a LL/LLV. No identificar fases por tipo único.

Conectar el reparto con energía y extracción del volumen; no limitarlo a una gráfica binaria. La trayectoria debe conservar cantidades cuando aparece/desaparece una fase y cuando se intercambian etiquetas numéricas de soluciones.

### M5 — Sólido del agua, triple y diagramas

Auditar e integrar el modelo de hielo Ih compatible con las referencias del agua; sólido–líquido, sólido–vapor y triple dentro del dominio común. Otros hielos requieren sus modelos propios; no declararlos por extrapolación.

TP en el triple no determina las fracciones. Comprobar el rango real con especificaciones extensivas adicionales: ni siquiera U/V bastan universalmente para toda degeneración. Diagramas P–T y trayectorias son derivados del mismo cierre y deben distinguir región no soportada, inestable y metastable. Una gráfica ternaria de composición requiere tres componentes; no confundirla con coexistencia de tres fases de una sustancia pura.

No extender sólidos en mezclas automáticamente: solubilidad, SLE, eutécticos y soluciones sólidas necesitan paquetes y datos específicos. Registrar ese trabajo futuro con sus requisitos.

### M6 — Robustez y segunda ley del conjunto

Mejorar/documentar el actual muestreo interno de eventos. Ensayar transiciones que aparecen/desaparecen dentro de un paso, convergencia por paso/tolerancia, trazas y cercanía a límites. No afirmar vigilancia continua si el algoritmo solo certifica puntos.

Para cada caso donde existan los datos de intercambio necesarios, verificar:

```
dS/dt = Σ(m_dot s)_entradas - Σ(m_dot s)_salidas + Σ(Q_dot/T_frontera) + S_dot_generada
S_dot_generada >= 0
```

T de frontera/depósito no se sustituye por T del fluido sin hipótesis. Si falta, declarar la verificación no evaluable. Separar balance de entropía, estabilidad local, estabilidad global y producción irreversible; una no certifica automáticamente las otras.

## 8. Matriz de pruebas exigida

- Referencias primarias/experimentos con fuente, datos y tolerancias; dos wrappers de una misma EOS no son dos modelos independientes.
- Identidades y derivadas con restricciones correctas; μ/fugacidad y unidades; h−u−Pv, g−h+Ts, Gibbs–Duhem donde aplique, volumen/composición y calores de mezcla.
- Reconstrucción de z, n_i, m_i, U/H/V y fracciones β/χ/ε. Límites puros, trazas y especies ausentes. Cambio de orden de componentes y fases.
- Potenciales y referencias: cambio consistente de ceros, extensividad al escalar cantidades, consistencia entre paquetes conectados. No comparar valores absolutos de μ de referencias incompatibles.
- Estabilidad frente a fases candidatas, raíces falsas/metastables, datos incompatibles, paquete sin parámetros y dominio no soportado.
- Recorrido TP → energético → TP y residuo completo, sin aceptar convergencia solo por último incremento pequeño.
- Inicialización conjunta/GL, datos redundantes/contradictorios, cero explícito versus ausente, unidades equivalentes y origen exacto del pendiente.
- Conservación local/global de todas las especies y energía, igualdad de las transferencias internas, inversión de donante y extracción por fase.
- Trayectorias y eventos contra referencias independientes, refinamiento de tolerancias y controles negativos que corrompan una transferencia, fase o referencia y fallen.
- Regresión completa y lectores TS sobre respuestas reales sin modificaciones. Ejemplos generados por endpoints, no números ajustados a mano.

## 9. Fuera de la primera ampliación

Equilibrio químico con reacción, electrólitos, membranas selectivas, cinética interfacial/nucleación, capilaridad, CFD/momento y modelos completos de sólidos multicomponente. Se preserva su lugar en la arquitectura, pero no se publican como capacidades. El usuario ha pedido una base extensible, no una promesa de que una única EOS cubre toda la termodinámica.

## 10. Entrega para Codex

Documento de decisiones físicas y guía de integración; tipos/versiones nuevos; matriz de capacidades por hito; ecuaciones ensambladas, variables y rutas; datos binarios/fuentes/referencias; estados parciales/no soportados; ejemplos reales; resultados de pruebas y límites. Señalar qué invariantes puede verificar el lector sin repetir la EOS. Indicar si hay que recargar el servicio. No modificar los lectores frontend para ocultar una inconsistencia del backend.

Fuentes primarias de fundamento/implementación:

- [IAPWS-95](https://iapws.org/technical-guidance/release/IAPWS-95): formulación del fluido y propiedades coherentes.
- [IAPWS, energía de Gibbs del hielo Ih](https://www.iapws.org/relguide/Ice-Rev2009.pdf) y [fusión/sublimación](https://www.iapws.org/relguide/MeltSub.html): sólido y referencias de coexistencia.
- [NIST teqp, equilibrio generalizado](https://pages.nist.gov/teqp-docs/en/latest/algorithms/GeneralizedPhaseEquilibria.html): restricciones y composición global en problemas de equilibrio.
- [Documentación oficial de CoolProp, mezclas](https://coolprop.org/fluid_properties/Mixtures.html): estabilidad y separación en fases como etapas diferenciadas.
- [Documentación de thermo, NRTL](https://thermo.readthedocs.io/thermo.nrtl.html): energía de exceso y derivadas; no constituye por sí sola validación de un binario concreto.
