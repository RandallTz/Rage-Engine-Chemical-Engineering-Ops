# Diagramas de equilibrio T–xy / P–xy del motor (D0–D3 y parte física de D5)

Implementación del lado backend de `frontend/PLAN_DIAGRAMAS_EQUILIBRIO_MOTOR.md`. D4 (lectura y vista) y la
integración son de Codex. No se tocó el frontend, `/laboratorio` ni `thermodynamics/proveedor.py`. Sin commit
ni push. **Recarga:** reiniciar el servicio (`uvicorn backend.main:app`); `backend/main.py` solo recibe las dos
rutas nuevas (aditivo).

## 1. Qué hay que hacer en el frontend

1. **Sincronizar la copia del contrato v2.** `docs/contratos/contratoEnsamblajeV2.ts` ganó el campo opcional
   `resultados.procedenciaModelo`. El verificador `frontend/verificar_consolidacion_multifasica.mjs` exige que
   la copia de `frontend/app/motor/` sea idéntica, y hoy falla solo por eso. Con la copia sincronizada (probado
   sobre una copia temporal del frontend, fuera del repositorio) pasa sus 237 comprobaciones. Los otros 20
   verificadores de `npm run test:motor-fundamental` pasan sin cambios.
2. **Copiar el contrato nuevo** `docs/contratos/contratoDiagramasEquilibrio.ts`, con el mismo control de
   igualdad.
3. Leer los diagramas con `GET /motor/termodinamica/diagramas/capacidades` y
   `POST /motor/termodinamica/diagramas/trazar`, un corte por petición (T–xy y P–xy en paralelo, cada una con
   su propio éxito o fallo).
4. Comparar un diagrama con una trayectoria solo si `respuesta.identidad.huellaModelo` es igual a la `huella`
   del paquete del volumen en `resultados.procedenciaModelo`. Las ejecuciones antiguas sin
   `procedenciaModelo` no permiten verificar la coincidencia: hay que ofrecer volver a resolver. También se
   puede enviar `huellaModeloEsperada`; si no coincide, la respuesta es `invalido` con
   `MOTOR_DIAG_HUELLA_DISTINTA`.

## 2. Contrato (D0)

`docs/contratos/contratoDiagramasEquilibrio.ts`, revisión 1, independiente del ensamblaje. La ruta existente
`GET /motor/termodinamica/diagrama` (P–T del agua con hielo) no cambia.

**Solicitud** (`SolicitudDiagrama`): exactamente dos componentes con CAS, `modelo` (el mismo paquete del
volumen; nunca se sustituye), `componenteEjeId`, `corte` (`{tipo: 'Txy', P}` o `{tipo: 'Pxy', T}` con unidades:
P en Pa, kPa o bar; T en K, degC o degF), `intervaloComposicion` (fracción molar del componente del eje, dentro
de [0, 1]), `resolucion` (`exploratoria` | `refinada`) y, opcional, `huellaModeloEsperada`. Sin tanque, masa,
tiempo ni ejemplo: el diagrama es una consulta intensiva. Los campos de más se rechazan.

**Respuesta** (`RespuestaDiagrama`):

| Campo | Contenido |
|---|---|
| `estado` | `completo` (todo el intervalo cubierto por segmentos certificados o explorado y sin L–V estable), `parcial` (hay huecos por dominio, convergencia o presupuesto), `no_convergente` (ningún punto), `invalido`, `incompleto`, `no_soportado` |
| `identidad` | modelo, `huellaModelo` (datos y parámetros del paquete), `firmaConsulta` (clave física: paquete, huella, especies, corte en SI, intervalo en el componente de menor CAS, perfil y versión del trazador; **no** incluye el componente del eje ni las unidades), versión del trazador |
| `condicion` | corte original intacto y `corteSI`, componentes con CAS, eje, intervalo, perfil |
| `puntos` | `PuntoCoexistencia`: T [K], P [Pa], `xEje`, dos **fases límite** (`liquido-limite`, `vapor-limite`) con composición molar por ID, `certificado` y `origen` |
| `ramas` | una rama `lv-1` con segmentos de puntos certificados consecutivos; ningún segmento cruza un hueco |
| `puntosEspeciales` | `extremo_puro`, `azeotropo` (refinado x = y, con `clase` minimo/maximo/tangente), `encuentro_otra_fase` (frontera L–V con la fase competidora identificada) y `limite_dominio` |
| `candidatosDescartados` | soluciones que no pasaron la certificación (p. ej. L–V metastables en zona LL): solo diagnóstico, **no se dibujan** |
| `incidencias`, `cobertura` | huecos con motivo (`sin_lv_estable`, `fuera_de_dominio`, `no_convergente`, `presupuesto`), tramos publicados, presupuesto consumido y reproducibilidad entre los dos sentidos de recorrido |
| `evidencia` | nivel del par o del paquete (ver §5), independiente del certificado numérico |
| `diagnosticos` | `MOTOR_DIAG_*` con ruta; también avisos (`aviso`) en respuestas con puntos |

