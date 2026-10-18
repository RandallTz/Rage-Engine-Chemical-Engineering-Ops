# Encargo para Claude: UNIFAC en el motor independiente

Fecha: 16 de octubre de 2026. Estado: **F1 entregado e integrado dentro de su alcance; ELL cubre seis especies y deja metanol bloqueado por datos.** Evidencia: [integración UNIFAC](INTEGRACION_UNIFAC.md). Este contrato se conserva como referencia de aceptación; el [roadmap principal](ROADMAP_MOTOR_MULTIFISICO.md) determina la continuidad. No volver a ejecutar F1 por sus instrucciones históricas.

Prioridad: F1 del [roadmap](ROADMAP_MOTOR_MULTIFISICO.md). Coordinación: [acuerdo de trabajo](COORDINACION_CLAUDE_CODEX_MOTOR.md).

## 1. Objetivo y frontera del encargo

Integrar UNIFAC como paquete termodinámico intercambiable de `/motor`: el mismo paquete debe aportar potenciales, estabilidad, reparto de fases y propiedades caloríficas al servicio puntual, al ensamblaje dinámico y al trazador de diagramas ya existentes.

La primera entrega completa será **UNIFAC original con un conjunto público de parámetros identificado**. La siguiente será **UNIFAC modificado Dortmund**, con grupos, formulación, datos y huella propios. Un juego dedicado a ELL se trata aparte y solo si la auditoría demuestra cobertura suficiente.

No basta con exponer gamma ni con reproducir un diagrama binario. No introducir un solver o paquete diferente para cada mezcla de ejemplo. No utilizar UNIFAC para completar automáticamente parámetros NRTL ausentes: son modelos distintos y la elección debe seguir siendo explícita.

Este encargo no incluye nuevos modelos de gas a alta presión, reacciones, momento, sólidos, electrolitos, expansión del catálogo de sustancias ni más fases/volúmenes. Esas ampliaciones tienen fases propias en el roadmap.

## 2. Base de código que hay que auditar antes de editar

| Archivo / área | Qué existe | Riesgo o punto de integración |
|---|---|---|
| `thermodynamics/proveedor.py` | UNIFAC original para actividades y acceso a `Chemical` | Conserva un cambio ajeno; no editar. Los objetos de propiedades se mutan con T/P. No convertirlo en el estado compartido de `/motor` |
| `thermodynamics/ell.py` | Juego ELL y traducción de grupos | IDs de subgrupos distintos; no trasladarlos por número ni dar por válida una traducción por nombre sin auditar definiciones |
| `core/mezclas.py` | Energía libre de exceso, NRTL/ideal, TP e inversiones, estabilidad N-componentes | `Sistema._modelo_sub` reconstruye explícitamente NRTL; no sirve sin cambios para submodelos UNIFAC |
| `core/mezclas.py::dgE_dT` | Derivada por paso complejo | Un adaptador que convierta T a float puede perder la parte imaginaria o fallar. Exigir derivada válida, no un cero accidental |
| `core/mezclas_datos.py` | Potenciales puros coherentes y siete especies | Tener grupos UNIFAC no amplía estos datos puros ni su dominio |
| `core/paquetes_volumen.py` | Paquetes para el coordinador dinámico | Registro, huellas, referencias, inicialización y propiedades de corriente |
| `backend/motor_mezclas.py` | Capacidades y API puntual | Registrar modelos y cobertura sin asumir pares NRTL para UNIFAC |
| `backend/motor_ensamblaje_v2.py` | Capacidades, recuento e inicialización por volumen | Publicar tamaño admitido y evidencia; preservar GL estructural frente a rechazo físico |
| `core/coexistencia_lv.py`, `core/diagramas_equilibrio.py`, `backend/motor_diagramas.py` | Trazador que reutiliza el paquete | Mantener esa reutilización; no copiar fórmulas o cambiar paquete durante el trazado |
| `docs/contratos/` | Tipos canónicos | Cualquier campo nuevo se acuerda aquí antes de que el frontend dependa de él |

