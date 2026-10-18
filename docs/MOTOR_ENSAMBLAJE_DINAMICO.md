# Ensamblaje y resolución dinámica del motor independiente

14 de octubre de 2026. Responde a `frontend/CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md` (E0–E3) sobre la física ya entregada en [MOTOR_TERMODINAMICA_H0_H1.md](MOTOR_TERMODINAMICA_H0_H1.md) y [MOTOR_TERMODINAMICA_H3.md](MOTOR_TERMODINAMICA_H3.md). El backend es mío; el frontend, de Codex, y no se ha modificado. No hay commit ni push.

**Qué hay.** Un volumen de agua pura, identificada por CAS, con balances totales de materia y energía, cierre IAPWS-95 y frontera rígida o a presión prescrita. Admite corrientes con donante según el signo del caudal, calor, inicialización con U o T, trayectorias con aparición y desaparición de fases, extracción por fase o de la mezcla, eventos y muestras certificadas. El esquema son los tipos de `frontend/app/motor/contratoEnsamblajeTermodinamico.ts`, sin cambiarlos. Tres rutas: capacidades, validar y resolver.

## Requisitos del encargo

| Requisito | Estado | Dónde / evidencia |
| --- | --- | --- |
| **E0** Contrato formalizado con los tipos TS, sin cambios de forma | Cumplido | §1; `tests/verificar_contrato_ensamblaje.mjs` compila 13 pares reales con `strict`, más un control negativo |
| E0 Validación de sintaxis, unidades, magnitudes, valores finitos y límites físicos, con origen por dato | Cumplido | §2; suite, apartados 1 y 6 |
| E0 Catálogo de variables y ecuaciones con IDs, familias y LaTeX | Cumplido | §3 |
| E0 Recuento estructural (completo, incompleto, conflicto, no evaluable) sin integrar | Cumplido | §3; apartados 1 y 6 |
| E0 Inicialización compatible: UV, UP, TP y **TV** (operación local nueva) | Cumplido | §4; apartado 3 |
| **E1** Volumen rígido monofásico, cerrado y abierto, con P real variable | Cumplido | §5; apartados 2 y 4 |
| E1 Donante según el signo; inversión; continuidad de presión; donante pendiente | Cumplido | §5; apartado 4 |
| **E2** Presión prescrita constante y suave, trabajo con derivada total de V, coordenada H verificada | Cumplido | §5; apartado 5 |
| E2 Presión discontinua | **Rechazada a propósito** (`MOTOR_ENS_NO_SUAVE`): falta la regla física de salto | §5 |
| **E3/H4** Equilibrio bifásico en la trayectoria, eventos de aparición y desaparición, extracción por fase u homogénea, fase ausente, cambio prohibido | Cumplido | §6; apartado 8 |
| Muestras certificadas; detención con resultado parcial sin muestras inválidas | Cumplido | §6; apartado 9 |
| Ejemplos generados desde los endpoints; lector TS; regresión completa | Cumplido | §7, §8 |
| Fuera del encargo: varios volúmenes, mezclas, reacción, transferencia selectiva, sólidos, región crítica | No implementado; se diagnostica | §9 |
| `redundante_compatible` en el recuento | **No se produce**: ninguna restricción admitida es redundante y compatible a la vez (§3) | — |

Integrador: solo `rk45`. `euler_implicito` sale `no_soportado` porque no está verificado con el cierre IAPWS.

---

## 1. Rutas y esquema

```
GET  /motor/ensamblajes/capacidades   alcance verificado (forma en §1.2)
POST /motor/ensamblajes/validar       SolicitudEnsamblajeDinamico -> RespuestaValidacionDinamica
POST /motor/ensamblajes/resolver      SolicitudEnsamblajeDinamico -> RespuestaResolucionDinamica
```

Es la revisión 1 del protocolo de ensamblaje, independiente de la revisión 1 de la API puntual, que no cambia. La API puntual sigue publicando `dinamica: false`; poder integrar no cambia el significado de esa bandera. El cuerpo se lee como JSON libre y la respuesta es HTTP 200 con diagnósticos de contrato: no hay 422 para errores conocidos. Un rechazo nunca conserva resultados anteriores: `resultados: null`.

### 1.1 Respuestas

