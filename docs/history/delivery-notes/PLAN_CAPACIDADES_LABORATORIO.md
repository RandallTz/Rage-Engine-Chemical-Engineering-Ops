# Las 20 mejoras: alcance y siguiente integración

No modificar el backend desde este trabajo. Cada capacidad debe declarar unidades, supuestos, procedencia, método ejecutado y diagnósticos. Una ficha o captura de datos no implica capacidad de cálculo.

| Mejora | Preparación disponible / trabajo pendiente |
|---|---|
| 1 Trazabilidad | Inspector, traza del motor y panel de revisión con bloques y conexiones de origen. Falta detalle de origen por término si la API no lo entrega. |
| 2 Cierre | Rango y grados de libertad de respuesta vigente; diagnósticos del motor. No contar fichas para inferir independencia. |
| 3 Dimensiones | Herramienta de productos con dimensiones SI. Validación automática completa requiere expresiones tipadas del ensamblador. |
| 4 Sustancias | Falta catálogo del proveedor con ID, fórmula, carga, masa molar, referencias y modelos admitidos. No inventar especies calculables. |
| 5 Elementos | El backend 9041197 verifica estequiometría y conservación elemental/masa para tasas especificadas. Catálogo general y carga iónica siguen pendientes. |
| 6 Comparación | Parámetros generales y por bloque, supuestos, estructura, resultados y procedencia. Versiones distintas de motor bloquean delta numérica. |
| 7 Referencias | Suites térmicas existentes. Cada modelo nuevo requiere caso analítico independiente y tolerancia justificada. |
| 8 Estados | Diferenciar formulación sin respuesta, respuesta validada/resuelta y respuesta desactualizada; respetar diagnósticos fuera de alcance. |
| 9 Fronteras | Biblioteca incluye condiciones. Solver de capas debe definir superficies e incompatibilidades antes de exponer editor ejecutable. |
| 10 Dinámica | Captura de inventario inicial; falta modelo temporal, estado inicial compatible y control de integración. |
| 11 Termoquímica | Hess, Kirchhoff y referencias de formación consultables. El motor ya declara referencia sensible y calor de reacción explícito. Energía acoplada con cinética general sigue pendiente. |
| 12 Equilibrio | Fundamentos disponibles; necesita actividades y estándares coherentes, restricciones y estabilidad. |
| 13 Entropía/exergía | Fundamentación disponible; faltan s de corrientes, temperaturas de frontera y ambiente de referencia. |
| 14 Capas | Captura geometría; integrar conducción 1D estacionaria con contacto y fronteras. |
| 15 Difusión | Fundamentos y bases de flujo; faltan propiedades, modelo y condiciones interfaciales en solver. |
| 16 Hidráulica | Fundamentos; integrar densidad/viscosidad, tuberías y pérdidas con rangos de validez. |
| 17 Sensibilidad | Utilizar llamadas al modelo validado; guardar escenarios, fallos y restricciones. No interpolar resultados como si fueran ejecuciones. |
| 18 Incertidumbre | Necesita rangos/distribuciones y unidades explícitas; declarar método de propagación y distinguir incertidumbre de parámetros y error de modelo. |
| 19 Compuestos | Definiciones compuestas existentes. Instanciación numérica general necesita puertos y variables tipados e IDs por instancia. |
| 20 Auditoría | Biblioteca, fuentes por área, dependencias y lista personal de revisión. Revisión bibliográfica ficha por ficha todavía necesaria. |

## Primera entrega requerida a Claude

Entrega 9041197 recibida: especies, estequiometría y tasas especificadas brutas/netas. La sección Motor reactivo ya llama a /laboratorio/resolver; el adaptador de la mesa sigue térmico/binario. Seguir PENDIENTES_BACKEND_CLAUDE.md para el trabajo restante.

## Contrato transversal

- Estado: formulado/incompleto/validado/resuelto/fuera de alcance. La vigencia depende de la firma física de entrada.
- Sustancias: ID del proveedor, fórmula elemental, carga, masa molar con unidad, referencia y modelos disponibles.
- Expresión: operador y argumentos tipados, variable ID, dimensión/base y términos de origen. LaTeX es salida, nunca código.
- Ecuación: ID, origen de bloque/conexión/término, supuestos aplicados, método, residuo y escala.
- Resultado: versión de motor/modelo, referencia de propiedades, unidades, fase y valores no disponibles explícitos.
- Casos independientes: conservación, restricciones físicas, errores, límites y regresión contra capacidades anteriores.