**Fases límite.** Burbuja y rocío son límites con cantidad de fase → 0, así que no son `FaseEvaluada`: no
llevan fracciones de fase y el lector de estados no se debilita para admitirlas. El diagrama no fija β.

**Diagnósticos** (estables, con ruta): `MOTOR_DIAG_REVISION`, `MOTOR_DIAG_DATO_INVALIDO`, `MOTOR_DIAG_UNIDAD`,
`MOTOR_DIAG_PAQUETE_NO_DISPONIBLE`, `MOTOR_DIAG_PARAMETRO_AUSENTE`, `MOTOR_DIAG_COMPONENTES_NO_SOPORTADO`,
`MOTOR_DIAG_COMPONENTE_NO_SOPORTADO`, `MOTOR_DIAG_FUERA_DE_DOMINIO`, `MOTOR_DIAG_NO_CONVERGENTE`,
`MOTOR_DIAG_FASE_COMPETIDORA`, `MOTOR_DIAG_PRESUPUESTO`, `MOTOR_DIAG_HUELLA_DISTINTA`. Están reservados en el
contrato pero sin uso todavía: `MOTOR_DIAG_REGION_CRITICA` (la región crítica la excluye el dominio del paquete)
y `MOTOR_DIAG_RAMA_AMBIGUA` (las discrepancias entre sentidos de recorrido se publican como incidencia
`rama_ambigua`). Todo rechazo conocido es una respuesta del protocolo con estado `200`, no un 422.

## 3. Fundamento y operación compartida (D1)

`core/coexistencia_lv.py` es la operación compartida. Solo usa la interfaz pública del paquete:
`mu(tipo, T, P, x, idx)`, `prueba_estabilidad`, `T_saturacion`/`P_saturacion`, `dominio`, `equilibrio_TP` y
`fase`. No contiene ninguna fórmula de actividad, presión de vapor ni fugacidad: la condición de equilibrio es
`μ_i^L(T, P, x) = μ_i^V(T, P, y)` del propio paquete, así que el Poynting y cualquier otra contribución entran
porque están en μ. No se impone `K = γ Psat/P`. Un adaptador basado en EOS que exponga `mu` sirve igual.

- Punto regular (T–xy): Newton en `(ln T, logit y)` a P y x fijos; P–xy: `(ln P, logit y)` a T fija.
- Azeótropo: Newton en `(ln T o ln P, logit x)` con y = x.
- Extremo puro: saturación del componente en el MISMO paquete (`T_saturacion`/`P_saturacion`). No se evalúa
  `log 0` ni se inserta una composición mínima ficticia.
- Semilla genérica: el flash TP certificado del paquete, por bisección de la T (o P) donde aparece vapor.
  Si no hay cambio de fase dentro del dominio, se declara fuera de dominio y no se toma como fallo numérico.
- **Certificado por punto**:
  - `igualdad_mu`: |Δμ|/RT ≤ 1e-10 para cada especie presente;
  - `normalizacion`;
  - `condicion_fija`: P del punto igual a la del corte (T–xy), o T igual a la del corte (P–xy);
  - `distincion_fases`: diferencia de volumen molar entre L y V;
  - estabilidad por plano tangente con la μ común frente a vapor (mínimo analítico) y líquido de prueba (malla de
    1361 puntos con refinamiento). La malla con refinamiento no demuestra el mínimo global y así lo dice el
    certificado.

`core/diagramas_equilibrio.py` es el trazador. La variable de continuación es x del líquido sobre una malla de
Chebyshev, y se recorre en los dos sentidos:
- el punto anterior sirve de semilla y el paso se subdivide si el Newton falla; si aun así falla, se recurre a
  la semilla por flash;
