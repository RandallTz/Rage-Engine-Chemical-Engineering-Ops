# Termodinámica del motor independiente — entrega H0/H1

14 de octubre de 2026. Responde a `frontend/CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md` (hitos H0 y H1) y a `frontend/PLAN_TERMODINAMICA_MOTOR.md`. Contrato HTTP: revisión 1 de `frontend/app/motor/contratoTermodinamica.ts`, **sin cambios de forma**.

> **Actualizado por H3** ([MOTOR_TERMODINAMICA_H3.md](MOTOR_TERMODINAMICA_H3.md)): PH, UP y UV están publicadas, la saturación TP ofrece `alternativas` y el ejemplo `ph-no-soportado` se retiró. Lo que este documento dice de esas especificaciones como «no soportadas» describe el estado de H1. TP no cambia.

Qué hay: evaluación puntual de un estado de **agua pura** a T/P dentro de un dominio monofásico verificado, con estabilidad certificada, y diagnósticos de contrato para todo lo demás (saturación, región crítica, sólido, mezclas, PH/UV/UP). No hay dinámica, flash bifásico ni especificaciones inversas: se publican como no soportadas.

| Pieza | Archivo |
| --- | --- |
| Física (sin contrato HTTP) | `core/agua_iapws95.py` |
| Contrato revisión 1 | `backend/motor_termodinamica.py` |
| Rutas (solo añadidas) | `backend/main.py`: `GET /motor/termodinamica/capacidades`, `POST /motor/termodinamica/evaluar` |
| Pruebas físicas y de contrato | `tests/validar_motor_termodinamica.py` (591 comprobaciones) |
| Ejemplos reales | `tests/generar_ejemplos_motor_termodinamica.py` → `docs/ejemplos/motor-termodinamica-*` |
| Python → JSON → TypeScript | `tests/verificar_contrato_motor_termodinamica.mjs` (validador TS real sobre las respuestas reales) |

`thermodynamics/proveedor.py` no se ha tocado (tiene un cambio de otra persona sin commitear). El adaptador nuevo es independiente y no lo importa.

---

## H0. Fundamento

### Relación fundamental y alcance

Para un sistema simple compresible en equilibrio interno, sin términos de superficie (capilaridad), eléctricos, magnéticos ni gravitatorios:

$$dU = T\,dS - P\,dV + \textstyle\sum_i \mu_i\,dn_i$$

$$H = U + PV,\qquad A = U - TS,\qquad G = H - TS = \textstyle\sum_i \mu_i n_i$$

Variables independientes naturales: U(S,V,n), H(S,P,n), A(T,V,n), G(T,P,n). El criterio de equilibrio depende de qué se fija: mínimo de G a T, P, n; mínimo de A a T, V, n; máximo de S a U, V, n. En H1 se fija T, P y n (un componente), así que el estado estable es el de **mínimo G**; no se aplica ese criterio a otras especificaciones.

IAPWS-95 es explícita en A(T, ρ): las propiedades salen de derivadas de φ = A/(nRT) = φ⁰(δ,τ) + φʳ(δ,τ), con δ = ρ/ρc y τ = Tc/T. Lo que se evalúa, todo por kg:

| Propiedad | Expresión |
| --- | --- |
| P | ρRT(1 + δφʳ_δ) |
| u | RTτ(φ⁰_τ + φʳ_τ) |
| h | u + P/ρ |
| s | R[τ(φ⁰_τ + φʳ_τ) − φ⁰ − φʳ] |
| f, g | RT(φ⁰ + φʳ);  f + P/ρ |
| c_v | −Rτ²(φ⁰_ττ + φʳ_ττ)  — derivada de u a **V y n constantes** |
| c_p | c_v + T(∂P/∂T)²_ρ / (ρ²(∂P/∂ρ)_T)  — derivada de h a **P y n constantes** |
| (∂P/∂ρ)_T, (∂P/∂T)_ρ, w | calculadas; las dos derivadas quedan en `Propiedades` para H2 |

El coeficiente `c_u` del modelo manual del motor **no** es c_p ni c_v: es la pendiente de una relación afín u(T) declarada por el usuario. Nada de este módulo lo reinterpreta.

### Separación de capas

