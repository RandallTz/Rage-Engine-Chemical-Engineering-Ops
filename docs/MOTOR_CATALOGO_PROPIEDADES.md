# F2 · Catálogo y propiedades (entrega acumulativa)

Entrega de la fase F2 de `frontend/ROADMAP_MOTOR_MULTIFISICO.md`, con el formato de
`frontend/COORDINACION_CLAUDE_CODEX_MOTOR.md`. Cambios en núcleo, backend, pruebas, contratos canónicos y `docs/`.
No se tocó `frontend/`, `/laboratorio` ni `thermodynamics/proveedor.py`. Sin commit, push ni despliegue. No se
actualizó ninguna dependencia ni se modificó ningún dato.

**Recarga:** reiniciar el servicio (`uvicorn backend.main:app`). Debe responder la ruta nueva `GET /motor/catalogo`.
Las capacidades existentes no cambian (§5).

## 1. Estado por hito

| Hito | Estado | Evidencia |
|---|---|---|
| F2.1 auditoría y registro extensible | **Backend verificable** | Registro único `core/catalogo.py`; identidad, datos puros y requisitos de paquete separados (§2–§3) |
| F2.2 propiedades con unidad, fuente, dominio y huella | **Backend verificable** para los datos puros de los paquetes de mezcla | Publicados en `GET /motor/catalogo` (§4). Las propiedades derivadas del estado siguen en la evaluación |
| F2.3 admisión por datos y rechazos estructurados | **Backend verificable** | Regla única por especie; código propio por dato faltante; **F9-R3 cerrado** (§3) |
| F2.4 sustitución de datos puros | **Backend verificable** | v_L, cp del gas ideal y Psat por especie, con fuente y dominio, en las tres rutas; potencial coherente; huella; rechazos (§11) |
| F2.5 referencias entre paquetes | **Backend verificable** | Corrientes entre paquetes con la misma referencia admitidas y conservativas. IAPWS-95 ↔ mezcla sigue rechazado, con la cifra que lo justifica. Datos de formación auditados (§12) |
| F2.6 sustancia nueva real y regresión | **Backend verificable** | Acetona incorporada solo por registro y contrastada con Tb, ΔHvap y el azeótropo con metanol (§13). Regresión completa en §10 |
| F9-R4 (nueva, corregida) | Corregida | Inversión PH/UP de una especie pura en un paquete de mezcla cuando Tsat(P) cae en el dominio (§14) |

## 2. F2.1 · Auditoría

**Antes:**

- La lista de especies estaba fija en `core/mezclas_datos._ESPECIES` y mezclaba identidad (nombre, M) con la
  procedencia de los datos.
- La admisión se decidía en varios sitios, con criterios distintos:

| Lugar | Cómo decidía |
|---|---|
| `core/mezclas.Sistema` | Pertenencia a la lista. Para NRTL-LLE, pertenencia al par. Para UNIFAC, la asignación de grupos, **solo con 2 o más especies** |
| `backend/motor_mezclas.capacidades_mezcla` | Casos especiales por paquete (par NRTL-LLE, filtro de asignaciones UNIFAC) |
| `backend/motor_termodinamica` y `backend/motor_diagramas` | Pertenencia a la lista o a `componentesCAS` |

Esa diferencia producía **F9-R3**: con la tabla UNIFAC ELL, el metanol puro se evaluaba aunque las capacidades lo
excluían, porque con una sola especie no se construye el modelo de grupos.

**Ahora:**

| Pieza | Archivo | Contenido |
|---|---|---|
| Identidad | `core/catalogo.REGISTRO` (`MappingProxyType` de `RegistroSustancia` congeladas) | CAS, nombre, M con su fuente, tabla de Psat y v_L con su método |
| Datos puros | `core/mezclas_datos.especie` (sin cambios) y `datos_puros_faltantes(cas)` (nuevo) | Psat de Wagner y cp de Poling, de las tablas fijadas de `chemicals`. Se cargan una vez, bajo el cerrojo F0, y nunca durante un flash |
| Requisitos de paquete | `core/catalogo.requisitos(liquido)` y `faltantes(liquido, cas)` | Por especie: datos puros, asignación de grupos de la variante, pertenencia al par NRTL-LLE o la formulación IAPWS-95 (solo agua). Por par o por grupo: se comprueban al construir el modelo de líquido |
| Admisión | Una sola regla: `faltantes(...)` vacío | La aplican el `Sistema` (también con una especie), las capacidades y el catálogo |