- se refina donde saltan T, ln P o la composición del vapor;
- las fronteras estable/inestable y de dominio se localizan por bisección (14 pasos);
- los azeótropos se buscan por cambio de signo **o** mínimo de |y − x|, para no perder contactos tangentes.

Las líneas entre puntos son interpolación visual; los segmentos nunca cruzan un hueco. No hay ninguna rama de
código por paquete, especie ni ejemplo.

**Huella**: `Sistema.huella()` (`core/mezclas.py`) es un sha256 de paquete y versión, CAS, datos de cada especie
(Psat, cp, v_L, M, rangos, fuentes), modelo de líquido con sus parámetros binarios, procedencia, referencia,
dominio y tolerancias. No depende del orden de los componentes y cambia si cambia cualquier dato aunque el
`modelo.id` siga igual. El agua (`agua-iapws95`) tiene su propia huella (formulación y versión auditada).

## 4. Capacidades implementadas (lista explícita)

| Capacidad | Estado |
|---|---|
| T–xy a P fija y P–xy a T fija, dos componentes | implementado |
| Paquetes `mezcla-ideal`, `nrtl-chemsep` (pares con parámetros), `nrtl-lle-agua-butanol` | implementado |
| Extremos puros desde la saturación del mismo paquete | implementado |
| Azeótropos homogéneos (cruce y contacto tangente), clase mínimo/máximo | implementado |
| Detección de competencia de otro líquido, frontera localizada y fase competidora identificada | implementado |
| Límites de dominio con bisección, sin extrapolar | implementado |
| Intervalo de composición parcial, eje en cualquiera de los dos componentes | implementado |
| Reproducibilidad entre sentidos de recorrido publicada | implementado |
| Presupuesto de evaluaciones y tiempo con resultado parcial | implementado |
| Huella del modelo en diagramas y en `procedenciaModelo` del ensamblaje v2 | implementado |
| Perfiles `exploratoria` (41 puntos base) y `refinada` (121), publicados en capacidades | implementado |

Perfiles: `saltoMaximoT` [K] (T–xy) y `saltoMaximoLnP` (P–xy) disparan el refinamiento. Una semilla por flash
cuenta como 45 evaluaciones. Las tolerancias de certificación son las mismas en ambos perfiles y el frontend no
puede elegirlas.

## 5. Evidencia

`evidencia.nivel` sale de las capacidades v2. Etanol–agua es `contrastada` (azeótropo); los demás pares ChemSep,
`cualitativa`. Mezcla ideal: `contrastada` frente a su expresión analítica. Agua/1-butanol: L–V `cualitativa`
(el ajuste es de LLE). El nivel de evidencia es independiente del certificado numérico de cada punto.

## 6. Pruebas físicas (D5) — `python tests/validar_motor_diagramas_equilibrio.py`: 78 comprobaciones OK