Revisar también el fallo observado de arranque en frío de `_pares_nrtl`: `KeyError: 'ChemSep NRTL'`. Reproducirlo con solicitudes concurrentes antes de atribuir causa. Corregirlo de forma acotada si se confirma, con su regresión; no ocultarlo en el frontend.

## 3. Decisiones físicas obligatorias

### 3.1 Un modelo de Gibbs para cada paquete

En esta primera integración se conserva el modelo de fases puras del motor. UNIFAC aporta el exceso líquido; no reemplaza la EOS del agua ni decide por sí solo la física del gas.

Con `gE` molar en J/mol y composición fija para las derivadas térmicas:

```text
gE(T,x) = R T Σ_i x_i ln gamma_i(T,x)
G^E(T,n) = n_total gE(T,x)
mu_i^E = ∂G^E/∂n_i = R T ln gamma_i
sE = -(∂gE/∂T)_(P,x)
hE = gE - T (∂gE/∂T)_(P,x)
CpE = -T (∂²gE/∂T²)_(P,x)
bar_h_i^E = -R T² (∂ln gamma_i/∂T)_(P,x)
```

El exceso se suma a los potenciales y propiedades del líquido definidos por el paquete. Las contribuciones ideales de mezcla y los términos puros se contabilizan una sola vez. Para este modelo sin dependencia de P del exceso, `vE = 0` es una aproximación explícita; no significa que UNIFAC calcule densidad real de mezcla.

Requisitos:

- Derivadas, gamma, hE y sE corresponden a **la misma variante y tabla**.
- El flujo energético usa la entalpía total de la fase donante del paquete, incluidas sus contribuciones de mezcla. No añadir un “calor UNIFAC” extra al balance.
- Se conservan las referencias por especie usadas por los paquetes actuales de mezcla. No importar entalpías arbitrarias de `Chemical` que cambien esas referencias.
- Si se necesita una nueva interfaz de derivadas, que sea mínima y compatible con ideal/NRTL; no forzar que todo futuro paquete EOS tenga `gamma` o `gE`.
- Las derivadas analíticas de una dependencia se pueden reutilizar tras auditar unidades y definiciones. No usar paso complejo sobre una ruta que lo descarta. Una alternativa numérica requiere convergencia de paso y error medido.
- Se conserva la segunda ley y el trabajo de frontera del coordinador actual.

### 3.2 Variante, grupos y parámetros inseparables

Cada paquete debe fijar explícitamente:

1. Variante de las ecuaciones.
2. Tabla y definición de subgrupos, grupos principales, R y Q.
3. Descomposición química de cada CAS y procedencia de esa asignación.
4. Tabla de interacciones, edición/revisión y convención de dependencia en T.
5. Dominio de datos puros, límites del modelo y rango operativo declarado.
6. Versiones de dependencias usadas para producir la evaluación.

No confiar en defaults de `UNIFAC.from_subgroups`: pasar variante, subgrupos y datos explícitos. No confundir el parámetro `version` de la biblioteca con la versión del contrato o del paquete del simulador.