| Capa | Qué es | En esta entrega |
| --- | --- | --- |
| Identidad química | CAS con dígito de control; nombre y símbolo son presentación | CAS obligatorio; `proveedorId` → no verificable |
| EOS | A(T, ρ) del fluido | IAPWS-95 |
| Propiedades de fase | u, h, v, s, c_p, c_v de una fase | de la EOS, en la rama elegida |
| Correlaciones | ajustes auxiliares | Psat, ρ′, ρ″ de `chemicals` (ajustes a la solución en precisión múltiple), **recomprobados** con la EOS en cada evaluación |
| Actividad | G^E de mezclas líquidas | no aplica (sustancia pura) |
| Estabilidad | ¿hay otra fase con menor G a la misma T, P? | TPD de sustancia pura (abajo) |

### Auditoría de lo que ya existe

| Adaptador | Qué suministra | Qué falta para el motor |
| --- | --- | --- |
| `thermodynamics/proveedor.py` (thermo `Chemical` + UNIFAC) | Psat, ΔHvap, c_p de líquido y gas ideal, ρ_L y σ por correlación, γ UNIFAC, ΔHf°/ΔGf°, densidad de vapor de gas ideal | Exige grupos UNIFAC a **todos** los componentes (el agua sola no debería necesitarlos). `Chemical.calculate(T,P)` muta estado compartido entre llamadas. Sin EOS, sin propiedades residuales, sin fugacidades, sin derivadas a V constante, sin estabilidad, sin especificaciones inversas. Densidad de mezcla por Amagat y vapor ideal. |
| `thermodynamics/entalpia.py` | h_L = Σx∫c_p,L dT; h_V = h_L + ΣyΔHvap (ref. 298.15 K) | Camino de gas/líquido ideal; sin dependencia con P, sin u ni s, sin referencia común con una EOS. Útil para el laboratorio, no como cierre del motor. |
| `thermodynamics/elv.py`, `ell.py` | Burbuja/rocío por Raoult modificada; ELL por igualdad de actividades con estabilidad | Ambos sobre `proveedor.py`; vapor ideal. Fuera del alcance de H1. |
| `core/vapor_if97.py` | IF97 regiones 1, 2, 4: T_sat, P_sat, h′, h″ (verificado contra tablas IF97) | Solo entalpía en saturación; sin región 3, sin u/s/v, sin flash U/V. Se usa aquí solo como **contraste independiente**. |
| `chemicals.iapws` 1.5.2 (IAPWS-95) | φ⁰, φʳ y derivadas hasta 2.º orden (3.º en φʳ), ajustes de Psat/ρ′/ρ″, `iapws95_rho(T,P)` | Funciones puras, sin estado. **No** certifica estabilidad: `iapws95_rho` elige la rama comparando P con su Psat. Este módulo no usa esa elección ni `iapws95_properties`. |
| `thermo.phases.IAPWS95*`, flashes de `thermo` | Fases y flashes genéricos | No auditados ni usados. Su presencia no es soporte. |

### Versión, referencia y procedencia

- Modelo publicado: `agua-iapws95`, versión `1`. Fórmulas IAPWS R6-95(2018) / Wagner y Pruß (2002).
- La librería debe ser `chemicals == 1.5.2` (la auditada). Si la versión cambia, o si al arrancar no reproduce los valores publicados (error relativo > 1e-8), **el catálogo sale vacío** y toda petición recibe `MOTOR_ESTADO_MODELO_NO_PUBLICADO`. Así una actualización de dependencias no cambia en silencio la identidad física del modelo.
- Referencia de energía y entropía: la de IAPWS-95, u = 0 y s = 0 del líquido saturado en el punto triple. Id: `iapws95-u0-s0-liquido-saturado-punto-triple`. **No coincide** con la referencia del modelo manual ni con la de `entalpia.py` (298.15 K): mezclar valores absolutos entre modelos es un error; las diferencias de h o u dentro de un mismo modelo no dependen de la referencia.
- Aislamiento: todo son funciones puras de (T, ρ). La prueba evalúa A, B, A y exige respuestas idénticas byte a byte.

---

## H1. Estado puro monofásico: decisiones físicas

### Dominio publicado

T ∈ [273.16, 1073.15] K, P ∈ [100 Pa, 100 MPa], excepto la banda crítica.