`Especie` y los valores no cambian. Por eso **las huellas de los paquetes son idénticas** a las publicadas en F1;
se comprueba en la sección 0 de la suite.

## 3. F2.3 · Admisión y rechazos

| Situación | Código (prefijo `MOTOR_ESTADO_`, `MOTOR_ENS_` o `MOTOR_DIAG_`) | Dato en `faltantes` |
|---|---|---|
| CAS no registrado (p. ej. la acetona, que sí tiene grupos DDBST: tener grupos no basta) | `COMPONENTE_NO_SOPORTADO` | `registro` |
| Registrado, pero sin coeficientes en una tabla | `DATO_PURO_AUSENTE` (**nuevo**) | `presion_vapor`, `cp_gas_ideal`, `masa_molar` o `volumen_liquido` |
| Fuera del par de NRTL-LLE agua/butanol, **también pura** | `PARAMETRO_AUSENTE` | `parametros_nrtl_lle` |
| Sin asignación de grupos en la variante UNIFAC, **también pura** (metanol con ELL) | `UNIFAC_ASIGNACION_AUSENTE` | `asignacion_grupos_lle` |
| No es agua, con IAPWS-95 | `COMPONENTE_NO_SOPORTADO` | `formulacion_iapws95` |
| Par NRTL o interacción de grupos ausente | `PARAMETRO_AUSENTE` / `UNIFAC_INTERACCION_AUSENTE` | Por conjunto: no figura en el catálogo |

**F9-R3 cerrado.** El metanol puro con `unifac-original-lle-public` devuelve `no_soportado` con
`MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE`, igual que en mezcla. En el ensamblaje da
`MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE`.

**Decisión sobre la especie pura.** Con g^E = 0 una especie pura no necesita grupos. Aun así, la regla exige los
requisitos por especie del paquete también en el límite puro, por dos razones:

- el contrato pide una misma regla para el límite puro y para las mezclas;
- un volumen puro puede recibir otra especie durante una trayectoria.

El metanol puro sigue disponible con los paquetes que lo admiten (ideal, NRTL, UNIFAC original y Dortmund).

## 4. F2.2 · Catálogo publicado (`GET /motor/catalogo`)

Tipos: `docs/contratos/contratoCatalogo.ts` (`CatalogoMotor`, revisión 1). Sin parámetros y sin efectos.

- **`sustancias[]`**:
  - `id` = CAS, `nombre`, `masaMolar` {valor, unidad, fuente};
  - `datosPuros`:
    - `estado` (`completos` | `incompletos`) y `faltantes`;
    - `propiedades`: `presion_vapor` (forma, coeficientes, unidad Pa, fuente, dominio en T), `cp_gas_ideal`
      (coeficientes, J/(mol K), fuente, dominio) y `volumen_liquido` (valor, m3/mol, condición, fuente);
    - `dominioLiquido` y `huella` (sha256 de los datos puros usados, que forman parte de la huella del paquete).
  - Un lector puede reproducir Psat y cp usados a partir de los coeficientes publicados; se comprueba a 1e-12.
- **`paquetes[]`**:
  - `modelo`, `nombre`;
  - `requisitos` {`porEspecie`, `porPar`, `porGrupo`};
  - `operaciones`:
    - `estado.especificaciones`;
    - `ensamblaje.disponible` (y `coberturaGrupos` si la ruta v2 la publica);
    - `diagramas`: {disponible, operaciones};
  - `especies[]`: una entrada por sustancia, en el orden del catálogo, con `admitida` y `faltantes` {dato, codigo, mensaje}.
