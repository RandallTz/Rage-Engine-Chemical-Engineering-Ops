# Diseño C4: frontera abierta, agua con gases no condensables y caudal calculado

Encargo: `frontend/ENCARGO_CLAUDE_CONSOLIDACION_MULTIFASICA_2026_10_15.md` §6. **Documento de diseño y
viabilidad; nada de esto está implementado ni publicado como capacidad.** El servicio actual rechaza los
campos propuestos aquí (`MOTOR_ENS_CAMPO_NO_ADMITIDO`) y sigue exigiendo todos los caudales como datos.
Borrador tipado: `docs/contratos/borradorFronteraAbierta.ts` (compila contra la revisión 2; no es una
revisión publicada).

Caso de referencia, sin solución objetivo: 3 L interiores, 2 kg de agua total, 10 °C, 1 atm inicial, aire
seco 79/21 molar N2/O2, calor neto constante declarado. Dos cierres: hermético y abierto a la atmósfera.

## 1. Por qué el agua pura no sirve como atajo del caso abierto

Agua pura con líquido y vapor en equilibrio tiene un grado de libertad intensivo (regla de las fases,
F = C − π + 2 = 1): fijar T fija P = Psat(T). A 10 °C, Psat = 1228.2 Pa (IAPWS-95), no 101 325 Pa. Con 2 kg
en 3 L el líquido no llena el recipiente, así que no hay otro mecanismo que suba la presión del espacio de
cabeza. El estado «agua pura, 10 °C, 1 atm, con espacio de vapor» **no existe**; imponer P = 1 atm con V fija y
salida calculada no tendría solución inicial (el caudal tendría que ser de entrada y de agua pura gaseosa a
1 atm, que a 10 °C condensaría). La hoja de agua pura hermética resuelta (P0 = 1228 Pa) es correcta para su
idealización, que no representa cerrar una olla con aire.

Alternativa distinta, que es otra elección de volumen de control: dominio del líquido solo, con superficie
libre a P ambiente y la atmósfera fuera. Entonces la evaporación hacia el exterior es una transferencia
interfacial con su propia ley (difusión/convección de vapor en aire), no un equilibrio local: queda fuera
de este diseño y no debe simularse con un coeficiente inventado.

## 2. Paquete propuesto: agua condensable + gases no condensables

Identidad propuesta: `agua-iapws95-aire-virial` versión 1 (nombre provisional).

### Fases y especies

- **Líquido**: agua pura IAPWS-95 a la presión total (incluye el término de Poynting de forma natural).
  **Hipótesis declarada: N2 y O2 insolubles** (disolución despreciada). A 25 °C, con el gas puro a 1 atm, la
  fracción molar disuelta es ~2.3e-5 (O2) y ~1.2e-5 (N2) por la ley de Henry; con aire, unas 5 y 1.3 veces
  menos respectivamente: efecto despreciable en balances de energía y
  volumen, no en química del agua (que no se modela). Henry sería una ampliación con datos propios.
- **Gas**: N2, O2 y H2O(g). No se crean líquidos de N2/O2 ni se extrapolan correlaciones de líquido a 300 K
  (ambos supercríticos: Tc = 126.2 K y 154.6 K). Argón omitido explícitamente (o como tercera especie si se
  quiere aire de composición estándar).

### Por qué no basta el gas ideal para el vapor

El segundo coeficiente de virial del agua según IAPWS-95 (límite de ∂αʳ/∂δ en δ → 0) da en saturación
`Z − 1 ≈ B Psat/(R T)`:

| T | B (cm³/mol) | Z_sat − 1 |
|---|---|---|
| 283.15 K | −1645 | −0.09 % |
| 323.15 K | −832 | −0.38 % |
| 373.15 K | −451 | −1.47 % |
| 393.15 K | −371 | −2.26 % |

En el hermético el contenido pasa de 100 °C; un vapor ideal desplazaría la presión de vapor ~2 % y rompería
el límite «aire → 0» frente al paquete `agua-iapws95` ya verificado. Por eso el gas usa una **ecuación de
virial truncada en el segundo coeficiente**, coherente termodinámicamente:

```
Z = 1 + B_mez(T, y) P/(R T),     B_mez = Σ_i Σ_j y_i y_j B_ij(T)
ln φ_i = (2 Σ_j y_j B_ij − B_mez) P/(R T)
h^res = P (B_mez − T dB_mez/dT),   s^res = −P dB_mez/dT,   v = R T/P + B_mez
```

Todas las propiedades del gas salen de esa única función (G residual = B_mez P), igual que en las mezclas
actuales. B_ww(T) se toma de IAPWS-95 (mismo límite que arriba, con su derivada); B_aa de una EOS de
referencia del aire seco o de N2 y O2; B_aw cruzados de una fuente primaria (ver §6).

### Referencias y potenciales

- Agua: referencia IAPWS-95 (u = s = 0 del líquido en el triple) en **ambas** fases. La parte ideal del gas
  de agua sale de φ° de IAPWS-95, de modo que el vapor ideal y el líquido comparten exactamente esa
  referencia, sin tabla externa de cp.
- N2 y O2: gas ideal con `h = s = 0` a 298.15 K y 1 bar, cp de una fuente primaria (p. ej. NASA-7 o el
  término ideal de su EOS de referencia).
- Mezclar referencias **por especie** es legítimo sin reacción (la consolidación C3 comprueba la invariancia
  ante desplazamientos por especie). Lo que no es legítimo es conectar por una corriente un volumen de este
  paquete con otro cuya agua use otra referencia: la conversión tendría que ser explícita o la conexión se
  rechaza, como hoy (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`).
- Equilibrio del agua: `μ_w^L(T, P) = μ_w^{ig}(T, P0) + R T ln(y_w P φ_w/P0)`. **No** se impone
  `P_total = Psat(T)` ni se suma una presión parcial de aire sobre un flash de agua pura.
- Potenciales publicados como en la revisión 2 (`PotencialesV2`): μ molar en J/mol, una referencia por
  especie declarada en `referencia`.

### Dominio propuesto (a confirmar con las pruebas)

T de 273.16 a ~450 K; P total ≤ 5 bar (virial truncado: error en Z del vapor por el tercer coeficiente por
debajo de ~0.1 % a esas presiones, a verificar contra IAPWS-95 en el límite de agua pura); sin hielo; sin
región crítica. El límite de resistencia del recipiente es **otra cosa**: un dato del equipo que, si se
declara, produce un evento (`limite_equipo`) sin cambiar el dominio de la EOS.

### Por qué no usar directamente una formulación de aire húmedo

IAPWS/TEOS-10 (aire húmedo: aire seco de Lemmon et al. 2000 + IAPWS-95 + coeficientes cruzados) es la
referencia de calidad y se usará para **contrastar** el paquete. Trata el aire seco como pseudo-componente
de composición fija: no permite seguir N2 y O2 por separado si salen en distinta proporción (aquí no
ocurriría sin disolución, pero el contrato los declara como especies). Instalarla como paquete es posible si
se acepta «aire seco» como un componente con identidad propia; queda como opción B en §6.

## 3. Inicialización desde T0, P0, V, agua total y proporción seca

Datos: T0, P0, V geométrico, n_w (agua total), fracciones secas (N2:O2). Incógnitas de inicialización:
n_aire (total de gas seco), n_w^L, n_w^G. Ecuaciones:

```
n_w^L + n_w^G = n_w                                     (materia del agua)
V = n_w^L v_L(T0, P0) + (n_aire + n_w^G) Z R T0/P0      (volumen, mismo espacio gaseoso para todos los gases)
μ_w^L(T0, P0) = μ_w^G(T0, P0, y_w)                      (equilibrio del agua)
y_w = n_w^G/(n_aire + n_w^G)
```

Tres incógnitas y tres ecuaciones (más la definición de y_w): cuadrado. Las cantidades de N2 y O2 son
**resultado** de la inicialización, no datos; U0 también es resultado (U0 = U(T0, V, n)). Después de t = 0,
P0 no se impone en el hermético: es solo condición inicial. En el contrato esto requiere una forma de
inicial distinta (borrador: `InicialPorPresionV2`) que diga qué cantidades se calculan; la forma actual
(todas las cantidades como datos) sigue válida y no se mezcla con la nueva en el mismo volumen. Si se dan a
la vez las cantidades de aire y P0, hay sobredeterminación: se diagnostica, no se elige una.

Comprobación del estimado del documento de las ollas: con gas ideal y aire insoluble se obtuvo
n_aire = 0.042493 mol; con el virial la diferencia es del orden de B_mez P0/(R T0) ≈ 1e-3 relativo. El paquete
debe recalcularlo con sus propias relaciones; no se reutiliza ese número como dato.

## 4. Cierre hermético

```
dn_i/dt = 0        (i = H2O, N2, O2)
dU/dt = Q_neto
V = 3 L
(T, P, fases) = cierre UV del paquete (n_i, U, V)
```

Verificaciones: U(t) = U0 + Q t exacta; n_i constantes; V fija; segunda ley con T de frontera si se declara.
No hay resultado objetivo: no se fija T, P ni fracción de vapor finales. La trayectoria se detiene con
diagnóstico al salir del dominio del paquete (p. ej. P > 5 bar); un límite de resistencia del equipo,
si se declara, es un evento aparte.

## 5. Frontera abierta: V fija, P ambiente y caudal de salida calculado

### Formulación

Estados: n_i, U. Incógnita algebraica adicional: F (mol/s, salida de la **fase gas** del donante, composición
y_i y entalpía molar h_G del gas). Restricción mecánica ideal: P(U, V, n) = P_amb.

```
dn_i/dt = −F y_i
dU/dt = Q_neto − F h_G
0 = P(U, V, n) − P_amb
```

La energía transportada es la entalpía de la mezcla gaseosa extraída: el calor latente ya está en h_G
(h del vapor de agua frente a h del líquido) y no se añade otra vez.

### Índice y reducción

La restricción no contiene F: el sistema es DAE de **índice 2**. Derivándola una vez:

```
dP/dt = (∂P/∂U)_{V,n} (Q_neto − F h_G) − Σ_i (∂P/∂n_i)_{U,V,n_j} F y_i = 0
F = (∂P/∂U) Q_neto / [ (∂P/∂U) h_G + Σ_i (∂P/∂n_i) y_i ]
```

Las derivadas son **de equilibrio** (a través del reparto de fases, que cambia con U y n), no de una fase
congelada: se obtienen del cierre UV por diferencias o analíticamente. Con F explícita queda una ODE en
(n, U) — reducción a índice 1/ODE — y la restricción se conserva con una proyección por paso (corregir U a
n fijo para que P = P_amb, o equivalentemente re-resolver F) más un residuo publicado
`mecanica.<v>.presion = max |P − P_amb|/P_amb`. Se prefiere esto a un DAE implícito porque el coordinador
actual es explícito (RK45) y ya certifica muestras; un DAE de índice 1 con F como algebraica (BDF/Radau)
es la alternativa si la proyección resultara mal condicionada.

### Signo y régimen

- F ≥ 0: sale gas. Si el denominador o el numerador cambian de signo (p. ej. enfriamiento: la presión
  tiende a bajar de P_amb), una **tapa ideal abierta** admite entrada de aire ambiente: hace falta
  `estadoExterior` (T, P, composición del aire ambiente) y el donante pasa a ser el exterior, con su
  entalpía. Sin estado exterior declarado, la entrada es imposible: se detiene con diagnóstico
  (`entrada_sin_estado_exterior`), no se copian propiedades del interior.
- Válvula antirretorno: régimen distinto (F ≥ 0 y P ≥ P_amb complementarios): se cierra y pasa a hermético
  hasta que P vuelve a alcanzar P_amb. Requiere eventos de cambio de régimen; queda declarado, no diseñado
  en detalle.
- Agotamiento del gas (todo líquido): imposible aquí con V fija mientras haya aire; con aire → 0 y líquido
  que llena V, P deja de estar determinada (líquido incompresible) y se detiene.

### Inicialización consistente

En t = 0 se exige P(U0, V, n0) = P_amb: la misma inicialización de §3 con P0 = P_amb. Si el usuario declara
P0 ≠ P_amb para la frontera abierta, el estado inicial es inconsistente con la restricción: se diagnostica
(no se «salta» el sistema al estado consistente sin decirlo).

### Recuento

Por volumen: estados n_i (3) y U; algebraicas T, P, reparto; una incógnita más (F) y una ecuación más (la
restricción mecánica). GL estructural 0 sin pedir F como dato. Hoy la revisión 2 rechaza «V fija + P
prescrita» porque exige caudales dados; el diseño generaliza esa guarda con el análisis anterior (rango
de la restricción respecto de F: el denominador no debe anularse), no la borra.

### Descarga real futura

Una válvula o una tapa con peso no garantizan P constante: necesitan una ley de transporte
(F = C_v f(P, P_aguas_abajo), masa de la tapa, fugas) con sus parámetros y contrapresión. Es otra
relación constitutiva con datos propios; la frontera ideal no la sustituye.

## 6. Datos necesarios y fuentes

| Dato | Fuente candidata | Estado |
|---|---|---|
| B_ww(T), dB_ww/dT | IAPWS-95 (límite de αʳ) | disponible en el proyecto |
| cp° y referencia de N2, O2 | NASA-7 / Burcat; o parte ideal de Span et al. 2000 (N2) y Schmidt–Wagner 1985 (O2) | por incorporar |
| B_NN, B_OO, B_NO | EOS de referencia de N2, O2 (o aire seco de Lemmon et al. 2000) | por incorporar |
| B_wN, B_wO (cruzados agua–gas) | Harvey y Huang, Int. J. Thermophys. 28 (2007) 556 (cálculo ab initio, usado por IAPWS para aire húmedo) | por incorporar |
| Contraste del paquete | IAPWS/TEOS-10 aire húmedo (Feistel et al. 2010; IAPWS «SeaAir»), CoolProp HumidAir | para pruebas, no para resolver |
| Solubilidad (si se añade) | constantes de Henry (IAPWS G7-04, gases en agua) | ampliación futura |

Opción B: paquete con «aire seco» como pseudo-componente (Lemmon et al. 2000 + IAPWS-95 + cruzados de
IAPWS), cuando sea aceptable seguir el aire sin separar N2 y O2.

## 7. Plan de pruebas (antes de publicar la capacidad)

1. Límite aire → 0: Psat del paquete frente a IAPWS-95 (residuo relativo por debajo de la contribución del
   tercer virial que se omite, cuantificado); entalpía de vaporización.
2. Gas seco: Z, h, s de N2/O2 frente a su EOS de referencia a 1–5 bar.
3. Aire húmedo saturado: y_w frente a IAPWS/TEOS-10 (factor de realce f(T,P)) entre 0 y 100 °C a 1 atm.
4. Identidades: h = u + P v, g = h − T s, Gibbs–Duhem en el gas, derivadas de equilibrio ∂P/∂U, ∂P/∂n por dos
   vías.
5. Inicialización: recuperar T0, P0, V y n_w; cantidades no negativas; sobredeterminación diagnosticada.
6. Hermético: U = U0 + Q t, n_i constantes, segunda ley con T de frontera; convergencia en tolerancia.
7. Abierto: conservación por especie incluyendo lo que sale; energía con h_G; |P − P_amb| publicado;
   F ≥ 0 en calentamiento; inversión con y sin estado exterior; comparación con una reducción independiente
   (integrar con F impuesto igual al calculado y comprobar que P se mantiene).
8. Controles negativos: corromper h_G (latente duplicado) → balance de energía no cumple; quitar el aire →
   inicialización incompatible con P0 = 1 atm (§1).
9. Comparación de los dos cierres con los mismos datos salvo la frontera; sin rama del solver por nombre.

## 8. Qué queda pendiente para implementarlo

Los datos de §6 con procedencia; el paquete con sus pruebas 1–4; la forma de inicial por presión; la
restricción mecánica con caudal incógnita en el ensamblaje (recuento, reducción, proyección, residuo y
eventos de régimen); ejemplos generados por endpoints. Nada de ello se ha añadido al motor en esta entrega.