- **Sólido.** Con T ≥ 273.16 K y P ≤ 100 MPa ningún hielo es estable: la fusión del hielo Ih baja de 273.16 K al subir P, y los hielos III, V y VI aparecen por encima de 209.9 MPa (IAPWS R14-08). El sólido queda fuera **por dominio**, no por la búsqueda de estabilidad; por eso `alcance` no lo incluye y una petición a −5 °C sale `no_soportado` con `MOTOR_ESTADO_FUERA_DE_DOMINIO`, sin reclasificarse como líquido.
- **T máxima 1073.15 K**: límite de la región 2 de IF97, para que todo el dominio tenga contraste independiente. IAPWS-95 llega más lejos; se ampliará cuando haga falta y se compruebe.
- **Banda crítica excluida**: T ∈ [0.995, 1.005]·Tc = [643.86, 650.33] K **y** P ∈ [0.95, 1.05]·Pc = [20.96, 23.17] MPa. Ahí la compresibilidad diverge, la densidad a T/P está mal condicionada y el margen de estabilidad se anula. Respuesta: `no_soportado`, `MOTOR_ESTADO_REGION_CRITICA`.

El rectángulo de `capacidades.dominio` es una envolvente: la banda crítica y la saturación se comprueban en cada petición.

### Tipo de fase y régimen

| Condición | tipo | regimen |
| --- | --- | --- |
| T < Tc, P > Psat(T) | `liquido` | `ordinario` (también si P > Pc: líquido comprimido) |
| T < Tc, P < Psat(T) | `vapor` | `ordinario` |
| T ≥ Tc, P ≤ Pc | `vapor` | `ordinario` |
| T > Tc, P > Pc | `fluido` | `supercritico` |

Por encima de Tc no hay transición de fase; llamar `vapor` al fluido de baja presión es una convención, declarada aquí. Un estado supercrítico tiene una sola fase `fluido`, sin calidad de vapor.

### Saturación: T/P indeterminado

Si |P/Psat(T) − 1| ≤ 1e-6, el punto está en la curva de saturación: líquido y vapor coexisten y T, P no fijan cuánto hay de cada uno. Respuesta `incompleto`, `MOTOR_ESTADO_SATURACION_INDETERMINADA`, `evaluacion: null`. **No se elige** fracción de vapor 0, 0.5 ni 1. El diagnóstico no lleva `alternativas` porque PH/UV/UP aún no se admiten (el contrato las pide «cuando se admitan»); las tendrá en H3.

La banda 1e-6 cubre un valor de Psat tecleado con 7 cifras. Fuera de ella el estado queda determinado y la estabilidad lo certifica con margen (a P = Psat·(1 ± 3e-6) las pruebas exigen líquido/vapor estable).

Ejemplo útil: 100 °C y 101.325 kPa es **vapor**, porque Psat(373.15 K) = 101 418 Pa > 101 325 Pa (el agua hierve a 1 atm a 373.124 K). Está en `docs/ejemplos/motor-termodinamica-vapor-100C-1atm-*`.

### Densidad

Por debajo de Tc hay dos ramas monofásicas: vapor ρ ∈ (0, ρ″] y líquido ρ ∈ [ρ′, ρ(1 GPa)]. Se elige la rama comparando P con Psat (Maxwell, ver abajo) y se resuelve P(T, ρ) = P en ella con Brent (rtol 1e-15) y tres pasos de Newton que no pueden salir de la rama. Por encima de Tc, una rama.

### Estabilidad: criterio, alcance y tolerancia

Para una sustancia pura a T fija, la distancia al plano tangente

$$\mathrm{TPD}(\rho) = \rho\,[f(T,\rho) - g^*] + P^*,\qquad g^* = g(T,\rho^*),\ P^* = P(T,\rho^*)$$

es la energía de Helmholtz por volumen menos su tangente en el estado ρ*. Si existe una densidad con TPD < 0, una fase de esa densidad tendría menor G a la misma T y P*: el estado no es estable. Se usa P* de la EOS (no la P pedida) para que TPD(ρ*) = 0 exactamente y el error de resolver ρ no se confunda con margen.

- **Alcance de la búsqueda**: las ramas monofásicas de arriba, hasta ρ(1 GPa) (límite de validez de IAPWS-95), 400 puntos log-espaciados por rama más ρ*, y refinamiento acotado de cada mínimo local de la malla. Unas 840 evaluaciones; ~4 ms por estado.
- **Por qué no se barre la campana**: entre ρ″ y ρ′ IAPWS-95 no representa estados homogéneos físicos (a 300 K y 300 kg/m³ da P ≈ −1.5·10²³ Pa) y un barrido ingenuo devuelve TPD ≈ −10²² Pa, una «inestabilidad» falsa. Ningún estado homogéneo de esa región es estable frente a la separación en las dos fases saturadas, así que excluirla no quita candidatos físicos. Es una limitación declarada en `metodo`.
- **Tolerancia**: residuo = max(0, −min TPD)/P* ≤ 1e-9. Además (∂P/∂ρ)_T > 0 en ρ*.
- **No es un sello**: la prueba fuerza líquido sobrecalentado (0.9·Psat) y vapor subenfriado (1.05·Psat) a 300, 450 y 600 K y exige que el certificado los rechace (residuo > 1e-6).
- Lo que no se afirma: un mínimo global fuera de las ramas buscadas, ni nada sobre fases sólidas (las excluye el dominio).