- **`regla`**: la semántica de admisión en texto.
- **`noDisponible`**: alta de sustancias desde la petición, overrides (F2.4) y alineación de referencias (F2.5).

**Coherencia comprobada.** Las especies admitidas de cada paquete son exactamente los `componentesCAS` de las tres
rutas: estado, ensamblaje v2 y diagramas. La construcción del catálogo lo verifica con un `assert`, y la suite lo
repite por ruta y especie pura contra el `Sistema`.

Los tamaños admitidos y contrastados, los dominios de estado y la evidencia siguen en las capacidades de cada
ruta; el catálogo no los duplica.

## 5. Cambios publicados

| Elemento | Cambio |
|---|---|
| Capacidades de estado, ensamblaje v2 y diagramas | Ninguno. Se comparó `motor-termodinamica-capacidades.json` de F1 con la respuesta nueva: idénticos |
| Huellas de paquete | Ninguno |
| Rechazos que cambian | Especie pura sin el requisito del paquete. Antes: metanol con ELL `evaluado` y etanol con NRTL-LLE `PARAMETRO_AUSENTE`. Ahora: rechazo con el código de §3 en todos los paquetes |
| Ruta nueva | `GET /motor/catalogo` |
| Código nuevo | `DATO_PURO_AUSENTE` |

## 6. F2.5 · Auditoría inicial de referencias (versión de F2.1; resultado final en §12)

- **Paquetes de mezcla:** todos comparten la referencia `gas-ideal-298.15K-1bar-h0-s0` por especie, y la masa molar
  sale del mismo registro.
