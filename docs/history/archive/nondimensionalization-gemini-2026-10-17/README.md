# Módulos retirados de `/adimensionalizacion` (17–18 de octubre de 2026)

Estos 23 archivos se retiraron de `frontend/app/adimensionalizacion/` durante la auditoría del frontend y se conservan aquí sin cambios, fuera de la compilación. No estaban en git y su contenido no se ha borrado.

## Por qué se retiraron

Presentaban como análisis del modelo del usuario resultados que no se calculaban a partir de él:

- **Decisiones por nombre de grupo.** Muchos módulos deciden por subcadenas del id de un grupo (`includes("pe")`, `includes("da")`, `includes("k")`…). El núcleo llama a los grupos `G1`, `G2`…, así que esas ramas casi nunca coincidían y caían siempre en el mismo caso por defecto.
- **Números fijos.**
  - `analisisEstabilidad.ts` usa un jacobiano fijo (0.6, −1.0, 1.2, −0.8) para cualquier modelo.
  - `analisisEstabilidadNumerica.ts` usa Pe = 10 y Da = 2 inventados.
  - `exportarSimulacion.ts` integra una cinética fija (u − u³ − v) y la firma como generada por el núcleo.
- **Condiciones inventadas.** `analisisCondicionesFrontera.ts` añade condiciones de Robin, Neumann, Dirichlet e inicial que el usuario no declaró.
- **Simetrías mal derivadas.** `analisisSimetriasLie.ts` declara siempre que el modelo admite autosimilitud. Para reacción-difusión publica una reducción que no es válida: un término de reacción rompe la invariancia de escala.
- **Un simulador que no es el del modelo.**
  - `SimuladorEnVivo.tsx` integra siempre una ecuación genérica de convección-difusión-reacción, no la del usuario.
  - Usa Euler explícito con Δt = 4·10⁻⁴, mientras que el límite de estabilidad con Fo = 1 y 80 nodos es ≈ 8·10⁻⁵.
  - Los NaN se sustituían por cero, lo que ocultaba la divergencia.
- **Paquete de publicación fijo.** `paquetePublicacion.ts` incluye un manuscrito con resultados («demostramos…») que no dependen del modelo.
- **Importador falso del motor.** `puenteMotor.ts` no lee las ecuaciones de las hojas de `/motor`: fabrica una ecuación genérica según un indicador.

## Qué los sustituye

Las ideas se conservan, pero ahora con cálculo real en el núcleo (`core/adimensionalizacion/estudio.py`, `asintotica.py`, `dinamica.py`, `simetrias.py` y `simulacion.py`, con la operación `estudiar`). Cada análisis tiene pruebas contra resultados analíticos conocidos en `tests/validar_estudio_adimensionalizacion.py`. La interfaz los presenta en la pestaña Estudio: `EstudioFormulacion.tsx` y las vistas `Vista*.tsx`.