### Política de fase

- `cantidad: monofasico`: el estado estable de H1 siempre tiene una fase; se verifica y se publica `politica_fases`. En saturación sale `incompleto`, no una fase forzada.
- `tiposPermitidos`: si el estado estable calculado no está en la lista → `invalido`, `MOTOR_ESTADO_FASE_INCOMPATIBLE`. **No** se busca solo la rama permitida para llamarla estable.
- `cambioInterno: prohibido`: en una consulta puntual sin trayectoria se registra `cambio_interno` como `no_evaluable` (residuo null). No implica monofásico.
- No hay ramas metastables forzadas.

### Verificaciones publicadas

| id | residuo (adimensional) | tolerancia |
| --- | --- | --- |
| `estabilidad` | max(0, −min TPD)/P* | 1e-9 |
| `dominio` | null: comprobación de pertenencia (motivo con límites) | null |
| `ecuacion_estado` | \|P(T,ρ) − P\| / max(P, ρ(∂P/∂ρ)_T). Escala con el módulo de compresibilidad porque la presión del líquido es rígida | 1e-12 |
| `identidad_h_u_Pv` | \|h − u − Pv\|/(RT), con la P especificada | 1e-9 |
| `derivadas` | max(\|c_p − (∂h/∂T)_P\|/c_p, \|c_v − (∂u/∂T)_ρ\|/c_v), analíticas frente a diferencias centradas de paso 1e-5·T re-resolviendo ρ en la misma rama. `no_evaluable` si a T ± dT la P cae en otra rama | 1e-6 |
| `saturacion` (T < Tc) | Maxwell: max(\|g′−g″\|/(RT), \|P(ρ″)−Psat\|/Psat, \|P(ρ′)−Psat\|/(ρ′(∂P/∂ρ)_T′)). El motivo da Psat, ρ′, ρ″ y \|P/Psat − 1\| | 1e-9 |
| `reconstruccion_material` | una fase con la composición global: 0 exacto | 1e-12 |
| `masa_molar` (si se declara) | \|M_decl − M\|/M | 1e-7 |
| `politica_fases` (si se restringe) | null | null |
| `cambio_interno` (si prohibido) | `no_evaluable`, null | null |

`equilibrio` no aparece porque nunca hay dos fases en H1. Si una verificación con residuo no se cumple, el estado no se publica (`no_convergente`).

### Masa molar y bases

La masa molar usada es la de IAPWS-95, 18.015268 g/mol, con su fuente. Una masa molar declarada que difiera más de 1e-7 relativo se rechaza como `MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA`: es la misma tolerancia que aplica el cliente, que si no rechazaría la respuesta. Consecuencia práctica: **18.015 g/mol se rechaza**. Con un único componente las fracciones molar y másica de la fase coinciden y valen 1; la de volumen también vale 1 porque hay una fase.

---

## Contrato: lo que hace el servidor con cada petición

El cuerpo se lee como JSON libre, no con Pydantic, para que cada problema conocido salga como respuesta del contrato con código y ruta en vez de un 422. HTTP siempre 200 para un JSON válido. Un rechazo siempre lleva `evaluacion: null` y al menos un diagnóstico; con varios problemas, el estado es el más grave por este orden: `invalido` > `no_soportado` > `incompleto` > `no_convergente`. Se diagnostican todos de una vez (datos que faltan y modelo no publicado, por ejemplo).

