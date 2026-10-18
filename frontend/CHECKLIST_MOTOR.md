# Checklist del motor

## Materia

- [x] Balance fundamental: local → integral → total
- [x] Supuestos y derivación paso a paso
- [x] Catálogo de componentes por ID
- [x] Corrientes: caudal por componente o total + composición
- [x] Acumulación, llenado y vaciado
- [x] Generación y consumo materiales declarados
- [x] Acoplamiento de varios volúmenes
- [x] Balances por componente y conservación global
- [x] Transporte convectivo y difusión 1D cartesiana
- [x] Variables, datos pendientes y recuento estructural
- [x] Unidades, resolución temporal y resultados
- [ ] Transferencia selectiva acoplada a termodinámica en /motor
- [ ] Cinética reactiva acoplada a la termodinámica real
- [ ] Caudales acoplados al balance de momento
- [ ] Resolución espacial en otras geometrías y dimensiones
- [ ] Resolución inversa general de sistemas ensamblados

## Termodinámica

- [x] Separación entre conservación, estado e hipótesis
- [x] Selección de paquete y procedencia de parámetros
- [x] Registro de sustancias y admisión por datos de cada paquete
- [x] Datos puros publicados con unidades, fuentes, dominios y huellas
- [x] Sustitución coherente de volumen líquido, Cp ideal y presión de vapor
- [x] Acetona incorporada por registro y contrastada
- [x] Corrientes entre paquetes de mezcla con la misma referencia
- [x] Agua pura: IAPWS-95
- [x] Estados TP, PH, UP y UV
- [x] Gibbs, Helmholtz, entropía y potenciales químicos
- [x] Mezclas ideales y NRTL con parámetros disponibles
- [x] Flashes contrastados: ideal hasta 7; NRTL hasta 4 componentes
- [x] UNIFAC original y Dortmund: grupos, energía y equilibrio predictivo
- [x] UNIFAC-ELL: 7 especies, entre 10 y 40 °C; metanol sin datos
- [x] Equilibrio líquido–vapor
- [x] Equilibrio líquido–líquido y LLV: agua–butanol
- [x] Hielo y equilibrio sólido–líquido–vapor del agua: estático
- [x] Diagrama P–T del agua con hielo
- [x] Fracciones de fase y reparto por componente
- [x] Diagramas binarios T–xy y P–xy
- [x] Certificados, dominios y controles de coherencia
- [ ] Parámetros completos y contrastes NRTL con 5 o más componentes
- [ ] Corrientes materiales entre IAPWS y paquetes de mezcla
- [ ] Mayor contraste experimental de las predicciones UNIFAC
- [ ] Vapor no ideal y mezclas a alta presión
- [ ] Regiones críticas fuera del dominio actual
- [ ] Equilibrio sólido–líquido de mezclas
- [ ] Equilibrio químico acoplado a reacciones
- [ ] Diagramas completos LL, LLV y sólido–líquido
- [ ] Continuación de curvas con pliegues
- [ ] Cortes multicomponente y superficies de equilibrio

## Energía

- [x] Primera ley: local → integral → total
- [x] Supuestos y derivación paso a paso
- [x] Acoplamiento de inventarios y energía
- [x] Transporte de entalpía por corrientes
- [x] Calor y trabajo de frontera explícitos
- [x] Recipiente rígido con presión calculada
- [x] Presión prescrita constante o suave
- [x] Contacto térmico entre volúmenes
- [x] Cambio de fase durante la trayectoria
- [x] Extracción por fase y eventos de fase ausente
- [x] Conservación energética y certificación de muestras
- [x] Segunda ley cuando se conoce la temperatura de frontera
- [ ] Energía de reacción con referencias termodinámicas coherentes
- [ ] Cambio de fase sólido durante la dinámica
- [ ] Transporte energético espacial acoplado a propiedades
- [ ] Transferencia de calor y materia fuera del equilibrio
- [ ] Trabajo mecánico acoplado al balance de momento
- [ ] Presiones discontinuas con regla física de salto
- [ ] Detección de transiciones no capturadas por el muestreo de pasos