| Caso | Resultado |
|---|---|
| Ideal benceno–tolueno T–xy frente a Raoult + Poynting resuelto aparte | dT < 1e-8 K, dy < 1e-10 |
| Ideal P–xy a 370 K | dP/P < 1e-10 |
| Extremos puros frente a la saturación del paquete | idénticos (< 1e-9 K) |
| Extremos puros frente a NIST (benceno, tolueno, etanol, agua, metanol) | < 0.3 K |
| Metanol–agua (sin azeótropo en la literatura) | completo, ningún azeótropo fabricado |
| Orden de componentes invertido | misma física (< 1e-7 K) y misma firma |
| Eje en el otro componente | xEje = 1 − x, misma firma, azeótropo invariante |
| 1.01325 bar frente a 101325 Pa | misma firma; corte original conservado |
| Azeótropo etanol–agua frente a α = 1 con ln γ, Psat y Poynting (otra vía) | dx < 1e-7, dT < 1e-7 K |
| Azeótropo frente a la literatura (78.15 °C, x 0.894) | 78.07 °C, x 0.881, mínimo de T. Los parámetros ChemSep vienen de ajustes a VLE: **no** es una validación predictiva independiente |
| P–xy etanol–agua a 350 K | un azeótropo de P máxima |
| Agua/1-butanol a 1 atm | rama L–V interrumpida entre x = 0.6583 y 0.9789. Los encuentros a 367.2839 K coinciden (< 1e-4) con el L–L–V que resuelve el motor multifásico por otro camino (meseta de `equilibrio_PH`). La fase competidora es el otro líquido. Heteroazeótropo 94.13 °C frente a 93.0 °C de la literatura (± 2 K) |
| Agua pura por encima del techo del paquete (373 K) | hueco `fuera_de_dominio` y `limite_dominio`, sin extrapolar |
| Trazas junto a x = 0 y 1 (refinada) | puntos a < 1e-3 de ambos extremos |
| Dos sentidos de recorrido | diferencias < 1e-8 K y < 1e-10 en y |
| Presupuesto agotado | `parcial`, hueco `presupuesto`, solo puntos certificados |
| Controles negativos del certificado | potencial, normalización y condición fija alterados → `no_cumple`; raíz L–V en zona LL → μ igual pero `inestable`, competidor líquido |
| 12 rechazos estructurados | tres componentes, par sin parámetros, agua pura, P o T fuera de dominio, unidad, dato nulo, intervalo, eje, revisión, campo de más, huella |
| Muestras LV reales del ensamblaje v2 (calentamiento a P constante) | (T, x, y) sobre su T–xy (dT < 1e-6 K) y regla de la palanca con β publicado (< 1e-9) |
| Huella del ensamblaje frente a la del diagrama | iguales |
| Estados estáticos L–V a T fija | sobre su P–xy (< 1e-9). El ensamblaje no tiene un caso isotermo dinámico: queda declarado así |

Coste medido (este equipo, en frío):

| Sistema | exploratoria | refinada |
|---|---|---|
| benceno–tolueno | 0.6 s, 41 puntos | 0.7 s, 137 puntos |
| etanol–agua | 0.6 s, 47 puntos | 1.0 s, 142 puntos |
| agua–butanol (competencia LL) | 1.4 s, 18 puntos | 2.2 s, 48 puntos |

Otros: `node tests/verificar_contrato_diagramas.mjs` compila los 11 pares de ejemplo contra el contrato, con
controles negativos, y comprueba los invariantes de cada respuesta (285 puntos). Los ejemplos están en
`docs/ejemplos/motor-diagramas/` y se generan con `python tests/generar_ejemplos_motor_diagramas.py`.

## 7. Límites pendientes

- Solo binarios. Una hoja de tres componentes recibe `MOTOR_DIAG_COMPONENTES_NO_SOPORTADO`; no se elimina ni se
  renormaliza ningún componente.
- Se detecta y explica el encuentro con otra fase, pero no se trazan las regiones L–L, L–L–V ni SLE.
- La continuación es en x del líquido; no hay longitud de arco. Un pliegue en x se manifestaría como fallo o
  hueco declarado, no se seguiría.
- La estabilidad es una prueba en malla con refinamiento, no una demostración del mínimo global.
- Región crítica: excluida por los paquetes (T ≤ 0.9 Tc), nunca extrapolada. Vapor ideal hasta 5 bar.
- `agua-iapws95` y el hielo son de un componente: su diagrama es P–T (ruta existente).
- No hay trabajos persistentes ni progreso en streaming: los cortes medidos tardan menos de 3 s. El presupuesto es
  cooperativo entre puntos; abortar el HTTP no detiene el cálculo en curso.
- D4 (lector, vista, marcadores, caché, exportación) y la validación de extremo a extremo con la interfaz son de
  Codex.

## 8. Archivos

Nuevos: `core/coexistencia_lv.py`, `core/diagramas_equilibrio.py`, `backend/motor_diagramas.py`,
`docs/contratos/contratoDiagramasEquilibrio.ts`, `tests/validar_motor_diagramas_equilibrio.py`,
`tests/generar_ejemplos_motor_diagramas.py`, `tests/verificar_contrato_diagramas.mjs`,
`docs/ejemplos/motor-diagramas/*`, este documento.
Modificados (aditivo): `backend/main.py` (2 rutas), `core/mezclas.py` (`Sistema.huella`),
`core/paquetes_volumen.py` (`huella` de los paquetes), `backend/motor_ensamblaje_v2.py`
(`resultados.procedenciaModelo`), `docs/contratos/contratoEnsamblajeV2.ts` (tipo de `procedenciaModelo`),
`docs/ejemplos/motor-v2/*` (regenerados: solo ganan `procedenciaModelo`).