- **validar**: `{revision, solicitudId, modeloId, recuento, variables, ecuaciones, diagnosticos, inicializacion}`. No integra. `inicializacion.estadoTermodinamico` es una `EvaluacionEstado` certificada por el servicio puntual, o `null`.
- **resolver**: `{validacion, estado, resultados}`. La validación va completa. `estado` vale:
  - `resuelto`: se integró hasta tf;
  - `parcial`: se detuvo por un evento de política, fase ausente, salida de dominio, agotamiento o donante en saturación;
  - `no_soportado`: algún diagnóstico `no_soportado`;
  - `invalido`: un recuento distinto de `listo`, una inicialización no compatible o diagnósticos pendientes;
  - `no_convergente`.
- `resultados` trae:
  - `metodo`: integrador, tolerancias, pasos, reintentos y cómo se vigilan los eventos;
  - `tiempos` y `series`, todo en SI;
  - `estadosTermodinamicos`: una `EvaluacionEstado` certificada por muestra, sin los `motivo` largos de las verificaciones (son opcionales en el tipo);
  - `eventos` y `residuos`.
- **Series:** `volumen.<v>.m.<c>`, `.U`, `.T`, `.P`, `.V` y `.q` (fracción másica de vapor, definida abajo); `.H` y `.W` solo con presión prescrita; `.Q`; `corriente.<i>.F` (kg/s, con signo, en el sentido declarado) y `corriente.<i>.h` (entalpía del donante). Si una muestra no define h (fase de extracción ausente), esa serie **no se publica**: los tipos no admiten nulos dentro de `valores`.
- **Fracción de vapor `q`** (variable inicial y serie, la misma definición en ambas): suma de `fraccionMasica` de las fases de tipo `vapor` presentes en el estado certificado, dentro o fuera de la campana. Vapor sobrecalentado da q = 1 aunque no haya coexistencia; líquido, 0; en coexistencia, el título. Un fluido supercrítico (tipo `fluido`, T > Tc y P > Pc) no es vapor: q = 0, y se lee junto a las fases publicadas. Por encima de Tc con P ≤ Pc la convención de H1 llama `vapor` a la fase, así que q = 1. Es la definición que aplica `lectorEnsamblajeTermodinamico.ts`. *Corrección del 14/10/2026 (incidencia `INCIDENCIA_CLAUDE_FRACCION_VAPOR_ENSAMBLAJE.md`)*: antes, una única fase vapor solo contaba q = 1 si llevaba la verificación `equilibrio`, y el vapor sobrecalentado salía con q = 0.
- **`modeloId`**: `ens-` y 32 hexadecimales de un SHA-256 del ensamblaje normalizado. Entran el CAS y M, el modelo y la política, la referencia IAPWS, balances y formas, el tipo de frontera con sus datos en SI, Q, cada corriente con su signo, caudal, donante, continuidad y extracción, y los iniciales en SI. No entran `solicitudId`, `derivacion`, `origen`, `estudio` ni resultados. Unidades equivalentes de un dato constante dan la misma identidad (10 L y 0.01 m³); una función de t entra como forma canónica más factor y desplazamiento, así que «200·t kPa» y «2·t bar» se tratan como distintas (limitación declarada). Es `null` si hay datos inválidos.

### 1.2 Capacidades: forma aditiva sin tipo TS

Propuesta para que Codex la añada:

```ts
export type CapacidadesEnsamblaje={revision:1;disponible:boolean;motivo:string|null;modelos:ModeloEstado[];
  componentesCAS:string[];volumenes:number;componentes:number;balances:{materia:boolean;energia:boolean;momento:boolean};
  formas:{materia:'cantidad';energia:'total'};fronteras:('rigida'|'presion_prescrita')[];
  inicializaciones:Record<'rigida'|'presion_prescrita',('U'|'T')[]>;presionPrescrita:{constante:boolean;funcionSuave:boolean;discontinua:boolean};
  corrientes:{mecanismos:'convectivo'[];materia:('por_componente'|'total_y_composicion')[];presionExterior:('dato'|'continuidad')[];inversion:boolean};
  extracciones:('mezcla_homogenea'|'fase')[];fases:{monofasico:boolean;coexistenciaLiquidoVapor:boolean;eventos:boolean};
  transferencias:'calor'[];expresiones:{variables:['t'];unidadTiempo:'s';suaves:string[];noAdmitidas:string[]};
  integradores:{id:'rk45';nombre:string;tolerancias:string[]}[];muestrasMaximas:number;dinamicaApiPuntual:false};
```

### 1.3 Diagnósticos

