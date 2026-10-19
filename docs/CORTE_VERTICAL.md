# Corte vertical: el modelo común resuelto por sus propios motores

18 de octubre de 2026. Paso 4 de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §10. Es el primer recorrido completo por la arquitectura nueva, sin pasar por el motor anterior:

    modelo común (core/modelo)
      -> relaciones siempre presentes (core/modelo/relaciones.py)
      -> capa termodinámica (core/termodinamica)
      -> compilador (core/compilador)  -> solver (core/solvers)
      -> resultados en el formato común (core/resultados)
      -> motor de gráficas (frontend/componentes/graficas)

**Rutas HTTP**

- `POST /modelo/validar` con `{modelo}`: devuelve las relaciones y las variables de la capa.
- `POST /modelo/resolver` con `{modelo}`: devuelve un conjunto de resultados en el formato común.

## 1. Compilador (`core/compilador/compilador.py`)

Ejecuta las relaciones del modelo **sin ramas por equipo, operación ni sustancia**:

| Relación | Forma ejecutada |
|---|---|
| Materia, por volumen y componente | dn_vi/dt = Σ_s B_vs·ṅ_s·x_si |
| Energía, por volumen | dE_v/dt = Σ_s B_vs·ṅ_s·h_s + Σ_q B_vq·Q_q (+ V_v·dP_v/dt) |
| Estado | E = U con frontera rígida (cierre UV, V dato); E = H con presión prescrita (cierre PH, P(t) dato) |
| Equilibrio | El de la capa termodinámica en cada evaluación: las fases son un resultado |
| Corriente | Caudal dato; composición y entalpía del **donante** según el signo actual del caudal. El donante es un volumen (mezcla, o una fase con criterio físico si hay dos líquidos) o el exterior (estado TP declarado) |
| Intercambio | Q dato (impuesto) o G·(T_desde − T_hasta) (conductancia) |
| Verificación | Integrales auxiliares de la materia y la energía intercambiadas con el exterior; residuo de conservación global |

- Los datos (número o expresión en `t`) pasan a SI con el servicio único de unidades. Las expresiones las analiza `core/expresiones_motor`, incluida la derivada dP/dt.
- Las evaluaciones internas usan el cierre rápido (`core/termodinamica/volumen.py`, con semilla y sin prueba de estabilidad completa).
- Cada muestra publicada se certifica con `capa.cierre`: todas las candidatas con su `tm`.

## 2. Solver (`core/solvers/integrador.py`)

Dormand-Prince 5(4) con tolerancias por componente. El sistema le ofrece `rhs(t, y)` y `firma(t, y)`, un valor discreto cualquiera; aquí es el conjunto de fases de cada volumen, pero el solver no lo sabe.

- **Si la firma cambia dentro de un paso:** biseca sobre la salida densa, re-integra hasta el instante del cambio y reinicia allí, para no promediar a través de la arista de las propiedades.
- **Si una etapa falla:** reintenta con un paso menor.
- **Si el sistema lanza `Detencion`** (agotamiento, fase extraída ausente…): la trayectoria se detiene con su código.
- **Si el sistema no admite el nuevo régimen** (`admite(firma)` devuelve un motivo, por ejemplo una política de fases monofásica y aparece otra fase): se detiene en el instante del cambio con código `politica_incumplida`.

## 3. Evidencia

`python tests/validar_corte_vertical.py` (71 comprobaciones). El **mismo código** resuelve:

| Sistema | Contra | Resultado |
|---|---|---|
| Prueba guía: benceno + tolueno (ideal), 100 W desde 330 K | Raoult en forma cerrada, H = H₀ + Q t y el motor existente en vivo | Vapor a 365,275 K y líquido fuera a 371,919 K (1e-4 K); estado igual al motor (1e-7); eventos en el mismo instante (1e-6 s) |
| Agua pura (IAPWS-95) que hierve | IF97 y el motor en vivo | T_sat (5 mK) y calor de la meseta = n·h_fg (1e-3); estado igual al motor |
| Dos volúmenes con corriente y conductancia | Respuesta publicada del motor | Diferencias del orden de 1e-9 |
| Dos aguas rígidas (UV) en contacto térmico | Respuesta publicada | 1e-9 |
| Decantador agua-butanol con extracción de la fase líquida menos densa | Respuesta publicada | 1e-16 |
| Etanol-agua NRTL que hierve | Respuesta publicada | 1e-11, eventos idénticos |

