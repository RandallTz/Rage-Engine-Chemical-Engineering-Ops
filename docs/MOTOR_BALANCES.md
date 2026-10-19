# Motor de balances

18 de octubre de 2026. Es el motor «Balances + Supuestos» de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §5. Recibe las ecuaciones fundamentales y los supuestos de cada volumen y produce las ecuaciones explícitas que resuelve el compilador común. Las ecuaciones se generan **en el servidor**, desde los supuestos que la hoja declara; el cliente solo dice qué dato es qué.

- **Código:** `core/balances/` (`generar(modelo)`).
- **Adaptador de hojas del Engine:** `frontend/motores/modelo/desdeHojaBalances.ts` (`modeloBalancesDesdeHoja`, `cabeEnBalances`).
- **Resolución:** `POST /modelo/resolver`. Si el modelo tiene volúmenes con estado supuesto y no trae `matematico`, `core/compilador/explicito.py` llama al motor de balances y resuelve lo generado.
- **Pruebas:**
  - `python tests/validar_motor_balances.py` (27, contra soluciones analíticas, con modelos escritos a mano);
  - `node frontend/verificar_bateria_multifisica.mjs` (todas las hojas del Engine frente al cálculo actual).

## 1. Recorrido

    hoja (supuestos, topología, datos)
      -> modelo común sin ecuaciones (desdeHojaBalances.ts)
      -> motor de balances: ecuaciones explícitas + restricciones (core/balances)
      -> compilador de ecuaciones escritas + solvers (core/compilador/explicito.py, core/solvers)
      -> resultados en el formato común

## 2. Leyes

Generales: no hay ramas por equipo, operación ni sustancia. Cada término aparece o no según los supuestos del volumen.

### Materia (forma total, masa de cada componente como estado)

    dm_iv/dt = Σ_s B_vs ṁ_is − Φ_iv,resto + G_iv − C_iv

| Término | Aparece si | Dato |
|---|---|---|
| ṁ_is por la corriente s (B = +1 si entra en v, −1 si sale) | el volumen no elimina el transporte (frontera fija, sin convección y sin difusión lo elimina) | `corrientes[s].materia`: por componente (másico, o molar · M_i) o total con fracciones |
| Φ_resto | la frontera restante no es impermeable (`restoImpermeable: false`) | `terminos["resto.<i>"]` |
| G, C | las fuentes no se han eliminado (`sinReaccion`, `sinGeneracion`, `sinConsumo`) | `terminos["generacion.<i>"]`, `terminos["consumo.<i>"]`; por volumen (tasa · V) si se declararon uniformes |

### Energía con u(T) declarada como supuesto (`u_lineal`)

    U_v = m_v u(T_v),   u(T) = u_ref + c (T − T_ref)
    dU_v/dt = Σ_s [max(q,0)·h(aguas arriba) + min(q,0)·h(v)] + Q̇ + Ẇ_τ + Ẇ_b + R − p·dV_v/dt

- q es el caudal másico total de la corriente hacia v. El donante se elige por el **signo** con max/min: ninguna dirección se supone.
- h = u(T) + p/ρ si la entalpía transporta la energía de flujo (`entalpia: true`). Si no, h = u(T) y el trabajo de flujo q·p/ρ se suma aparte.
- La corriente exterior usa la temperatura de su `estadoExterior`. Sin ella, la corriente solo puede salir: si se invierte, el cálculo se detiene.
- p·dV/dt solo con frontera móvil (`fija: false`), con dV/dt = (dm/dt)/ρ.
- **Requisitos de u(T) lineal**, que se comprueban y se rechazan con su motivo:
  - forma total;
  - acumulación;
  - energía cinética despreciable;
  - estado térmico uniforme;
  - régimen monofásico sin cambio de fase;
  - esfuerzos separados en presión y viscoso;
  - con corrientes o frontera móvil, presión impuesta y densidad.

## 3. Restricciones (dominio vigilado)

El cálculo se detiene en el instante en que una se incumpliría, localizado por bisección (`core/solvers/integrador.py`). Nunca se recorta.

| Restricción | Por qué |
|---|---|
| m_iv ≥ 0 | una masa no puede ser negativa (agotamiento) |
| G, C ≥ 0 | son tasas brutas |
| T_min ≤ T_v ≤ T_max | dominio de validez del supuesto u(T) |
| q_i·q_j ≥ 0 en una corriente convectiva | una corriente convectiva lleva todos sus componentes en el mismo sentido (la selectiva no) |
| −q ≥ 0 en una corriente exterior sin estado declarado | no puede entrar materia de estado desconocido |