| Código | Estado | Cuándo |
| --- | --- | --- |
| `MOTOR_ESTADO_FORMA_INVALIDA` | invalido | tipo JSON equivocado, ID no entero positivo, texto vacío |
| `MOTOR_ESTADO_CAMPO_NO_ADMITIDO` | invalido | cualquier clave no prevista (no se ignoran) |
| `MOTOR_ESTADO_SOBREESPECIFICADO` | invalido | campo de otra especificación, p. ej. `h` en una TP |
| `MOTOR_ESTADO_REVISION` | invalido | `revision` ≠ 1 |
| `MOTOR_ESTADO_DATO_SIN_DECLARAR` | incompleto | campo ausente, `valor: null`, fracción ausente (una especie ausente se declara con 0) |
| `MOTOR_ESTADO_DATO_INVALIDO` | invalido | no numérico, no finito, fracción negativa |
| `MOTOR_ESTADO_UNIDAD_INCOMPATIBLE` | invalido | unidad fuera de la tabla del contrato |
| `MOTOR_ESTADO_FUERA_DE_MAGNITUD` | invalido | T, P, V ≤ 0 (T absoluta), cantidad negativa o total nulo |
| `MOTOR_ESTADO_COMPOSICION_NO_NORMALIZADA` | invalido | Σ ≠ 1 (tolerancia 1e-10); no se renormaliza |
| `MOTOR_ESTADO_COMPONENTE_DESCONOCIDO` | invalido | fracción o cantidad para un ID inexistente |
| `MOTOR_ESTADO_ID_DUPLICADO`, `MOTOR_ESTADO_IDENTIDAD_DUPLICADA` | invalido | ID repetido; dos IDs con el mismo CAS |
| `MOTOR_ESTADO_IDENTIDAD_SIN_DECLARAR` | incompleto | sin `identidadQuimica` |
| `MOTOR_ESTADO_CAS_INVALIDO` | invalido | formato o dígito de control |
| `MOTOR_ESTADO_IDENTIDAD_NO_VERIFICABLE` | no_soportado | hay `proveedorId`: este modelo solo verifica CAS |
| `MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA` | invalido | ver arriba |
| `MOTOR_ESTADO_POLITICA_INVALIDA`, `MOTOR_ESTADO_ESPECIFICACION_DESCONOCIDA`, `MOTOR_ESTADO_BASE_INVALIDA` | invalido | valores fuera de las uniones del contrato |
| `MOTOR_ESTADO_MODELO_NO_PUBLICADO` | no_soportado | id/versión no publicados (o librería no auditada) |
| `MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO` | no_soportado | CAS distinto del agua, **también con fracción 0** |
| `MOTOR_ESTADO_ESPECIFICACION_NO_SOPORTADA` | no_soportado | PH, UV, UP (aún no); `alternativas: [["T","P","composicion"]]` |
| `MOTOR_ESTADO_FUERA_DE_DOMINIO` | no_soportado | T o P fuera del rectángulo; ruta a la magnitud culpable |
| `MOTOR_ESTADO_REGION_CRITICA` | no_soportado | banda crítica |
| `MOTOR_ESTADO_SATURACION_INDETERMINADA` | incompleto | T/P en la curva de saturación |
| `MOTOR_ESTADO_FASE_INCOMPATIBLE` | invalido | estado estable fuera de `tiposPermitidos` |
| `MOTOR_ESTADO_NO_CONVERGENTE`, `MOTOR_ESTADO_VERIFICACION_FALLIDA` | no_convergente | densidad o certificación fallidas |

Rutas: `declaracion.especificacion.T`, `componentes.<id>.identidadQuimica.cas`, `declaracion.especificacion.composicion.fracciones.<id>`… Los IDs de componente vuelven intactos (un componente con id 7 devuelve `composicionMolar: {"7": 1}`). Los IDs de fase son `liquido-1`, `vapor-1`, `fluido-1`.

Las PH/UV/UP se validan igualmente (unidades, cantidades, ceros) antes de declararse no soportadas, para que la interfaz pueda preparar la especificación desde ya.

---

## Evidencia

Ejecutar desde la raíz:

```
python tests/validar_motor_termodinamica.py                 # 591 comprobaciones
python tests/generar_ejemplos_motor_termodinamica.py        # regenera docs/ejemplos/motor-termodinamica-*
node tests/verificar_contrato_motor_termodinamica.mjs       # 21 comprobaciones con el validador TS
```