La documentación oficial separa variantes y expone métodos de Gibbs y derivadas: [API UNIFAC de thermo](https://thermo.readthedocs.io/thermo.unifac.html). Las tablas públicas de [original](https://www.ddbst.com/published-parameters-unifac.html) y [Dortmund](https://www.ddbst.com/PublishedParametersUNIFACDO.html) deben identificarse por su edición efectiva; “la última” no es una identidad reproducible.

No se incorporan parámetros privados, UNIFAC 2.0 con completado de matriz ni ajustes propios dentro del ID de un paquete publicado distinto. Una ampliación de ese tipo requeriría otro encargo e identidad.

### 3.3 Ausencias, ceros y fases

- Distinguir interacción ausente de valor cero explícitamente definido y de convenciones internas válidas para el mismo grupo.
- Comprobar todas las interacciones dirigidas requeridas por los grupos del conjunto; no suponer simetría.
- La falta de grupos, definición de grupo, interacción o propiedad pura produce diagnóstico con especie/grupo/ruta. No gamma = 1 por omisión.
- Un sistema de una sola especie con datos puros válidos tiene exceso de mezcla nulo; no debe depender artificialmente de parámetros entre grupos de otras sustancias.
- Cantidad exactamente cero conserva ID, balance y posibilidad de entrar posteriormente; no convertir trazas positivas en cero.
- No fabricar inventarios positivos para evitar `log(0)`. Resolver las caras y límites del problema con un tratamiento definido.
- La coexistencia exige igualdad de potenciales y prueba de estabilidad del paquete. Una igualdad de actividades con dos composiciones iguales no prueba separación LL.
- Un paquete usa la misma función de Gibbs para todas las fases líquidas que compiten. No seleccionar el juego ELV para una fase y el ELL para otra.
- Mantener el rechazo por tope de fases y por presupuesto agotado; no certificar por omisión de fases competidoras.

### 3.4 Cobertura y evidencia

UNIFAC evita exigir parámetros moleculares NRTL para cada par, pero necesita grupos, interacciones entre grupos y datos puros. No promete cubrir cualquier sustancia o mezcla.

Comprobar primero el catálogo actual, sin ampliarlo en este encargo. No aumentar automáticamente `componentesMaximos`, `fasesMaximas` o `volumenesMaximos`. Registrar los tamaños realmente contrastados por variante y operación.

Separar:

- **Coherencia interna:** identidades, conservación, estabilidad buscada y referencias.
- **Contraste numérico independiente:** otra implementación o una referencia calculada por una vía distinta.
- **Evidencia experimental:** errores frente a mediciones, sin usar esos mismos puntos para reajustar el paquete.

Dos envolturas de la misma llamada a `thermo` no constituyen implementaciones independientes. Un resultado predictivo puede ser matemáticamente coherente y tener error experimental; publicar ambas cosas sin ocultar el error.

## 4. Hitos de trabajo

### UNIFAC-U0 · Auditoría y base reproducible

Entregar un informe corto antes de la modificación física principal:

- Inventario de versiones instaladas y recursos de datos realmente disponibles.
- Matriz CAS → asignación de grupos por variante → datos puros → interacciones necesarias → operación admisible.
- Edición exacta de parámetros públicos y cobertura por dirección.
- Mapa de cambios mínimos en `_modelo_sub`, derivadas, registros, capacidades y huellas.
- Casos de referencia, tolerancias, fuentes y presupuestos elegidos antes de observar el resultado final.
- Línea base de pruebas y ejemplos actuales; auditoría del arranque concurrente.

Las decisiones rutinarias se documentan y se continúa. Un faltante de datos bloquea el subcaso afectado, no el resto del encargo. No actualizar dependencias ni sustituir datos silenciosamente.

### UNIFAC-U1 · Adaptador original y coherencia local

- Implementar el adaptador de exceso original con datos fijados.
- Soportar evaluación de gamma/Gibbs y derivadas requeridas por la energía.
- Implementar selección de subconjunto activo sin asumir matrices NRTL `.b/.a/.alpha`.
- Mantener evaluación por lotes o alternativa con presupuesto medido para la búsqueda multisemilla.
- Hacer inmutables las asignaciones y tablas de cada sistema; cachés por identidad completa, sin estado global mutable T/P/x.
- Auditar que gamma y derivadas de G coincidan, incluidas composiciones diluidas y límites puros.

**Cierre:** suite local independiente y controles negativos. Este hito solo no habilita todavía una trayectoria pública.

### UNIFAC-U2 · TP, estabilidad y reparto de fases

- Conectar el adaptador al mismo algoritmo de equilibrio del motor.
- Probar monofásico, LV y LL/LLV donde el modelo tenga datos y los casos lo produzcan.
- Preservar la condición de estabilidad frente a todas las fases candidatas del alcance declarado, aunque una tabla se haya ajustado principalmente a ELV.
- Registrar evidencia predictiva de LL por separado: resolver LL con un juego no contrastado no lo valida experimentalmente.
- Comprobar ceros, trazas, permutaciones, escalado, distintas semillas y tope de fases.

**Cierre:** reparto certificado, reconstrucción por especie y rechazo explícito de soluciones triviales/inestables.

### UNIFAC-U3 · Energía e inversiones

- Incluir hE y sE del mismo modelo en fase y mezcla; CpE cuando se publique o utilice.
- Probar identidades molares y totales, y entalpías parciales molares.
- Conectar PH/UP y UV/TV solo donde las restricciones determinen un estado.
- Mantener el rechazo del líquido incompresible que no permite identificar P a partir de U/V o T/V.
- Viajes TP → inversión → estado original en interior de fase y coexistencia; tratar ambigüedades sin elegir una raíz arbitraria.
- No publicar cp/cv de mezcla bifásica como si fueran propiedades de una fase homogénea.

**Cierre:** misma U/H/V y mismo reparto reconstruidos por una única solución de estado, sin offsets o fuentes de calor añadidos para corregir curvas.

### UNIFAC-U4 · Ensamblaje dinámico

Pruebas mínimas con el coordinador actual:

| Caso | Qué comprobar |
|---|---|
| Calentamiento a presión prescrita | H y calor impuesto; energía de mezcla incluida; aparición de vapor |
| Recipiente rígido dentro del dominio | U y calor impuesto, V constante y P calculada |
| Mezcla adiabática de corrientes | T obtenida de la energía total, no un promedio impuesto; sin doble calor de mezcla |
| Red con corriente interna e inversión | Donante según signo, cancelación exacta de transferencias internas y referencias compatibles |
| Especie que entra desde cero | ID conservado, trabajo de frontera y certificados sin inventario ficticio |
| Extracción por fase | Composición correcta, desaparición de fase y resultado parcial honesto |
| Política de fase restringida | Detención y muestra final certificada bajo el contrato vigente |
| Datos incompletos o fuera de dominio | Recuento canónico y diagnóstico físico separados, sin resultados fabricados |

Usar conjuntos de 2, 3 y más componentes según cobertura; al menos un caso de cinco o siete si U0 verifica todos sus datos. La falta de cobertura de siete se informa; no se rellena para cumplir una cifra.

**Cierre:** conserva cada especie y energía, y conserva la segunda ley en los casos evaluables. La trayectoria usa el mismo paquete que el estado puntual.

### UNIFAC-U5 · API, diagramas y metadatos

- Registrar el paquete en las capacidades puntuales, de ensamblaje y de diagramas apropiadas.
- Reutilizar TP/estabilidad/coexistencia del paquete para T–xy/P–xy; no introducir una fórmula alternativa solo para graficar.
- Mantener fases límite con composición y certificado, sin fracción de fase ficticia.
- Diagnosticar grupos/interacciones ausentes también en el trazado.
- Huella dependiente de variantes, asignaciones químicas, valores usados, propiedades puras y referencias; invariante a orden, nombres de presentación y unidades equivalentes.
- Si cambia un grupo, dato o interacción, cambia la huella y caduca la comparación con diagramas/resultados anteriores.
- Reusar las rutas existentes cuando alcancen. No crear un endpoint por mezcla o por ejemplo.

**Cierre de F1A:** U0–U5 y U8 aprobados por sus pruebas; Codex integra y verifica el recorrido. Dortmund y el juego ELL no se declaran completados por ese cierre.

### UNIFAC-U6 · Dortmund

- Mantener variante, asignaciones y parámetros Dortmund separados de original.
- Usar asignaciones correspondientes a esta variante; no reutilizar IDs de grupos originales por coincidencia numérica.
- Repetir U1–U5: derivadas, energía, estabilidad, inversiones, dinámica, diagramas y rechazos.
- Comparar ambas variantes para los mismos datos declarados y medir diferencias; sin reemplazar una por otra para ocultar una desviación.
- Identificar la tabla pública concreta disponible y conservarla en la huella.

**Cierre de F1B:** paquete Dortmund integrado y evidencia documentada. No sustituye ni cambia el paquete original.

### UNIFAC-U7 · Juego original dedicado a ELL, condicionado

- Auditar definiciones y traducciones químicas del módulo anterior.
- Validar las asignaciones y el conjunto de parámetros como una identidad propia.
- Si se ofrece LLV, todas sus fases deben usar ese mismo conjunto, y hay que medir también su comportamiento LV.
- Si la cobertura o el dominio no son suficientes, dejar el subhito bloqueado y nombrar lo que falta.

Este subhito no autoriza corregir el reparto de un paquete alternando tablas durante la solución.

### UNIFAC-U8 · Entrega y regresión

- Documento físico `docs/MOTOR_UNIFAC.md`, actualizado por hito con decisión, cobertura, resultados y limitaciones.
- Contratos canónicos y ejemplos originales de endpoints en `docs/ejemplos/motor-unifac/`.
- Nuevos verificadores de física/API/tipos y regresión anterior.
- Comparación numérica de todos los ejemplos existentes afectados por cambios compartidos.
- Benchmarks: estado frío/caliente, TP, PH, UV, estabilidad y trayectoria; N, fases, muestras, tolerancias y coste medidos.
- Manifest de archivos tocados; versiones, datos y huellas; comandos y códigos de salida reales.
- Lista de campos aditivos, diagnósticos y trabajo concreto para Codex.

Sin commit, push ni despliegue salvo petición expresa posterior.

## 5. Contrato con el frontend

### Identidades propuestas, no publicadas todavía

- `unifac-original-public`, versión `1`.
- `unifac-dortmund-public`, versión `1`.
- `unifac-original-lle-public`, versión `1`, solo si U7 se entrega.

La versión del paquete se acompaña de datos/huella; no significa usar los parámetros del año 2026. Si los nombres existentes o la auditoría aconsejan otro ID, decidirlo en U0 y documentarlo una vez antes de publicar ejemplos.

### Metadatos mínimos

Proponer una ampliación aditiva del contrato canónico para representar, cuando proceda:

| Dato | Requisito |
|---|---|
| Familia y variante | No inferirlas del nombre de la sustancia |
| Juego de datos | ID, edición, fuente y huella |
| Grupos por especie | CAS/ID, subgrupo, grupo principal, cuenta y procedencia |
| Cobertura | Falta de asignación, interacción o propiedad pura por operación |
| Dominio del conjunto | Intersección aplicable; no confundir la envolvente del catálogo con el dominio de la mezcla elegida |
| Evidencia | Numérica y experimental separadas; limitaciones predictivas |
| Dimensión | Admitida y contrastada, sin confundir especies con fases |

No publicar grupos como si fueran pares moleculares NRTL. No usar `pares: null` para insinuar que cualquier combinación es válida. Si el contrato actual no alcanza, dejar el tipo preciso en `docs/contratos/` y describir su semántica en el informe; no modificar el frontend.

Diagnósticos esperados, con códigos finales fijados en el contrato: asignación ausente, grupo desconocido/incompatible con variante, interacción dirigida ausente, dato puro ausente, fuera de dominio, estado no identificable, no convergencia, presupuesto y tope de fases. Deben citar propietario, especie/grupo y ruta cuando sean identificables.

## 6. Criterios de prueba y tolerancias

Fijar en U0 los casos, fuentes y escalas antes de cerrar implementaciones. Diferenciar precisión del algoritmo de error del modelo frente al experimento.

| Familia | Criterio |
|---|---|
| Coeficientes de actividad | Contra cálculo independiente con mismos datos; objetivo inicial Δln gamma ≤ 1e-8 en interiores regulares |
| Gibbs / potenciales | Derivada de n gE frente a R T ln gamma y Gibbs–Duhem; escalas declaradas, pruebas direccionales |
| Calórico | hE, sE y CpE frente a derivadas independientes; estudios de paso cuando se use diferencia finita |
| Fases | Igualdad de mu, descenso de G y estabilidad; conservar tolerancias físicas del motor cuando correspondan |
| Materia | Reconstrucción por especie, incluidos trazas y cantidades exactamente nulas; la energía no interviene en su escala |
| Energía | H o U frente al balance completo; calor de mezcla contado una vez; invariancia de trayectoria ante offsets compatibles |
| Datos experimentales | Error absoluto/relativo por propiedad, T y composición, con fuente e incertidumbre cuando esté disponible |
| Regresión | Cambio nulo o diferencia explicada y cuantificada; nunca sobrescribir expectativas solo para obtener verde |

No se impone un único umbral para todas las magnitudes. Si un objetivo numérico no es alcanzable, medir la causa y el error antes de ajustar la tolerancia; no relajar el certificado para ocultar no convergencia.

Matriz mínima de regresión:

- Límite puro, casi puro y dilución infinita cuando se publique.
- Trazas y ceros, entrada de especie desde cero, permutación y escalado de inventarios.
- Mismos datos con unidades equivalentes.
- Subconjunto activo frente al sistema reducido; grupos e IDs conservados.
- Grupo inexistente, variante equivocada, interacción ausente y cero explícito válido.
- Dos solicitudes concurrentes con T/P/x y mezclas diferentes; resultados iguales a su ejecución aislada.
- Tabla o asignación modificada → huella distinta; nombres/orden/unidades → misma huella física.
- Ausencia de datos puros aunque UNIFAC sí tenga grupos.
- LV, LL y aproximación a fases incipientes en los casos cubiertos.
- Parametrización distinta nunca tomada como “el mismo modelo” en caché o marcadores de diagrama.

Para contraste experimental, seleccionar datos primarios con identificación del sistema y condiciones. El [archivo ThermoML de NIST](https://www.nist.gov/mml/acmd/trc/thermoml/thermoml-archive) sirve como punto de entrada; no implica que todos los sistemas o propiedades necesarios estén disponibles. Guardar DOI/tabla/puntos y unidades usados. No llamar validación predictiva a recuperar un dato de ajuste.

## 7. Reparto de archivos

Claude: `core/`, `backend/`, pruebas físicas/API, contratos canónicos y documentación de entrega. Los archivos nuevos se organizan junto al motor actual. Refactorizar solo lo necesario para incorporar el adaptador y mantener compatibilidad.

Codex: copias de contratos, lectores, UI, catálogo de hojas y gráficos, pruebas de integración del frontend y checklist después de verificar la entrega.

No tocar `frontend/`, `/laboratorio` ni `thermodynamics/proveedor.py` desde este encargo. Los módulos antiguos pueden leerse o importarse si U0 demuestra que son adecuados, inmutables y coherentes; no conectarlos indiscriminadamente al nuevo motor.

## 8. Cierre verificable de UNIFAC original

- [ ] No hay rutas o ramas por mezcla de ejemplo.
- [ ] Modelo, grupos y tabla explícitos; sin defaults cambiantes ni parámetros inventados.
- [ ] Gamma, mu, G, H y S coherentes y contrastados.
- [ ] TP e inversiones publicadas funcionan en su alcance real.
- [ ] Dinámica usa el mismo paquete y conserva especie/energía.
- [ ] Diagramas y trayectoria comparables solo con huella compatible.
- [ ] Parámetros ausentes y estados no identificables se rechazan con origen.
- [ ] Capacidad admitida y evidencia contrastada diferenciadas.
- [ ] Contratos, ejemplos, pruebas y límites entregados sin tocar frontend ni laboratorio.
- [ ] El informe distingue original entregado, Dortmund pendiente y ELL condicionado, según el avance real.

Referencia histórica del modelo original: [Fredenslund, Jones y Prausnitz, 1975](https://doi.org/10.1002/aic.690210607). Sirve como fundamento; los valores usados deben corresponder a la edición de datos que se fije en U0.