`DiagnosticoPreparacion` = `{codigo, estado, mensaje, variableIds, origen:{propietarioId, ruta}}`. Si el problema está en un dato, `origen` es **el del dato** (propietario y ruta al campo de la hoja). Si está en la estructura, la ruta es un puntero JSON de la solicitud.

| Código | Estado | Cuándo |
| --- | --- | --- |
| `MOTOR_ENS_DATO_PENDIENTE` | incompleto | texto en blanco (pendiente, nunca cero) |
| `MOTOR_ENS_UNIDAD`, `MOTOR_ENS_MAGNITUD`, `MOTOR_ENS_FUNCION_DATO` | invalido | unidad de otra familia, magnitud inesperada, función (`inicial`, `frontera`, `geometria`, `estudio`) equivocada |
| `MOTOR_ENS_EXPRESION`, `MOTOR_ENS_DEBE_SER_CONSTANTE` | invalido | sintaxis, valor no finito en [0, tf], t en un dato que debe ser constante |
| `MOTOR_ENS_NO_SUAVE` | no_soportado | abs, min, max o step en un dato (salto sin regla física) |
| `MOTOR_ENS_FUERA_DE_MAGNITUD` | invalido | T, P, V o tf no positivos en [0, tf]; cantidad negativa |
| `MOTOR_ENS_REFERENCIA`, `MOTOR_ENS_FALTA`, `MOTOR_ENS_CAMPO_NO_ADMITIDO`, `MOTOR_ENS_FORMA` | invalido | estructura (un `termodinamica` con una consulta guardada se rechaza) |
| `MOTOR_ENS_COMPONENTES`, `…_COMPONENTE_NO_SOPORTADO`, `…_IDENTIDAD_NO_VERIFICABLE` | no_soportado | más de un componente, otro CAS, proveedorId |
| `MOTOR_ENS_IDENTIDAD` / `…_CAS_INVALIDO` / `…_MASA_MOLAR_CONTRADICTORIA` | incompleto / invalido / invalido | identidad; la masa molar contradictoria se conserva y se rechaza |
| `MOTOR_ENS_BALANCES`, `…_FORMA`, `…_TERMINOS`, `…_ESTACIONARIO`, `…_FUENTES`, `…_SELECTIVO`, `…_TRANSFERENCIA`, `…_METODO`, `…_MODELO` | no_soportado | fuera del régimen admitido |
| `MOTOR_ENS_DOS_CIERRES` | conflicto | u(T) manual y EOS a la vez |
| `MOTOR_ENS_DENSIDAD` | conflicto | densidad declarada constante (restricción adicional a la EOS) |
| `MOTOR_ENS_POLITICA` | conflicto | hipótesis de fase de materia o energía distintas de las del cierre (sin OR) |
| `MOTOR_ENS_FRONTERA`, `MOTOR_ENS_CONTEXTO`, `MOTOR_ENS_EXTRACCION` | conflicto o invalido | frontera y formulación incoherentes; puertos sin corriente; extracción distinta en la corriente y en el cierre |
| `MOTOR_ENS_MECANICA` | incompleto | frontera móvil sin relación mecánica |
| `MOTOR_ENS_Q_PENDIENTE` / `MOTOR_ENS_Q_ADIABATICO` | incompleto / conflicto | sin calor y no adiabático (Q vacío ≠ 0) / adiabático con calor |
| `MOTOR_ENS_DONANTE_PENDIENTE` | incompleto | puede entrar materia y no hay estado exterior; `variableIds` = `corriente.<i>.Text`, `.Pext` |
| `MOTOR_ENS_P_DUPLICADA` | conflicto | continuidad y dato de presión en la misma corriente |
| `MOTOR_ENS_EXTRACCION` | incompleto | multifase posible, la corriente puede extraer y no hay política de extracción |
| `MOTOR_ENS_SOBREDETERMINADO` | conflicto | ecuación sin incógnita propia, p. ej. P adicional en un volumen rígido; refiere los datos implicados |
| `MOTOR_ENS_INICIAL…` | según el caso | inicialización (§4); los códigos del servicio puntual se prefijan con `MOTOR_ENS_INICIAL.` |
| `MOTOR_ENS_DETENIDO_<EVENTO>` | invalido | trayectoria detenida; acompaña a `estado: parcial` |
| `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`, `…_DONANTE_NO_CERTIFICADO` | invalido | una muestra o un donante no se certifica: se corta antes de él |

---

## 2. Datos y fuente única

