# Guía para agentes (Claude, Codex, Gemini u otros)

Antes de cambiar nada en este repositorio, lee en este orden:

1. [ARQUITECTURA_MOTOR.md](ARQUITECTURA_MOTOR.md): qué es el simulador, el motor de motores, el modelo común, la termodinámica siempre presente, dónde vive hoy cada pieza, las reglas de trabajo y el orden de migración.
2. Los contratos comunes:
   - [docs/CONTRATO_MODELO_COMUN.md](docs/CONTRATO_MODELO_COMUN.md): el modelo;
   - [docs/CAPA_TERMODINAMICA.md](docs/CAPA_TERMODINAMICA.md): la termodinámica siempre presente;
   - [docs/SERVICIO_UNIDADES.md](docs/SERVICIO_UNIDADES.md): unidades;
   - [docs/FORMATO_RESULTADOS.md](docs/FORMATO_RESULTADOS.md): resultados y gráficas;
   - [docs/CORTE_VERTICAL.md](docs/CORTE_VERTICAL.md): compilador y solver propios, de punta a punta.
   - [docs/MOTOR_BALANCES.md](docs/MOTOR_BALANCES.md): ecuaciones generadas en el servidor desde los supuestos de cada volumen;
   - [docs/BATERIA_MULTIFISICA.md](docs/BATERIA_MULTIFISICA.md) (generado): qué hojas resuelve el Engine común y qué falta.
3. [frontend/MAPA_MOTOR.md](frontend/MAPA_MOTOR.md): inventario funcional del motor actual (`/motor`), su alcance y su verificación.
4. El documento de continuidad o de alcance de la pieza que vayas a tocar:
   - adimensionalización: [frontend/ADIMENSIONALIZACION_ALCANCE.md](frontend/ADIMENSIONALIZACION_ALCANCE.md) y [frontend/CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md](frontend/CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md);
   - motor: [frontend/ROADMAP_MOTOR_MULTIFISICO.md](frontend/ROADMAP_MOTOR_MULTIFISICO.md).

**Prioridades vigentes** (decisiones del usuario, ARQUITECTURA_MOTOR.md §9.1 y §10 «Orden vigente»): UNIFAC con prioridad completa y NRTL sin tratar; primero pulir la termodinámica, después los balances pendientes del checklist; la discretización y el mallado son del motor de solvers y transformación, un paso posterior a la adimensionalización; Ecuaciones y Adimensionalización se unificarán en una hoja única (§11).

Reglas mínimas (detalle en ARQUITECTURA_MOTOR.md §8):

- Sin commit ni push salvo que el usuario lo pida; al commitear, archivo por archivo, nunca `git add -A`.
- No modificar `/motor`, `/laboratorio` ni sus backends sin encargo expreso.
- La interfaz no calcula: ciencia, unidades y solvers en Python.
- Todo modelo parte de las ecuaciones fundamentales y llega al modelo con supuestos registrados; nunca se plantea el modelo directamente (ARQUITECTURA_MOTOR.md §2, principio 10).
- Cada ecuación va en su lugar: un panel (materia, energía, momento, termodinámica) muestra solo su familia; la clasificación está en `frontend/app/motor/ubicacionEcuaciones.ts` (ARQUITECTURA_MOTOR.md §8).
- Toda fórmula se comprueba numéricamente contra una referencia antes de darla por buena.
- No detener procesos ajenos (frontend en 3000, backends en 8004 y 8005); los propios, por PID.

`frontend/AGENTS.md` añade las notas propias de Next.js para el código del frontend.