En los seis casos se cumple además:

- conservación global de materia y energía por debajo de 1e-12;
- complementariedad por debajo de 1e-8;
- todas las fases candidatas publicadas en cada muestra, con β = 0 antes de aparecer.

Una comprobación estática verifica que el compilador, el solver, la capa, las relaciones, los resultados y las unidades no mencionan equipos, operaciones ni sustancias.

`node verificar_corte_vertical.mjs` (14 comprobaciones): la ruta HTTP devuelve el mismo conjunto, y el motor de gráficas lo dibuja, incluida la β de todas las candidatas frente al tiempo.

## 4. Segunda entrada: ecuaciones escritas (paso 5.1)

`core/compilador/explicito.py`. Un modelo cuyos volúmenes declaran su estado como supuesto y que trae `matematico` se ejecuta tal como está escrito: una ecuación d u/dt = f(t, u, parámetros) por variable de campo y una condición inicial por variable. `resolver()` elige la entrada; la estructural no cambia.

- Valores en SI desde `datos["matematico.<id>"]`, con comprobación de que la unidad corresponde a la dimensión del símbolo.
- Métodos: RK45 (`rk45`) o BDF implícito (`euler_implicito`, `bdf`).
- Dominio: `restricciones` no negativas → evento `agotamiento` en el instante exacto, por bisección sobre la salida densa (`core/solvers/integrador.py`, `dominio(t, y)`); un cero en t = 0 con derivada negativa detiene en t = 0.
- Rechaza con motivo: coordenadas espaciales y operadores diferenciales (motor de discretización, 5.2), ecuaciones algebraicas (DAE), orden mayor que uno, funciones declaradas sin definición, condición inicial que depende de variables, unidad incompatible, dato pendiente.

## 5. Evidencia de la segunda entrada

- `python tests/validar_compilador_explicito.py` (27 comprobaciones), con modelos escritos a mano, sin volúmenes ni componentes:
  - logístico con la tasa en 1/min, contra la analítica (1e-7);
  - oscilador como sistema de primer orden (1e-8);
  - agotamiento detenido en m0/k exacto (1e-6 s) y, sin restricción, la recta que sigue;
  - rígido y' = −a(y − cos t), a = 1e4: BDF igual a la analítica y con menos de 1/20 de los pasos de RK45;
  - ocho rechazos con motivo, la ruta HTTP y la comprobación estática (ningún equipo ni sustancia en el código).
- `node verificar_compilador_explicito.mjs` (76 comprobaciones): las seis hojas de materia de prueba sin campo espacial, llevadas al modelo común por `modeloDesdeHojaMotor` y resueltas por `POST /modelo/resolver`, con RK45 y con el método implícito. Mismo estado y tiempo final que el solver TS; frente a la analítica y al solver TS, entre 1e-16 y 1e-11 (RK45). Con el implícito, el compilador queda a 4e-9 de la analítica y el Euler implícito del solver TS a 1.3e-5. Las dos hojas 1D se rechazan con su motivo.

## 6. Fuera de esta versión

El compilador responde `NoSoportado` con motivo en estos casos:

- **Fuentes materiales (reacción):** corresponden al motor de constitutivas.
- **Caudales volumétricos.**
- **Volúmenes con estado supuesto:** el compilador exige el cierre de equilibrio.
- **U inicial con presión prescrita.**
- **Momento, campos espaciales (1D) y estacionario:** son las fases F3 a F7 del roadmap.