- **Dónde están los valores.** Solo en `datos`: un registro por ID con magnitud, función, texto, unidad y origen. El volumen y las corrientes guardan referencias.
- **Qué datos se leen.** Solo los referenciados por la estructura activa. Un dato del modo inactivo (por ejemplo, T0 cuando la energía inicial es U) no se lee ni se convierte en restricción.
- **Unidades.** La tabla de `unidadesMotor.ts`, con desplazamiento para °C y °F.
- **Expresiones** (`core/expresiones_motor.py`):
  - misma gramática que `expresionesMotor.ts`, analizada a un árbol propio, nunca con `eval`;
  - **t es el tiempo en segundos** sea cual sea la unidad del dato, y solo se admite en datos de `frontera`;
  - se evalúan en 401 puntos de [0, tf] para comprobar que son finitas y respetan el signo físico;
  - dP/dt de una presión prescrita sale de la **derivada simbólica** del árbol, comprobada frente a diferencias finitas.
- **Caudales.**
  - Los dos modos son exclusivos.
  - La base del caudal y la de la composición se conservan por separado.
  - Masa ↔ moles usa la masa molar del modelo (18.015268 g/mol), nunca una conversión universal.
  - Con un componente, `total_y_composicion` exige la fracción 1 en su base; la suite comprueba que un caudal molar con composición másica da exactamente lo mismo que el caudal másico equivalente.
- **Donante exterior.**
  - Es obligatorio salvo que el caudal sea constante y no pueda entrar materia (salida constante positiva, o cero).
  - Una expresión en t puede invertir el sentido y exige donante.
  - Un cero constante no transporta energía ni pide donante.
- **Extracción.** Con política no monofásica se exige solo a las corrientes que pueden extraer: salida no nula o caudal que depende de t. Una entrada constante positiva nunca extrae, y así se declara. El frontend la pide a todas, que es más estricto y compatible.

## 3. Ensamblaje, catálogo y recuento

**Variables** (`VariableEnsamblada.papel`):
- **Diferenciales:** m y U en volumen rígido; m y H con presión prescrita (ahí U pasa a algebraica).
- **Algebraicas:** T; P (rígido) o V (presión); q; h de cada corriente; P del donante con continuidad; W con presión prescrita.
- **Datos:** V (rígido) o P (presión), F, Q, T_ext, P_ext. Un dato pendiente pasa a ser una incógnita más.

**Ecuaciones** (`EcuacionEnsamblada`, familias materia, energía, estado y mecánica):

| id | Relación |
| --- | --- |
| `materia.<c>` | dm/dt = Σ s_j F_j |
| `energia` | rígido: dU/dt = Σ s_j F_j h_j + Q − P dV/dt, con V = V_geom ⇒ dV/dt = 0. Presión: dH/dt = J_E + V dP/dt, con H = U + PV |
| `estado.u` / `estado.h`, `estado.v`, `estado.reparto` | cierre UV (rígido) o PH (presión): T, P o V y q, por máximo de S |
| `estado.U`, `mecanica.trabajo` | presión: U = H − PV; dW/dt = P dV/dt con la derivada total (comprobación de la forma en U) |
| `estado.donante.<i>` | h_j: exterior h(T_ext, P_donante) si s_j F_j > 0; del volumen (mezcla o fase) si < 0 |
| `mecanica.continuidad.<i>` | P_donante = P del volumen |
| `mecanica.P_restriccion` | P = P_dato en rígido (restricción adicional: conflicto) |
| `estado.flujo` | si la formulación conserva u + Pv en el transporte: se publica la identidad u + Pv ≡ h y se resuelve con h |

**Recuento.** Es un análisis **estructural**: emparejamiento máximo (caminos aumentantes) entre ecuaciones e incógnitas. Las incógnitas son las derivadas de los estados, las variables algebraicas y los datos pendientes; estos se emparejan al final, para que, si sobra una incógnita, sea **el dato que falta** el que se señale y no una variable interna.

- Ecuación sin pareja → `conflicto`, con `MOTOR_ENS_SOBREDETERMINADO`.
- Incógnita sin pareja, dato faltante o inicial faltante → `incompleto`; `gradosLibertad` = incógnitas − ecuaciones.
- Datos inválidos → `no_evaluable`, con los números en null.
- `ecuacionesIndependientes` es el rango estructural.
- La regla de fases no se resta aparte: el reparto lo fija el cierre de equilibrio.
- `datosDefinidos` y `datosFaltantes` cuentan los datos referenciados.
- **El recuento no integra ni evalúa la EOS.**

