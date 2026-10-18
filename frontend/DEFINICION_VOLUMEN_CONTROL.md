# Definición del volumen y papeles de sus variables

14 de octubre de 2026. Alcance: motor independiente `/motor`. Backend y laboratorio sin modificar. Claude conserva la responsabilidad del servicio termodinámico.

## Una definición que afecta al modelo

La vista Estado abre «Volumen de control». Las alternativas leen y modifican la formulación existente; no guardan una segunda etiqueta mecánica independiente:

| Elección | Efecto |
|---|---|
| Volumen fijo | Frontera fija, volumen geométrico declarado, dV/dt = 0 y trabajo de frontera nulo. |
| Frontera móvil | Conserva el término de trabajo de presión. No inventa la relación mecánica pendiente. |
| Presión exterior dada | Frontera móvil y presión uniforme prescrita, con trabajo P_ext dV/dt. La magnitud de P se declara con unidad en Resolver. |

Elegir volumen fijo inicia un dato geométrico vacío si no existía. Su valor debe ser constante, positivo y tener unidad compatible. Se reutiliza `volumen` o la clave del volumen del ensamblaje cuando ya existe; en otro caso se usa `geometria_V`. Estado y Resolver leen el mismo banco de datos. La geometría declarada aparece también en las ecuaciones finales, la trazabilidad y la serie V de los resultados energéticos.

El cambio queda registrado en los desgloses matemáticos y retira la referencia al resultado anterior. No borra masas iniciales, caudales ni propiedades declaradas. Los datos que dejan de ser activos se conservan para poder volver a otra formulación.

Una frontera fija por sí sola no prohíbe acumular masa. En el modelo homogéneo actual, imponer además densidad constante y V ocupado = V geométrico impone masa constante: el compilador rechaza entradas/salidas incompatibles y también m/ρ distinto de V geométrico. Un tanque parcialmente lleno requiere distinguir volumen geométrico y volumen ocupado y declarar el espacio restante; este cambio no introduce esa física silenciosamente.

## Datos, variables y relaciones

Estado muestra las condiciones iniciales por defecto; corrientes y parámetros se muestran bajo petición. Los valores se editan en Resolver, mediante enlaces al campo exacto. No se duplican formularios para un mismo dato.

- m_i y U: estados determinados por sus balances.
- T: variable algebraica obtenida de U = m u(T), únicamente cuando la relación manual uniforme está declarada.
- V: dato geométrico fijo, o resultado de m/ρ si la hipótesis de densidad constante y el balance energético correspondiente están activos. Si falta la relación, se indica pendiente.
- P: dato de frontera cuando se prescribe y se utiliza en las ecuaciones. Sin ecuación de estado o relación mecánica, se indica «Sin modelo», nunca «Calculada».
- T(0) o U(0): condición inicial, distinta de la temperatura de la corriente exterior y de T(t).
- c_u, u_ref, T_ref y ρ*: parámetros del modelo manual. No son incógnitas termodinámicas calculadas.

Las variables enlazan al balance, relación o dato que realmente existe. Una relación ausente se muestra como texto pendiente, sin un enlace a una ecuación inexistente. La visualización del mapa de estados se limita a la formulación total de masas; no etiqueta campos espaciales como si fueran estados de tanque.

## Separación con termodinámica

«Consultar propiedades» es una pestaña aparte. La evaluación puntual se conserva con su propia declaración y firma; no sustituye condiciones iniciales ni parámetros del solver. Una evaluación de fase puntual tampoco certifica el régimen durante una trayectoria.

La interfaz ya pudo leer un modelo de agua publicado por el servicio durante la revisión visual. No se ejecutó ni se validó aquí esa implementación física de Claude. El cierre termodinámico dinámico sigue requiriendo la entrega y comprobaciones del contrato `CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md`.

Para la integración futura, el coordinador debe leer la frontera y sus restricciones desde la formulación efectiva, y V/P desde sus declaraciones únicas. Una consulta UV/UP independiente no debe fijar automáticamente V/U del sistema dinámico. No se cambian las rutas ni el esquema de la evaluación puntual con esta entrega.

## Verificación

- `npm run test:motor-fundamental`: todas las suites pasan; conserva materia, acoplamientos, multicomponente y energía manual.
- `npm run test:volumen-control`: 229 comprobaciones; unidades, geometría compartida, compatibilidad material/energética, trabajo de frontera, papeles y relaciones, y referencias temporales.
- TypeScript y ESLint: sin errores en los archivos modificados.
- Navegador: definición compacta, abrir/cerrar datos, separación de consulta de propiedades y enlace a la relación energética verificados. Las hojas existentes no fueron editadas durante esa revisión visual.

No se agregan fases, EOS, propiedades reales, nuevos integradores ni un solver energético de varios volúmenes. Los límites del modelo manual siguen explícitos.
