# Revisión de NRTL y reparto por componente — 15 de octubre de 2026

## Conclusión y alcance

La implementación tiene contrastes satisfactorios de la fórmula NRTL, las identidades termodinámicas y el equilibrio de etanol–agua. Eso distingue la corrección de la implementación de la calidad experimental de cada conjunto de parámetros. No equivale a certificar cualquier mezcla, presión o combinación de fases.

`core/mezclas.py` calcula NRTL para el catálogo de componentes, con matrices de interacción; `parametros_nrtl` carga parámetros asimétricos de **ChemSep NRTL** mediante `thermo.interaction_parameters.IPDB`. Un par sin datos se rechaza. Las ecuaciones de conservación no dependen de los nombres etanol o agua.

Las capacidades publicadas distinguen el contraste líquido–vapor para etanol–agua de predicciones cualitativas para otros pares y para separación líquido–líquido. El paquete `nrtl-lle-agua-butanol` es un ajuste distinto, con alcance propio. El vapor del paquete de mezcla es ideal, el líquido tiene volumen incompresible de referencia, y el dominio actual limita P a 5 bar y T a las correlaciones y a 0.9 Tc de cada especie. La estabilidad usa búsqueda con refinamiento y la vigilancia dinámica de fases es puntual dentro de cada paso.

## Elección del paquete

En **Estado → volumen → Paquete termodinámico** se puede seleccionar un paquete registrado y compatible. La selección modifica la identidad física de la hoja, conserva los datos numéricos e invalida resultados anteriores. El servidor vuelve a comprobar especies, dominio, referencias y frontera mecánica.

Se resolvió por HTTP el mismo calentamiento de etanol–agua con los mismos datos, cambiando únicamente el paquete y el identificador de solicitud:

| Paquete | Resultado | Certificación | T final |
|---|---|---|---|
| `nrtl-chemsep` | resuelto | cumple | 396.32503518004205 K |
| `mezcla-ideal` | resuelto | cumple | 384.58557892891207 K |

Los `modeloId` difieren. Peticiones y respuestas están en `qa_multifasico_2026_10_15/reparto/`. Es una comprobación de sustitución del paquete, no un argumento para considerar ideal esa mezcla.

El motor no elige silenciosamente otro paquete ni cambia de modelo en mitad de una trayectoria. Incorporar otro modelo exige registrar su adaptador, datos, dominio y verificaciones. No basta con escribir un identificador nuevo.

## Fracciones por componente

Se conservan tres magnitudes diferentes:

- **Fracción de fase**: qué parte de la mezcla está en esa fase, con base másica, molar o volumétrica.
- **Composición molar de fase**, `x_i^α`: qué parte de los moles de esa fase corresponde al componente i; incluye el vapor, habitualmente escrito `y_i`.
- **Reparto del componente**, `θ_i^α = n_i^α/n_i = β_α x_i^α/z_i`: qué parte del componente i está en esa fase. Este reparto es idéntico en masa y en moles para un mismo componente.

El botón **Reparto por componente** añade una gráfica por componente y volumen al tablero. Incluye cada ID de fase que aparece durante la trayectoria, por lo que también distingue dos líquidos. Las gráficas se pueden mover, editar y quitar; repetir la acción no duplica ni sobrescribe las existentes. La tabla de detalles muestra el mismo reparto para la muestra elegida.

Si una fase está ausente, la fracción asignada a ella de un componente presente en el sistema es cero. Si el componente está globalmente ausente, su reparto queda indefinido (`NaN` en presentación, celda vacía/guion en tabla y exportación), sin fabricar ceros. Las composiciones de fases ausentes siguen sin dato. No se recalcula un flash ni se modifica el certificado original.

En la muestra de 300 s del ejemplo del navegador:

| Componente | En vapor | En líquido |
|---|---|---|
| etanol | 0.8748421 | 0.1251579 |
| agua | 0.5564318 | 0.4435682 |

La composición molar de ese vapor es distinta: aproximadamente 0.5117563 etanol y 0.4882437 agua. Los denominadores son diferentes.

## Verificación realizada

- Contrastes NRTL existentes ejecutados de nuevo: **6 controles** de `ln γ` contra `thermo.nrtl`, Gibbs–Duhem, entalpía de exceso mediante derivada independiente, reconstrucción de h, azeótropo y fases a ambos lados. La primera comparación usa otra implementación, pero comparte los datos de interacción; no sustituye un contraste experimental.
- `tests/validar_motor_consolidacion_v2.py`: **128 comprobaciones**, código 0.
- La ejecución completa M0–M6 iniciada se detuvo por duración después de concluir los contrastes específicos y la consolidación. No se cuenta como aprobada ni como fallida en esta revisión.
- `verificar_reparto_componentes.mjs`: **215 comprobaciones**, con referencia manual, trazas de 1e-15, componentes ausentes, tres fases, trayectorias reales, conservación del reparto y cambio de paquete. Incluido en `test:motor-fundamental`.
- `npm run test:motor-fundamental`: código 0; la comprobación del reparto se volvió a ejecutar tras añadir las dos respuestas HTTP (215 en vez de 211).
- TypeScript y ESLint de los cuatro archivos de presentación modificados: sin errores.
- Navegador: gráficas de etanol y agua en paralelo, persistencia del orden tras recargar, tabla bifásica, selector de paquetes y evidencia del par verificados. La hoja conserva NRTL y todos sus datos originales.

Los cambios de este encargo se limitan a presentación, pruebas y documentación del frontend. No se modificaron la física del backend ni `/laboratorio`.