## 4. Inicialización

Siempre por el **servicio puntual local**, sin HTTP, con la política del cierre. Solo hay una elección activa de energía inicial.

| Frontera | Datos | Operación |
| --- | --- | --- |
| Rígida | m(0), U(0), V | UV certificado |
| Rígida | m(0), T(0), V | **TV** local (`agua.evaluar_TV`): mínimo de A a (T, V, m); palanca en v dentro de la campana. Después UV certificado con la u obtenida, que debe reproducir T(0) a 1e-7 |
| Presión | m(0), U(0), P(0) | UP certificado |
| Presión | m(0), T(0), P(0) | TP certificado. En saturación → `pendiente` (falta una especificación de energía o reparto; no se inventa q) |

Estados resultantes:
- `compatible`: publica las variables iniciales y la `EvaluacionEstado`.
- `incompatible`: estado fuera de dominio (p. ej. U(0) bajo el punto triple), política violada en t = 0 (monofásica con un estado bifásico) o masa inicial nula (sin estado intensivo).
- `no_soportada`: región crítica.

No se usa ningún resultado de una consulta anterior como semilla. `c_u` no interviene.

## 5. Física de la trayectoria (E1, E2)

**Volumen rígido.** Estados (m, U); u = U/m, v = V/m → UV → T, P, fases. La presión cambia al calentar: en la hoja real de Codex (10 kg en 10 L, 1 kW, 300 s) pasa de 6.08 a 10.89 MPa, y U = U₀ + Q·t exactamente.

**Presión prescrita.** Cuasiestática, con P uniforme igual a P_ext(t), suave. Coordenada H:

$$\frac{dU}{dt} = J_E - P\frac{dV}{dt},\ H = U + PV \ \Rightarrow\ \frac{dH}{dt} = J_E + V\frac{dP}{dt}$$

Estados (m, H): h = H/m → PH → T, v, fases; V = m·v y U = H − PV se reconstruyen y no se integran. Para **verificar** la equivalencia se integra aparte W = ∫P dV/dt dt con la derivada total:

$$\frac{dV}{dt} = v\frac{dm}{dt} + m\Big[\Big(\frac{\partial v}{\partial h}\Big)_P\frac{dh}{dt} + \Big(\frac{\partial v}{\partial P}\Big)_h\frac{dP}{dt}\Big],\qquad \frac{dh}{dt} = \frac{dH/dt - h\,dm/dt}{m}$$

- **Derivadas en una fase**, analíticas desde la EOS:
  - (∂v/∂h)_P = (∂v/∂T)_P / cp;
  - (∂v/∂P)_h = (∂v/∂P)_T − (∂v/∂T)_P (v − T(∂v/∂T)_P)/cp.
- **Derivadas en coexistencia:**
  - (∂v/∂h)_P = (v″−v′)/(h″−h′);
  - (∂v/∂P)_h por diferencias centradas de PH (δP = 1e-6·P), solo si dP/dt ≠ 0.
- **Residuo publicado:** `energia` = |U − (U₀ + ∫J_E dt − W)|. Nunca se usa dm/dt/ρ constante.
- **Prueba independiente:** una compresión adiabática cuasiestática con P(t) en rampa y en seno debe ser **isentrópica**. Se cumple con |Δs| ≤ 1.0e-6 J/(kg·K) en todas las muestras certificadas, y esa condición no aparece en ninguna ecuación del coordinador.

**Corrientes.**
- J_E = Σ s_j F_j h_j + Q.
- Donante según el signo **actual**: exterior h(T_ext(t), P_donante(t)) al entrar; el volumen al salir.
- `continuidad` toma P_donante = P del volumen en cada evaluación.
- El estado exterior es el del plano de transporte: no se interpone ninguna válvula, bomba ni pérdida invisible.
- Si el donante exterior cae en saturación, la trayectoria se detiene con `donante_en_saturacion`. Es un caso real: por continuidad, el donante sigue a la presión del recipiente hasta Psat(T_ext).

**Lo que la EOS no hace.** Recupera el equilibrio mecánico de un estado concentrado. No es un balance de momento, no predice caudales hidráulicos y no añade trabajo de bomba.

## 6. Integración, fases y eventos (E3/H4)

