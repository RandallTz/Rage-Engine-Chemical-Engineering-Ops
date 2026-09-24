"""
Ecuaciones MESH (Mass, Equilibrium, Summation, Heat).

Placeholder intencional: no se plantea ninguna formulacion aqui todavia.

Lo que SI esta resuelto y era prerrequisito (ver roadmap, Fase 4):

  - La entalpia de corriente tiene UNA sola definicion
    (thermodynamics/entalpia.py), y su forma vectorizada acepta ya un
    perfil completo -- h_liquido(T, x) con T de m elementos y x de forma
    (m, n) -- que es exactamente la firma que necesita un balance por
    etapas.
  - El punto de rocio existe (thermodynamics/elv.py), sin el cual no se
    puede inicializar un perfil ni clasificar una corriente.
  - El sistema M-E-S-H completo esta escrito y verificado para N=1 en
    core/flash.py: representacion de K, forma del residuo, reduccion a
    una incognita escalar (Rachford-Rice) y balance de energia. La
    columna rigurosa es ese mismo sistema repetido y acoplado.

Y lo que da el caso de referencia contra el que comparar cuando esto se
escriba: una columna MESH con muchas etapas y reflujo alto tiene que
converger a lo que ya dan McCabe-Thiele y FUG, que estan validados por
separado. Sin ese punto de comparacion, "no converge" seria
indistinguible de "converge a algo incorrecto".

Zona libre de pint: solo floats/np.ndarray en SI.
"""