- **Agua IAPWS-95:** usa `iapws95-u0-s0-liquido-saturado-punto-triple`.
- **Corrientes:** el ensamblaje v2 rechaza **cualquier** corriente entre volúmenes con paquetes distintos
  (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`). Es seguro, pero más restrictivo de lo necesario. Entre dos paquetes de
  mezcla (por ejemplo NRTL y UNIFAC) la referencia por especie es la misma y la entalpía transportada sería coherente.
- **Siguiente paso de F2.5:**
  - admitir corrientes entre paquetes con referencia idéntica;
  - formular una conversión explícita IAPWS ↔ gas ideal de 298.15 K para el agua, o mantener el rechazo;
  - demostrar la conservación en ambos casos.
- **Datos de formación** (preparación de F5): no están en el registro. `chemicals` tiene Hf°(g) y S°(g) para las 7
  especies (`chemicals.reaction.Hfg` y `S0g`; por ejemplo agua −241 822 J/mol y 188.8 J/(mol K)). Falta auditar
  su fuente y su coherencia con la referencia de los paquetes antes de usarlos.

## 7. Evidencia

`python tests/validar_motor_catalogo.py`, 87 comprobaciones. Secciones:

- **0. Registro.** Solo lectura y dataclass congelada. Las huellas de tres paquetes y las capacidades puntuales
  son idénticas a las publicadas en F1.
- **1. Regla única.**
  - Admitidas = `componentesCAS` de las tres rutas para los 8 paquetes.
  - El `Sistema` de cada especie pura se construye o se rechaza igual que dice el catálogo, con el mismo código
    (6 paquetes de mezcla × 7 especies = 42 combinaciones).
  - F9-R3 en estado y en ensamblaje; etanol puro con NRTL-LLE; acetona en estado y diagramas.
- **2. Extensibilidad (simulada en el proceso de la prueba).**
  - La acetona, registrada con datos de las mismas tablas y v_L de `thermo` (HEOS_FIT), queda admitida en ideal y
    UNIFAC, no en NRTL-LLE ni en IAPWS-95.
  - Agua–acetona con UNIFAC original da un TP certificado **sin código nuevo**.
  - Una sustancia registrada sin tablas da `DATO_PURO_AUSENTE` por propiedad en el `Sistema` y en el servicio.
  - El registro se restaura al terminar.
- **3. Contenido y contraste independiente.**
  - Los coeficientes publicados reproducen Psat y cp usados.
  - Psat del agua (Wagner–McGarry) frente a IAPWS-95, de 280 K a 0.9·Tc: < 0.2 %.
  - Temperatura normal de ebullición frente al NIST Chemistry WebBook:

    | Especie | Calculada (K) | Literatura (K) | Diferencia (K) |
    |---|---|---|---|
    | agua | 373.16 | 373.12 | +0.04 |
    | etanol | 351.44 | 351.39 | +0.05 |
    | benceno | 353.24 | 353.24 | 0.00 |
    | tolueno | 383.79 | 383.75 | +0.04 |
    | 1-butanol | 390.88 | 390.88 | 0.00 |
    | acetato de etilo | 350.22 | 350.26 | −0.04 |
    | metanol | 337.69 | 337.85 | −0.16 |

- **4. Concurrencia e HTTP.** 8 hilos en frío construyen el mismo catálogo; la ruta HTTP coincide con la función;
  la respuesta es una copia.

**Ejemplos:** `docs/ejemplos/motor-catalogo/` (`python tests/generar_ejemplos_motor_catalogo.py`):

- el catálogo;
- las capacidades puntuales;
- tres rechazos: F9-R3, etanol puro con NRTL-LLE y acetona no registrada;
- metanol puro con UNIFAC original, evaluado.

**Verificador:** `node tests/verificar_contrato_catalogo.mjs`. Hace:

- compilación de los tipos con controles negativos;
- identidad única;
- una entrada por sustancia en cada paquete;
- admitida ⇔ sin faltantes;
- admitidas = `componentesCAS` puntuales;
- rechazos con su código.

## 8. Archivos

**Nuevos:**

- `core/catalogo.py`
- `backend/motor_catalogo.py`
- `docs/contratos/contratoCatalogo.ts`
- `docs/ejemplos/motor-catalogo/` (32 JSON tras F2.6)
- `tests/validar_motor_catalogo.py`
- `tests/generar_ejemplos_motor_catalogo.py`
- `tests/verificar_contrato_catalogo.mjs`
- este documento

**Modificados:**

| Archivo | Cambio |
|---|---|
| `core/mezclas_datos.py` | Vista del registro y `datos_puros_faltantes` |
| `core/mezclas.py` | El `Sistema` aplica la regla única y da códigos `COMPONENTE_NO_SOPORTADO` y `DATO_PURO_AUSENTE` |
| `backend/motor_mezclas.py` | Capacidades desde la regla; se retiraron los casos especiales |
| `backend/main.py` | Ruta `GET /motor/catalogo`, añadida por bytes y respetando los finales de línea |

## 9. Trabajo para Codex (F2.1–F2.3; lo de F2.4–F2.6 está al final de §15)

1. Sincronizar `contratoCatalogo.ts`.
2. Descubrir sustancias y paquetes desde `GET /motor/catalogo`, sin una lista química propia. Mantener los
   componentes simbólicos para balances sin propiedades.
3. Al elegir paquete, ofrecer solo las especies con `admitida`. Para las demás, mostrar el `dato` y el `mensaje` del
   faltante (p. ej. «sin grupo CH3OH en la tabla ELL»). Esto vale también con un solo componente (F9-R3).
4. Mostrar las propiedades puras (fuente, unidad, dominio, huella) en detalles, separadas de las propiedades del
   estado evaluado.
5. Tratar `DATO_PURO_AUSENTE` como dato faltante, igual que `PARAMETRO_AUSENTE` y `UNIFAC_*`.
6. La guarda del lector para el metanol puro con ELL puede quedarse. Ahora el backend devuelve el rechazo
   estructurado, así que no hace falta una excepción local.

## 10. Regresión ejecutada

Ejecutado el 16 de octubre de 2026 con el código final; las suites de Python en paralelo:

| Comando | Resultado | Salida |
|---|---|---|
| `python tests/validar_motor_catalogo.py` | OK, 87 | 0 |
| `python tests/validar_motor_unifac.py` | OK, 136 | 0 |
| `python tests/validar_motor_termodinamica.py` | OK, 585 | 0 |
| `python tests/validar_motor_termodinamica_h3.py` | OK, 3729 | 0 |
| `python tests/validar_motor_ensamblaje.py` | OK, 245 | 0 |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 | 0 |
| `python tests/validar_motor_consolidacion_v2.py` | OK, 128 | 0 |
| `python tests/validar_motor_n_componentes.py` | OK, 82 | 0 |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 |
| `node tests/verificar_contrato_catalogo.mjs` | OK: 7 sustancias, 8 paquetes, 4 casos | 0 |
| `node tests/verificar_contrato_unifac.mjs` | OK | 0 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK | 0 |
| `node tests/verificar_contrato_diagramas.mjs` | OK | 0 |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK | 0 |
| `node tests/verificar_contrato_ensamblaje.mjs` | OK | 0 |
| `npm run test:motor-fundamental` (en `frontend/`) | OK | 0 |

Los ejemplos de entregas anteriores no se regeneraron: las capacidades y las huellas no cambian (§5), y los
verificadores pasan con ellos.

*(La tabla anterior corresponde a la entrega F2.1. La regresión de F2.4–F2.6 está en §15.)*

## 11. F2.4 · Sustitución de datos puros

**Qué se sustituye y por qué solo eso.** Cada especie de un paquete de mezcla se describe con una sola función
de Gibbs por fase, construida con tres entradas: Psat (Wagner), cp del gas ideal (Poling) y v_L
(`core/mezclas_datos`). h, s, μ, el cp del líquido, la densidad y el calor de vaporización se **derivan** de esas
entradas. Por eso solo esas tres entradas son sustituibles, y la sustitución cambia el mismo potencial con todas
sus derivadas.

| Propiedad (`datosPuros[cas]`) | Campos | Comprobación al leer |
|---|---|---|
| `volumen_liquido` | `valor`, `unidad` (m3/mol, cm3/mol, L/mol), `fuente` | > 0 |
| `cp_gas_ideal` | `coeficientes` {a0..a4} de cp/R, `dominio.T`, `fuente` | cp > 0 en 201 puntos del dominio |
| `presion_vapor` | `forma` (WagnerPoling \| WagnerMcGarry), `coeficientes` {A, B, C, D, Tc, Pc}, `dominio.T`, `fuente` | Tc > 0, Pc > 0, Tmax ≤ Tc; ln P finito, estrictamente creciente y ≤ ln Pc en 201 puntos |

El dominio en T del líquido puro (`T_rango`) se recalcula con los dominios sustituidos.

**Rechazos.**

- `*_SUSTITUCION_NO_ADMITIDA` (`no_soportado`), en tres casos:
  - `masa_molar`: es identidad, y cambiarla alteraría los inventarios;
  - cualquier propiedad del estado: h, s, μ, cp del líquido, densidad;
  - cualquier sustitución en IAPWS-95: es una formulación completa.
- `*_SUSTITUCION_INVALIDA` (`invalido`): falta la fuente, unidad o dominio inválidos, cp ≤ 0, Psat no física,
  CAS ajeno a la petición o campo desconocido.
- Todos llevan ruta: `declaracion.datosPuros.<cas>.<propiedad>[.campo]` en el servicio puntual, y la ruta JSON en
  ensamblaje y diagramas.

**Dónde se declara.**

| Ruta | Campo |
|---|---|
| Estado puntual | `declaracion.datosPuros` |
| Ensamblaje v2 | `paquetes[].datosPuros`; cada volumen aplica las de sus especies |
| Diagramas | `datosPuros` |

Tipos: `SustitucionDatosPuros` en `docs/contratos/contratoCatalogo.ts`. `PaqueteV2.datosPuros?` y
`SolicitudDiagrama.datosPuros?` son aditivos.

**Huella y caducidad.**

- La sustitución, con su fuente, entra en la huella del paquete: mismo valor con otra fuente da otra huella.
- Sin sustitución, la huella es exactamente la de siempre.
- La sustitución no altera el registro ni la caché global: se aplica sobre una copia de `Especie` en ese `Sistema`.
- No se publica un eco de las sustituciones: la petición es su registro y la huella (`huellaModelo`,
  `procedenciaModelo[].huella`) su prueba.

**Coherencia comprobada** (suite del catálogo, sección 7):

| Sustitución | Comprobación |
|---|---|
| v_L | v de la fase cambia exactamente x_i·Δv_L; ∂g/∂P = v; g = h − T s |
| cp_ig ×1.1 | ∂h/∂T del vapor = el cp nuevo, a 1e-7 |
| Psat (A ×1.02) | Clapeyron h_ig − h_L = T(RT/Psat − v_L)·Psat' se cumple con la Psat nueva; Tb del etanol pasa de 351.44 K a 353.45 K y el TP a Tb' + 0.01 K es vapor |

En diagramas, el extremo puro es la Psat nueva; en ensamblaje, V(0) incluye el v_L sustituido y la trayectoria
se certifica.

## 12. F2.5 · Referencias entre paquetes y conservación

- **Entre paquetes de mezcla:** todos usan `gas-ideal-298.15K-1bar-h0-s0` por especie y la misma M del registro.
  - Una corriente entre volúmenes con paquetes distintos se admite si `referencia.id` coincide.
  - Capacidad publicada: `corrientes.entrePaquetes = "misma_referencia"`, aditivo y tipado.
  - Evidencia: red NRTL ChemSep → UNIFAC original (corriente y contacto térmico), con materia por especie
    < 1e-12, energía y segunda ley certificadas.
- **Agua IAPWS-95 ↔ mezcla:** h_mezcla − h_IAPWS del agua va de −46 296 a −45 586 J/mol entre 280 y 500 K y entre
  1 y 5 bar. Varía ~710 J/mol porque los modelos difieren (líquido incompresible y vapor ideal frente a IAPWS-95).
  - Ninguna constante convierte una referencia en la otra conservando la energía. La corriente se sigue
    rechazando con `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`, y el mensaje nombra ambas referencias.
  - El **contacto térmico** sí se admite, porque el calor no depende de la referencia, y se certifica.
- **Datos de formación (preparación de F5):** `chemicals.reaction.Hfg/S0g` tiene Hf°(g) y S°(g) a 298.15 K y
  1 bar para las 8 especies. Esa es la misma referencia de estado de los paquetes de mezcla, y el cero (h = s = 0
  del gas ideal) se sustituiría por Hf° y S° por especie. No se incorporan en F2: falta auditar su fuente por
  especie y contrastarlas antes de F5.

## 13. F2.6 · Acetona (67-64-1) incorporada por registro

**Datos**, de las mismas tablas y versiones que las 7 especies de la base:

| Dato | Valor | Fuente |
|---|---|---|
| Psat | Wagner de Poling (`chemicals` 1.5.2), 178.45–508.1 K | `chemicals` |
| cp_ig | polinomio de Poling, 200–1000 K | `chemicals` |
| v_L | 7.4014e-5 m3/mol | `thermo` 0.6.1, VolumeLiquid HEOS_FIT a 298.15 K, el mismo método que la mayoría |
| M | 58.07914 g/mol | `thermo` |
| Grupos UNIFAC | CH3 + CH3CO | DDBST original y Dortmund; en la tabla ELL, traducidos con R y Q idénticos |

**Sin código nuevo.** Queda admitida en ideal, NRTL ChemSep y las tres variantes de UNIFAC, y no en NRTL-LLE ni
en IAPWS-95. Los pares NRTL con datos se resuelven por sí mismos. Con la acetona hay 5 conjuntos NRTL completos de
4 especies y 1 de 5 (antes 2 y 0). **No tienen contraste dinámico propio**: `tamanos.contrastados` no cambia.

**Contraste independiente.**

| Magnitud | Literatura | Motor |
|---|---|---|
| Tb a 1 atm | 329.22 K | 329.22 K |
| ΔHvap en Tb (CRC) | 29.10 kJ/mol | 30.70 kJ/mol (+5.5 %) |
| Azeótropo acetona–metanol a 1 atm (Horsley, *Azeotropic Data*) | 55.5 °C, x_acetona ≈ 0.80 | UNIFAC original 55.22 °C / 0.781; Dortmund 55.28 / 0.787; NRTL ChemSep 55.36 / 0.791 |
| Calentamiento acetona–agua con UNIFAC (dinámica) | — | burbuja detectada y trayectoria certificada |

**ΔHvap en Tb para las 8 especies** (CRC Handbook):

| Especie | Motor (kJ/mol) | Literatura (kJ/mol) | Diferencia |
|---|---|---|---|
| agua | 41.31 | 40.65 | +1.6 % |
| etanol | 40.48 | 38.56 | +5.0 % |
| benceno | 31.84 | 30.72 | +3.6 % |
| tolueno | 34.63 | 33.18 | +4.4 % |
| 1-butanol | 44.89 | 43.29 | +3.7 % |
| acetato de etilo | 33.44 | 31.94 | +4.7 % |
| metanol | 37.25 | 35.21 | +5.8 % |
| acetona | 30.70 | 29.10 | +5.5 % |

Es un **sesgo sistemático** del modelo de vapor ideal ya declarado: Clapeyron con Z = 1 sobrestima Δv, y por tanto
ΔH, cuando el vapor real a 1 atm tiene Z ≈ 0.95–0.98. No es un error de los datos de la acetona. Se publica en la
evidencia; corregirlo exige un vapor no ideal (F8, EOS).

**Nota sobre los v_L.** Los v_L del registro son literales fijados al registrar, no se recalculan al arrancar. Por
ejemplo, `thermo` 0.6.1 da hoy 1.80686e-5 m3/mol para el agua frente a 1.80683e-5 registrado. Recalcularlos
cambiaría las huellas sin cambio físico intencionado.

## 14. F9-R4 · Inversión PH/UP de una especie pura en un paquete de mezcla (corregida)

**Hallazgo.** Al probar el contacto IAPWS/mezcla apareció este rechazo:
`Componente puro en saturación a 373.161 K: T y P no determinan el reparto`.

**Causa.** La búsqueda isobara de una especie pura pone el extremo del intervalo en Tsat(P)·(1 ∓ 1e-9). Pero el TP
puro rechaza como ambigua la banda |P/Psat − 1| ≤ 1e-6, que en T equivale a ~8e-8 relativo. El extremo caía
dentro de la banda, y el reintento de `_TP_seguro` a 1e-12 también.

**Alcance.** Cualquier PH/UP de una especie pura en un paquete de mezcla con Tsat(P) en el dominio. No lo cubría
ninguna prueba.

**Corrección** (`core/mezclas`). Dentro de la búsqueda isobara de una especie pura, el lado de Tsat ya se conoce:
líquido por debajo y vapor por encima. Se evalúa esa fase (`_puro_TP(..., lado=)`) en lugar de rechazar. El TP
directo sigue rechazando la ambigüedad.

**Verificación:**

- PH del agua pura (ideal) a 320, 373, 373.16 y 380 K recupera T y la fase;
- un estado a 1.9e-6 K bajo Tsat, dentro de la banda, se resuelve;
- el contacto IAPWS/mezcla se certifica.

## 15. Regresión de F2.4–F2.6

Ejecutado el 16 de octubre de 2026 con el núcleo final; las suites de Python en paralelo:

| Comando | Resultado | Salida |
|---|---|---|
| `python tests/validar_motor_catalogo.py` (secciones 0–7) | OK, 126 | 0 |
| `python tests/validar_motor_unifac.py` | OK, 136 (cobertura de 8 especies; el caso «con grupos y sin datos puros» pasa a ser el n-hexano) | 0 |
| `python tests/validar_motor_n_componentes.py` | OK, 82 (la auditoría N0 se mantiene sobre las 7 especies de su entrega e informa de los conjuntos NRTL nuevos con la acetona) | 0 |
| `python tests/validar_motor_termodinamica.py` / `_h3.py` | OK, 585 / 3729 | 0 |
| `python tests/validar_motor_ensamblaje.py` / `_v2.py` / `consolidacion_v2.py` | OK, 245 / 114 / 128 | 0 |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 |
| `node tests/verificar_contrato_catalogo.mjs` | OK: 8 sustancias, 8 paquetes, 8 casos puntuales, 7 ensamblajes y diagramas | 0 |
| `node tests/verificar_contrato_{unifac,ensamblaje_v2,diagramas,motor_termodinamica,ensamblaje}.mjs` | OK | 0 |
| `npm run test:motor-fundamental` (en `frontend/`) | **Falla en `verificar_consolidacion_multifasica.mjs`**: «Contract copy is current» | 1 |

Ejecuté por separado los verificadores del frontend que siguen en la cadena. Fallan cuatro, y **ninguno es
físico**:

| Verificador | Motivo |
|---|---|
| `verificar_consolidacion_multifasica`, `verificar_diagramas_equilibrio`, `verificar_cobertura_grupos`, `verificar_catalogo_motor` | Comparan su copia del contrato con la canónica, que cambió: `entrePaquetes`, `datosPuros`, `SustitucionDatosPuros` |
| `verificar_integracion_unifac` | Tiene fijadas 6 especies en la tabla ELL; con la acetona son 7. El metanol sigue excluido |

El resto pasa.

**Ejemplos regenerados** (raíz, `motor-v2/`, `motor-n-componentes/`, `motor-diagramas/`, `motor-unifac/`,
`motor-catalogo/`), comparados número a número con la copia de F2.1, ignorando `tmMinimo` y el tiempo de pared:

- **Estados, trayectorias y diagramas:** sin ningún cambio numérico.
- **Capacidades:** solo cambios aditivos:
  - la acetona en `componentesCAS` de los paquetes que la admiten;
  - 5 pares NRTL más en `pares`; la lista cambia de orden porque se recorre en el orden del registro;
  - `corrientes.entrePaquetes`;
  - la cobertura de grupos con 8 especies.
- **Catálogo:** 8 sustancias.
- **`motor-catalogo/`:** el rechazo de la acetona no registrada pasa a ser el del n-hexano, y hay 12 casos
  nuevos de F2.4–F2.6 (24 archivos).

### Trabajo para Codex (F2.4–F2.6)

1. Sincronizar las copias de `contratoEnsamblajeV2.ts`, `contratoDiagramasEquilibrio.ts` y `contratoCatalogo.ts`,
   y actualizar en `verificar_integracion_unifac` el recuento de la tabla ELL (7 especies, metanol excluido).
2. Ofrecer la acetona desde el catálogo. No hace falta lista propia: llega en `GET /motor/catalogo`.
3. Edición de `datosPuros` (F2.4), en detalles y no en la pantalla principal:
   - solo `volumen_liquido`, `cp_gas_ideal` y `presion_vapor`, con la fuente obligatoria;
   - conservar el valor original y la elección del usuario;
   - mostrar los rechazos `SUSTITUCION_*` con su ruta;
   - tras sustituir, invalidar resultados y caché **por huella**: la huella cambia con el dato y con la fuente;
   - las sustituciones de un paquete del ensamblaje viajan en `paquetes[].datosPuros` y valen para todos sus volúmenes.
4. Red: una corriente entre volúmenes con paquetes de mezcla distintos ya se admite (`entrePaquetes =
   "misma_referencia"`). Entre agua IAPWS-95 y mezcla, solo contacto térmico; la corriente se rechaza con
   `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`.
5. Registrar **F9-R4** (§14) como corregida.

### Límites que siguen

- Las sustituciones son solo de datos puros de paquetes de mezcla. No incluyen parámetros NRTL ni UNIFAC.
- No hay alta de sustancias desde la petición: el registro es del servidor.
- Los datos de formación están auditados pero no incorporados (F5).
- El vapor ideal sobrestima ΔHvap entre un 2 y un 6 % en Tb (§13).
- Los conjuntos NRTL nuevos con la acetona no tienen contraste dinámico propio.