**Integrador.**
- Dormand-Prince 5(4) (`scipy.integrate.RK45`), con `rtol` y `atol` separados por magnitud: masa en kg, energía en J.
- Paso máximo = intervalo de muestreo.
- Estados [m, E, ∫J_E dt, W].

**Etapas.** Usan flashes rápidos sin barrido ni certificación (`certificar=False`) con semilla de T. La semilla solo acelera: u a v fijo y h a P fija son monótonas, así que la raíz de la horquilla es la única.

**Vigilancia de fases.**
- Sobre cada paso **aceptado**, en tres puntos interiores de la salida densa y en el extremo. Las etapas de intentos rechazados no cuentan.
- Si el conjunto de fases cambia, se localiza el instante por bisección sobre la salida densa (tolerancia 1e-9·tf). Después se **re-integra desde el inicio del paso hasta ese instante** (sin pasos que crucen la arista de las propiedades) y se reinicia el integrador.
- Códigos de evento: `aparicion_fase`, `desaparicion_fase` y `cambio_denominacion` (líquido ↔ fluido ↔ vapor sin coexistencia, que no es una transición de fase).
- Un cambio que entra y sale dentro de un mismo paso y no se ve en esos 4 puntos podría pasar inadvertido. Ese es el alcance declarado: la vigilancia es de puntos, no certifica toda la trayectoria.

**Políticas.**
- `cambioInterno: prohibido` detiene la trayectoria en cualquier aparición o desaparición.
- `monofasico` la detiene al aparecer una segunda fase.
- `tiposPermitidos` la detiene ante un tipo no permitido.
- Se publican las muestras certificadas hasta el instante del evento, que también es muestra, y la respuesta es `parcial`.

**Fallo de un flash en una etapa.**
- No se reutilizan propiedades de la etapa anterior: se repite desde el último estado aceptado con el paso dividido entre 4.
- Bajo 1e-10·tf se detiene con `salida_dominio`, `agotamiento`, `donante_en_saturacion` o `fase_ausente`, según el motivo.
- Una fase de extracción ausente en t = 0 detiene en t = 0 con la muestra inicial.

**Muestras.**
- Uniformes en [0, tf], más el instante de cada evento y el de detención.
- Cada una se **certifica** con el servicio puntual (UV o PH con barrido global y estabilidad).
- Los donantes exteriores activos se certifican con TP.
- Si una muestra no se certifica, se corta antes de ella: no hay muestras inválidas ni sustitutos.

**Calor latente.** No se añade ninguna fuente: está en h″ − h′. La prueba lo comprueba, porque H = H₀ + Q·t exacto a lo largo de la ebullición.

### Residuos publicados (`resultados.residuos`)

| ecuacionId | maximoEscalado | tolerancia |
| --- | --- | --- |
| `materia.<c>` | máx\|m − m₀ − ∫Σ s F dt\| con cuadratura **independiente** (`quad`) de los caudales, dividido por (atol_m + rtol·máx m) | 10 |
| `energia` | máx\|U − (U₀ + ∫J_E − W)\| / (atol_E + rtol·máx(\|U\|, \|∫J_E\|)). En presión es la equivalencia forma U ↔ forma H; en rígido es una comprobación de contabilidad | 10 |
| `estado.u` / `estado.h` | máx\|m·u_cert − U\| (o h_cert, H) del estado certificado / escala de energía | 1 |
| `estado.v` | máx\|m·v_cert − V\|/V / 1e-9 | 1 |
| `mecanica.P` | presión: máx\|P_cert − P_ext(t)\|/P / 1e-12 | 1 |
| `estado.donante` | máx\|h_TP certificado − h usado\|/(RT) / 1e-9 | 1 |

---

## 7. Evidencia

```
python tests/validar_motor_ensamblaje.py                # 239 comprobaciones, ~1.5 min
node tests/generar_solicitudes_ensamblaje.mjs           # solicitudes REALES con prepararEnsamblajeTermodinamico
python tests/generar_ejemplos_motor_ensamblaje.py       # docs/ejemplos/motor-ensamblaje-* desde los endpoints
node tests/verificar_contrato_ensamblaje.mjs            # tipos TS strict + 175 EvaluacionEstado por el lector puntual
```