| Comprobación | Resultado medido |
| --- | --- |
| Valores publicados IAPWS R6-95(2018): tabla 6 (9 derivadas de φ a 500 K, 838.025 kg/m³), tabla 7 (P, c_v, w, s en 11 estados), tabla 8 (Psat, ρ′, ρ″, h′, h″, s′, s″ a 275, 450, 625 K) | 74 valores, error relativo máximo **3.8e-9** (los publicados tienen 9 cifras) |
| IF97 como formulación independiente (regiones 1, 2 y 3; la región 3 verificada antes contra la tabla 33 de IF97), 187 estados de líquido, vapor y supercrítico en todo el dominio | \|Δv/v\| ≤ **4.9e-4**, \|Δh\| ≤ **0.51 kJ/kg**, \|Δs\| ≤ **0.83 J/(kg·K)**; la fase coincide con la región IF97 en todos. Tolerancias de la prueba: 1e-3, 1 kJ/kg, 2 J/(kg·K) |
| h = u + Pv, g = h − Ts, relación de Maxwell (∂s/∂ρ)_T = −(∂P/∂T)_ρ/ρ², (∂s/∂T)_P = c_p/T, c_p > c_v > 0 | en 6 estados de las tres familias |
| Estabilidad | rechaza los 6 metastables forzados; acepta a Psat·(1 ± 3e-6); rechaza Psat·(1, 1 ± 5e-7) como saturación |
| Contrato | 29 rechazos con estado, código, ruta, propietario y eco del id; unidades K/°C/°F y Pa/kPa/bar dan el mismo estado; base másica; null presente en la serialización; JSON sin NaN |
| 25 °C, 1 bar | ρ = 997.047 kg/m³, h = 104.92 kJ/kg, s = 0.3672 kJ/(kg·K), c_p = 4.1813 kJ/(kg·K) |

Los ejemplos de `docs/ejemplos/motor-termodinamica-*` salen de ejecutar los endpoints; ningún número está escrito a mano. Casos: líquido a 25 °C, vapor a 100 °C y 1 atm, líquido comprimido 600 K/50 MPa con política monofásica, supercrítico 900 K/50 MPa, saturación indeterminada, fase incompatible, región crítica y PH no soportada.

Las dos referencias no son independientes en el sentido físico fuerte: IF97 está ajustada a IAPWS-95. Lo que aportan es independencia de **implementación y forma funcional** (otra ecuación, otras regiones, otra resolución de densidad), suficiente para detectar errores de rama, unidades o referencia. La validez experimental de IAPWS-95 es la que documenta su publicación.

---

## Para Codex

- **Rutas**: `GET /motor/termodinamica/capacidades` y `POST /motor/termodinamica/evaluar`, como espera `servicioTermodinamica.ts`. Respuestas con la forma exacta de revisión 1; los campos opcionales (`cp`, `cv`, `motivo`, `alternativas`, `cas`) se **omiten** cuando no proceden, nunca van como null; `evaluacion: null` y `residuo: null` sí van explícitos.
- **Capacidad publicada**: `agua-iapws95` v`1`, `especificaciones: ["TP"]`, `fases: ["liquido","vapor","fluido"]`, `componentesCAS: ["7732-18-5"]`, `dinamica: false`.
- **Hallazgo en `validarRespuestaEstado`**: si la solicitud no declara `masaMolar`, el validador acepta cualquier `masaMolarKgMol > 0` del servidor (solo contrasta cuando el usuario la declara). Una respuesta con 0.018 kg/mol para el agua pasaría. Opcional: contrastar contra un catálogo o al menos exigir coherencia con el CAS.
- **18.015 g/mol se rechaza** (tolerancia 1e-7, la vuestra). Si la interfaz rellena masas molares redondeadas, conviene no enviarlas o enviar la del modelo.
- **`proveedorId`** con este modelo → `no_soportado`. Enviar solo el CAS.
- **Saturación** sin `alternativas` hasta que PH/UV/UP estén publicadas; la interfaz puede leer `MOTOR_ESTADO_SATURACION_INDETERMINADA` y explicar que falta una especificación de energía o volumen.

## Pendiente (no publicado)

- **H2/H4 necesitan antes el contrato `validar`/`resolver` del ensamblaje** (contrato §C): estados diferenciales y algebraicos, inicialización, recuento. No se ha empezado; la evaluación de esta entrega se llama localmente (`core.agua_iapws95.evaluar_TP`) y está pensada para que el coordinador numérico la invoque sin HTTP.
- **H3**: saturación con fracción de fase, PH/UV/UP para agua (inversión en T, ρ; TPD a la especificación correspondiente, no G), reconstrucción de U/V. Entonces se añadirán `alternativas` y la verificación `equilibrio`.
- Derivadas para H2 ya calculadas y no publicadas en revisión 1: (∂P/∂ρ)_T, (∂P/∂T)_ρ, w. Publicarlas exige ampliar el contrato.
- Región crítica, T > 1073.15 K y P > 100 MPa: fuera hasta tener verificación específica.
- Mezclas (H5/H6), sólidos, reacción y electrolitos: sin modelo; cualquier CAS distinto del agua sale `no_soportado`.
