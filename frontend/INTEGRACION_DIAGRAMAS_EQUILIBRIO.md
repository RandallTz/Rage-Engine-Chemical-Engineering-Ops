# Integración de diagramas y preparación multicomponente

15 de octubre de 2026. Seguimiento de `PLAN_DIAGRAMAS_EQUILIBRIO_MOTOR.md`. Backend/física: entrega de Claude en `docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md`. Este informe describe el trabajo de Codex en frontend, lectores, verificación y experiencia de `/motor`.

## 1. Resultado disponible

En **Resultados → Equilibrio**, una hoja binaria compatible puede calcular T–xy y P–xy en paralelo. Cada panel identifica su condición fija y tiene actualización independiente. El paquete procede del volumen; no se elige por nombre de ejemplo ni se sustituye ante un fallo.

El instante seleccionado suministra P para T–xy y T para P–xy. Se pueden cambiar referencias manualmente, con sus unidades, dentro de opciones. Las preferencias visuales quedan fuera de la firma física del ensamblaje. Entrar en esta vista no ejecuta el trazado hasta solicitarlo. Cambiar de pestaña no destruye los diagramas ya calculados.

Las líneas unen únicamente puntos certificados dentro de cada segmento del backend. Los candidatos descartados no se dibujan. Los segmentos separados por competencia LL, dominio, presupuesto o convergencia no se conectan. La interfaz no deduce una región estable a partir del aspecto de la curva.

El componente del eje es seleccionable: la presentación toma las composiciones del ID elegido de las dos fases límite, conservando el orden de los pares de coexistencia. No vuelve a ejecutar un flash ni ordena por separado el vapor para conseguir una curva suave.

## 2. Identidad, huellas y marcadores

- Copias sincronizadas de `contratoDiagramasEquilibrio.ts` y `contratoEnsamblajeV2.ts`; este último incorpora `resultados.procedenciaModelo`.
- El lector comprueba que cada volumen esté identificado una sola vez en la procedencia, con su modelo, especies y huella.
- Las consultas de una trayectoria nueva envían `huellaModeloEsperada`.
- Los marcadores requieren coincidencia de modelo, versión, componentes, huella y condición fija. Una condición manual diferente o una muestra posterior al corte sin certificar no se superpone como comparable.
- Las ejecuciones históricas sin procedencia siguen siendo legibles. Se pueden consultar diagramas, pero no superponerlas como si sus parámetros estuvieran comprobados; la vista ofrece volver a resolver.
- La coexistencia límite no se representa como una fase material de cantidad positiva ficticia. Los puntos del diagrama no tienen beta, fracción másica ni volumétrica. Las muestras sí conservan sus fases y cantidades reales.

El lector verifica coherencia del certificado y los metadatos; no repite la ecuación de estado ni demuestra el mínimo global de Gibbs. La prueba de estabilidad y su alcance siguen siendo responsabilidad del paquete del backend.

## 3. Preparación general para N componentes

`contextoMuestraEquilibrio` y `verificarEstadoMateriaRed` recorren los componentes por ID y las fases efectivamente publicadas. No contienen un caso de agua, etanol, binario o ternario para reconstruir la materia.

Se obtiene, por muestra y componente:

```text
N = sum_i n_i
n_i^alpha = N beta_alpha x_i^alpha
m_i^alpha = n_i^alpha M_i
Delta n_i = sum_alpha n_i^alpha - n_i
Delta m_i = sum_alpha m_i^alpha - n_i M_i
```

Las cantidades integradas y las reconstruidas se conservan separadas. No se redondea, recorta ni renormaliza un resultado para cerrar el residuo. El reparto de un componente globalmente ausente queda indefinido; su cantidad cero permanece explícita.

En **Detalles técnicos → Reconstrucción de materia por fase** se pueden inspeccionar las cantidades, sumas y residuos con sus unidades. Es una reconstrucción del estado, no una nueva certificación del balance dinámico completo.

Se reforzó además el lector para comprobar:

1. Potencial químico declarado para cada componente presente, sin claves omitidas o ajenas.
2. La identidad molar `sum_i x_i mu_i = M_fase (h_fase - T s_fase)` y, cuando las unidades extensivas están declaradas, la reconstrucción de G total.
3. Unidades SI de las variables de estado, incluso si el catálogo y la serie fueron alterados a la misma unidad equivocada.

**Límite físico todavía real:** el backend publica estabilidad de mezclas verificada hasta tres componentes. Las pruebas estructurales de lectura/presentación para 5, 8 y 12 componentes no habilitan esa física. No se retiró la cota ni se simuló que esos flashes existían.

Al ampliar esa capacidad, la siguiente tarea de núcleo es generalizar y contrastar la búsqueda de estabilidad y el reparto de fases para más componentes, manteniendo el ensamblaje común y publicando límites numéricos honestos. No basta con aumentar una constante ni con repetir agua–etanol. Los cortes binarios iniciales no deben convertirse en una restricción del motor multicomponente.

## 4. Lectura de diagramas, caché y exportación

`lectorDiagramasEquilibrio` comprueba revisión, correlación de petición/respuesta, modelo, huella esperada, componentes, condiciones originales/SI, perfiles, referencias, normalización, puntos y certificados. Respeta que `distincion_fases` es una comprobación de separación mínima, no un residuo cuyo valor deba ser menor que la tolerancia.

Verifica también que los segmentos referencien puntos existentes, que reconstruyan la cobertura y que no atraviesen huecos. Un recorrido completo puede incluir intervalos explorados sin LV estable; eso es distinto de un hueco por fallo numérico o dominio, y requiere su incidencia de fase competidora. No se presenta un presupuesto agotado como recorrido completo.