| Prueba (apartado de la suite) | Referencia independiente | Resultado |
| --- | --- | --- |
| 1. Petición incompleta | — | recuento `incompleto` con el dato y su ruta; inicialización `pendiente` y vacía; resolver no integra; Q ausente ≠ 0 |
| 2. Rígido cerrado | U = U₀ + Q·t exacto; **evaluar_TP(T, P)** de cada muestra devuelve u = U/m y v = V/m (otro camino que el cierre UV) | U exacto a 1e-6; v a 1e-8; P de 6.08 a 10.9 MPa |
| 3. Inicialización | T(0) → TV → U(0) → UV → T(0); °C y K | U reproducido a 1e-3 J; incompatibles y pendiente correctos |
| 4. Llenado rígido | m = m₀ + F·t; U = U₀ + F·h_in·t exactos | exacto a 1e-7 relativo |
| 4. Vaciado con calor, inversión F = 0.8·cos(0.05t), continuidad | **RK4 de paso fijo** de la prueba con los flashes del núcleo | ≤ 1e-6 a 2e-6 relativo; h donante exterior al entrar y del volumen al salir |
| 5. P constante | H = H₀ + Q·t, W = P(V − V₀), U = H − PV exactos | a 1e-6 |
| 5. P suave adiabática (rampa y seno) | **s constante** (segunda ley) | \|Δs\| ≤ 1.0e-6 J/(kg·K); residuo `energia` 0.019 de la tolerancia |
| 6. Restricciones y duplicados | — | u(T) + EOS, P adicional en rígido, densidad constante, políticas, continuidad + dato, masa molar, unidades; identidad estable frente a unidades y títulos |
| 7. Convergencia | serie de rtol 1e-5 … 1e-11 | errores decrecientes; < 1e-6 relativo a rtol 1e-9 |
| 8. Ebullición a 1 bar, 10 kW, 1 kg | t_ebull = m(h′ − h₀)/Q, t_seco = m(h″ − h₀)/Q | eventos en 33.349786 y 259.094162 s (teoría 33.349786 y 259.094162); T = Tsat durante la meseta a 1e-8 K; H = H₀ + Q·t (sin doble calor latente) |
| 8. Condensación en rígido (2 kg, 1 m³, −5 kW) | t* con v″(T*) = V/m y u″(T*) | evento en 55.220155 s, igual a la teoría a 1e-6 |
| 8. Extracción por fase | h′, h″ y h del estado | se extrae exactamente h_l, h_v o h; U_vapor < U_mezcla < U_líquido |
| 8. Fase ausente y política prohibida | — | `parcial` en el evento; extraer vapor de un líquido detiene en t = 0; el líquido extraído se agota en 7.27 s |
| 9. Dominio y agotamiento | — | calentamiento rígido hasta superar 100 MPa y vaciado hasta agotar: `parcial` con muestras certificadas; U(0) inválido no integra |
| 11. Fracción de vapor | `q` frente al reparto de fases publicado en la inicialización y en **cada** muestra: líquido, coexistencia, vapor sobrecalentado, entrada y salida de la campana, fluido supercrítico y la muestra de evento que detiene una política | igual a 1e-12 en todas |
| 10. HTTP y solicitudes reales del frontend | `prepararEnsamblajeTermodinamico` sobre las hojas de prueba de Codex | las 5 se validan; la rígida real se resuelve por HTTP |

Tiempos típicos con 101 muestras: 4 a 7 s. Domina la certificación de cada muestra, con barrido global y TPD. `coexistencia(T)` y `saturacion(T)` se memorizan: son funciones puras de T y la caché no cambia ningún resultado (las suites H1 y H3 pasan igual).

## 8. Ejemplos (`docs/ejemplos/motor-ensamblaje-*`)

Generados desde los endpoints. Varias peticiones son las solicitudes reales del frontend.

| Caso | Resultado |
| --- | --- |
| `capacidades` | alcance publicado |
| `validar-incompleto` | V en blanco: `incompleto`, culpa a `volumen.dominio.V` |
| `validar-conflicto-dos-cierres` | hoja real con u(T) manual: `MOTOR_ENS_DOS_CIERRES` |
| `validar-conflicto-P-rigida` | hoja real rígida con P: `conflicto`, `MOTOR_ENS_SOBREDETERMINADO` |
| `validar-inicial-T-rigida` | hoja real con T(0): TV compatible (293.15 K, 4.03 MPa) |
| `resolver-rigida-calentamiento` | hoja real: 297.10 → 304.42 K, 6.08 → 10.89 MPa |
| `resolver-abierta-presion-constante` | hoja real abierta a 1 bar, entrada 3 kg/s a 40 °C y 2 bar, salida 2 kg/s, 8 kW |
| `resolver-llenado-rigido` | llenado de un recipiente lleno de líquido con continuidad de presión: 7.83 → 12.48 MPa |
| `resolver-vaciado-con-ebullicion` | salida 1.5 kg/s con 20 kW desde un estado con traza de vapor |
| `resolver-presion-suave-adiabatica` | P = 3e5 + 2e5·sin(0.05t): isentrópica |
| `resolver-ebullicion-presion-constante` | aparición y desaparición de fase en los tiempos teóricos |
| `resolver-condensacion-rigida` | aparición de líquido en 55.22 s |
| `resolver-extraccion-liquido` | fase extraída agotada: `parcial` |
| `resolver-cambio-fase-prohibido` | política monofásica: `parcial` en el evento |