## 3 bis. Lo que se publica además de los estados

- **Observables** (`observable.<id>`), por volumen con energía:
  - `volumen.v.T`, `volumen.v.dUdt` y `volumen.v.V`;
  - cada término de energía activo: `volumen.v.calor`, `trabajo_viscoso`, `fuerzas`, `fuente` y `trabajo_frontera`;
  - por corriente: `corriente.s.mdot`, `corriente.s.h` (entalpía del donante) y `corriente.s.E` (energía hacia el volumen).
- **Cierres de presupuesto** (`verificaciones`), con integrales auxiliares (`campo.aux_*`):
  - `estado.<u>`: cada estado frente a la integral de su propio balance;
  - `global.materia.<i>` y `global.energia`: el sistema completo frente a lo que cruza su frontera (corrientes exteriores, fuentes, calor y trabajos). Las transferencias internas deben anularse, y así se comprueba que la red está bien ensamblada.

El Resolver del Engine (`frontend/app/motor/resolverEngine.ts`) traduce todo esto al `ResultadoMotor` que leen las vistas, sin recalcular física.

## 4. Variables de las expresiones

Los datos son números o expresiones (gramática de `core/expresiones_motor.py`). Las variables se definen una sola vez como expresiones de los estados:

| Ámbito | Variables |
|---|---|
| todos los datos | `t`; por volumen v y componente de símbolo S: `m_S_v`, `m_total_v`; con volumen como dato, `V_v`, `rho_S_v`, `rho_total_v`; con energía, `T_v`, `U_v` |
| datos propios de un volumen (términos, y corrientes con un solo volumen en un extremo) | `m` (del componente del término; la total si hay uno), `m_total`, `m_S`, y con volumen `V`, `rho`, `rho_total`, `rho_S`; con energía, `T`, `U` y, con densidad, `rho` y `V = m/rho` |

Cada dato se pasa a SI con el servicio único de unidades. Se rechaza una unidad cuya dimensión no es la de la magnitud del término.

## 5. Contrato (campos opcionales del modelo común v0)

Ver [CONTRATO_MODELO_COMUN.md](CONTRATO_MODELO_COMUN.md) §1. Por volumen:

- `terminos` (clave → dato);
- `volumenDatoId`;
- `termodinamica.parametros` de u(T): `cId`, `uRefId`, `TRefId`, `TMinId`, `TMaxId` y `rhoId`;
- `inicial.energia`, ahora opcional sin balance de energía.

Por corriente, el modo `total_y_composicion`. En `restricciones`, la forma `{expresion, tipo, descripcion}`.

## 6. Evidencia (18 de octubre de 2026)

- **`tests/validar_motor_balances.py`, 27 comprobaciones contra analíticas:**
  - serie con caudales constantes;
  - cascada de Bateman;
  - recirculación cerrada, con conservación y la solución oscilante amortiguada;
  - conversión A → B;
  - fuente por volumen y caudal molar;
  - caudal total por fracciones;
  - agotamiento en t = 50 s;
  - convectiva que se invierte, detenida en t = 5 s;
  - energía: cerrado calentado, entrada caliente con cantidad constante, llenado con frontera móvil (T_in − T = (T_in − T0)(m0/m)^(in/(in−out))), y la parada en T_max en t = m c (T_max − T0)/Q;
  - diez rechazos con motivo y la comprobación estática.
- **Batería multifísica:** las 10 redes de volúmenes (acoplamiento y multicomponente, hasta 8 componentes con trazas), las 6 hojas de energía con u(T) y las 5 hojas de materia de un dominio en forma total. Todas iguales al cálculo actual del Engine, entre 1e-16 y 1e-9 relativo. Ver [BATERIA_MULTIFISICA.md](BATERIA_MULTIFISICA.md).

## 7. Fuera de esta versión

Responde `NoSoportado` con motivo en estos casos:

- **Sustitución por volumen o densidad media** (`cantidadVolumen`) y **campos espaciales:** siguen por el adaptador de ecuaciones escritas y, después, por el motor de discretización.
- **Reglas de estado; balance de momento; estacionario** (balance algebraico).
- **Caudales volumétricos.**
- **La función `step`**, que no tiene traducción al árbol común.
- **Energía con estado de equilibrio:** la lleva la entrada estructural del compilador con un paquete termodinámico.