La caché en memoria es acotada (16 entradas), solo reutiliza resultados completos con huella conocida y conserva la pareja de petición/respuesta original. La clave incluye identidad de componentes, modelo/huella, corte normalizado, intervalo, eje, perfil y versión del trazador. No se reescribe `solicitudId` para fingir que un resultado guardado es una nueva respuesta HTTP. Cambiar nombres visuales o unidades equivalentes no cambia la física. Las respuestas parciales por fallo no quedan bloqueadas en caché.

El control de generaciones y AbortController impiden que una respuesta vieja sustituya una selección nueva. Abortar la espera no se presenta como prueba de que Python haya detenido un cálculo; el presupuesto cooperativo pertenece al backend.

Exportaciones:

- JSON con petición y respuesta originales, incluyendo certificados, incidencias y procedencia.
- CSV con rama, segmento, punto, T/P en SI, composiciones x/y por ID y estado del certificado. No incluye interpolaciones como si fueran cálculos certificados.

No se añadieron dependencias ni cálculos de flash en el frontend. Los diagramas calculados permanecen en memoria durante la vista; solo se persisten preferencias ligeras. El archivado duradero de diagramas en IndexedDB queda para una necesidad posterior, evitando aumentar localStorage con datos voluminosos.

## 5. Verificación ejecutada

| Comprobación | Resultado |
|---|---|
| `python -u -X utf8 tests/validar_motor_diagramas_equilibrio.py` | **78 OK**, script original sin alterar |
| `node tests/verificar_contrato_diagramas.mjs` | **11 pares reales** compilados y **285 puntos** comprobados |
| `npm run test:motor-fundamental` | Código 0, incluidas las regresiones existentes y los verificadores nuevos |
| `node verificar_preparacion_diagramas_equilibrio.mjs` | **1866 comprobaciones**: reconstrucción, unidades, fases, controles negativos y tamaños arbitrarios de catálogo |
| `node verificar_diagramas_equilibrio.mjs --ui` | **2468 comprobaciones**, incluidas exportaciones reales del navegador, huellas y marcadores |
| TypeScript y ESLint de los archivos modificados | Sin errores |

Los ensayos estructurales de 1, 2, 3, 5, 8 y 12 componentes, una a tres fases y escalas de cantidad `1e-12`, `1`, `1e12` son identidades algebraicas controladas. No son una ecuación de estado sintética publicada ni una validación de estabilidad para N>3.

La primera ejecución aislada de la batería física quedó esperando en la comprobación HTTP interna; se detuvo ese proceso y se repitió el mismo archivo sin modificar sus pruebas, fuera del aislamiento. Esa pasada completa terminó con las 78 comprobaciones correctas. Evidencia en `.tmp/diagramas-fisica-completa.log`.

Se ejecutó una vez la regresión completa del motor del frontend; las ampliaciones posteriores de caché/exportación/lectura se comprobaron con sus verificadores específicos y TypeScript/lint. No se afirma haber repetido toda la batería histórica del backend en esta entrega de frontend.

## 6. Revisión de extremo a extremo en navegador

Hoja de prueba: `motor-multifasico-v2-1`. Se volvió a resolver sin cambiar sus datos: 0.4 mol de etanol, 0.6 mol de agua, T inicial 330 K, P prescrita 101325 Pa, calor constante 100 W, frontera térmica 600 K y horizonte 450 s. Se conservaron sus gráficas y preferencias existentes. La nueva respuesta contiene 102 muestras y procedencia del paquete.

Para la muestra **t = 181.8181818 s**, T ≈ **354.68884 K** (81.53884 °C), P = **101325 Pa**:

- T–xy: 47 puntos, recorrido completo, sin huecos.
- P–xy: 47 puntos, recorrido completo, sin huecos.
- Ambos diagramas exigen y devuelven la misma huella de parámetros de la trayectoria.
- Las composiciones líquida/vapor de la muestra aparecen en sus cortes correspondientes.
- Mover el instante a la siguiente muestra mantiene la comparación T–xy al conservarse P; retira el marcador de P–xy porque cambia T. No proyecta esa muestra sobre el corte antiguo.
- Cambiar el eje a agua transforma x/y sin recalcular el equilibrio. Cambiar a K/kPa modifica únicamente presentación; se restauraron °C/bar y etanol.
- La tabla de reconstrucción muestra 0.2298508 + 0.1701492 = 0.4 mol de etanol y 0.1655310 + 0.4344690 = 0.6 mol de agua en vapor/líquido, respectivamente. Los cálculos/exportaciones mantienen precisión completa.

Evidencias archivadas bajo `frontend/qa_diagramas_2026_10_15/`: `trayectoria-ui.json`, `txy-ui.json`, `pxy-ui.json`. Los dos últimos se descargaron desde la interfaz, no se fabricaron a partir de otro proveedor ni se corrigieron antes de validarlos.

## 7. Coordinación y pendientes

El backend local se recargó para activar las rutas nuevas; no se modificaron su código físico, `/laboratorio`, `thermodynamics/proveedor.py` ni cambios de Claude. Sin commit ni push.

Los límites de la entrega física siguen siendo los publicados: vapor ideal hasta 5 bar, dominio de correlaciones del par, búsqueda de estabilidad mediante malla/refinamiento y continuación parametrizada por composición líquida sin longitud de arco. Una coincidencia diagrama–trayectoria comprueba coherencia interna, no sustituye datos experimentales independientes.

Quedan fuera: superficies 3D, diagramas completos LL/LLV/SLE, cortes multicomponente y ampliar la estabilidad física más allá de las capacidades verificadas actuales. El lector y la reconstrucción están preparados para transportar catálogos de tamaño general cuando el backend amplíe esas capacidades.