## 9. Guía de integración para Codex

1. **Capacidades.** Leer `GET /motor/ensamblajes/capacidades` y ofrecer solo lo publicado. Si `disponible: false`, mostrar `motivo`.
2. **Validar.** Enviar el resultado de `prepararEnsamblajeTermodinamico` tal cual a `/validar`, también con diagnósticos locales si se quiere el análisis del backend. Mostrar `recuento` (con `motivo`), las `ecuaciones` (LaTeX) y los diagnósticos por `origen.ruta`. La inicialización compatible trae T, P, V y q, y una `EvaluacionEstado` que el lector puntual acepta.
3. **Resolver.** Llamar a `/resolver` solo con `recuento.estado === 'listo'` e inicialización `compatible`; el backend lo vuelve a comprobar. Descartar respuestas tardías por `solicitudId` e invalidar el resultado si cambia `modeloId`.
4. **Resultados.** Las series van en SI y por `variableId`. `estadosTermodinamicos[k]` corresponde a `tiempos[k]`. Los eventos llevan su código y su instante. Con `estado: 'parcial'`, los diagnósticos `MOTOR_ENS_DETENIDO_*` dicen por qué.
5. **Unidades.** La variable t de las expresiones son **segundos**.
6. **Sin red en el integrador.** El coordinador llama a las propiedades localmente.
7. **Cierre dinámico y motor manual separados.** Una resolución no es una consulta guardada, y el motor manual con u(T) sigue intacto.
8. **Recarga.** Hay que reiniciar uvicorn: hay rutas y módulos nuevos.

## 10. Archivos

| Archivo | Cambio |
| --- | --- |
| `backend/main.py` | +3 rutas e imports (solo añadidos; fines de línea mezclados respetados) |
| `backend/motor_ensamblaje.py` | nuevo: contrato, validación, ensamblaje, recuento, inicialización, resolución |
| `core/ensamblaje_dinamico.py` | nuevo: coordinador numérico |
| `core/expresiones_motor.py` | nuevo: expresiones seguras y derivada simbólica |
| `core/agua_iapws95.py` | añadidos: `evaluar_TV`, `certificar=False` y `T_semilla` (por defecto todo igual que H3), caché de `coexistencia` y `saturacion` |
| `tests/validar_motor_ensamblaje.py`, `tests/generar_ejemplos_motor_ensamblaje.py`, `tests/verificar_contrato_ensamblaje.mjs`, `tests/generar_solicitudes_ensamblaje.mjs`, `tests/fixtures_ensamblaje/*.json` | nuevos |
| `docs/MOTOR_ENSAMBLAJE_DINAMICO.md`, `docs/ejemplos/motor-ensamblaje-*` | nuevos |

No se tocaron el frontend, el laboratorio ni `thermodynamics/proveedor.py`.

## 11. Límites y pendientes reales

- Un volumen, un componente (agua), sin reacción, transferencia selectiva, momento ni sólidos. La región crítica (Tsat > 643.86 K) se rechaza como en H3.
- La presión con escalones queda rechazada hasta definir la regla de salto (impulso de trabajo y reinicialización).
- Funciones no suaves (abs, min, max, step) en caudales, calor o T exterior: también rechazadas en esta entrega.
- La vigilancia de fases es por puntos (§6). La certificación es por muestra, no continua.
- La identidad de funciones de t no unifica unidades equivalentes (§1.1).
- El agotamiento de una fase extraída se detecta cuando una etapa la necesita y ya no existe. El instante se acota a 1e-10·tf, y el último estado publicado conserva una traza (< 1e-6) de la fase que se agota.
- El coste de certificación crece linealmente con el número de muestras: ~45 ms por muestra en UV, con un máximo de 1001 muestras.
