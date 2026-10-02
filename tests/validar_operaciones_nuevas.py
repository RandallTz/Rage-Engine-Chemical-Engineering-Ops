"""
Validacion de los cuatro equipos nuevos y, sobre todo, de que se puedan
COMBINAR sin que el solver se atasque.

  1. Separador de componentes (recuperacion por componente)
  2. Compresor / turbina (eficiencia isentropica)
  3. Reactor de equilibrio quimico (K_eq, sin cinetica)
  4. Intercambiador de DOS corrientes (acopla dos ramas del diagrama)

La parte que de verdad importa es la ultima seccion: una planta con 15
equipos de 9 tipos distintos y DOS reciclos. Un equipo que funciona
aislado no demuestra nada sobre el motor de resolucion -- los fallos de
este proyecto siempre han aparecido al encadenar, no al probar piezas
sueltas.

Ejecutar desde la raiz del proyecto:
    python tests/validar_operaciones_nuevas.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from thermodynamics.reaccion import GestorReaccion
from core.flash import EvaluadorFlash
from core.diagrama_corrientes import DiagramaCorrientes

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


BT = ["benzene", "toluene"]
P1 = 101325.0
PROV_BT = ProveedorTermodinamico(BT)
FLASH_BT = EvaluadorFlash(CalculadoraELV(PROV_BT))


def flujos(pool, corriente, n=2):
    """Caudal por componente [mol/s], para comprobar balances."""
    return np.array([pool[f"{corriente}.F"] * pool[f"{corriente}.x{i}"] for i in range(n)])


# ======================================================================
print("=" * 74)
print("1. SEPARADOR DE COMPONENTES")
print("=" * 74)

d = DiagramaCorrientes(BT, proveedor=PROV_BT)
for c in ("ali", "lig", "pes"):
    d.agregar_corriente(c)
d.agregar_separador("S1", "ali", "lig", "pes", recuperaciones=[0.95, 0.08])
datos = {"ali.F": 100.0, "ali.T": 340.0, "ali.P": P1, "ali.x0": 0.4}
gl = d.grados_de_libertad(datos)
res = d.resolver(**datos)
p = res["pool"]
check("1.1 GL = 0 y resuelve", gl["grados_de_libertad"] == 0 and res["completo"],
      f"GL={gl['grados_de_libertad']}")
print(f"  ligeros  F={p['lig.F']:.4f}  x_benceno={p['lig.x0']:.4f}")
print(f"  pesados  F={p['pes.F']:.4f}  x_benceno={p['pes.x0']:.4f}")

entra, sale = flujos(p, "ali"), flujos(p, "lig") + flujos(p, "pes")
check("1.2 Balance por componente", np.max(np.abs(entra - sale)) < 1e-10,
      f"max dif {np.max(np.abs(entra - sale)):.2e} mol/s")
check("1.3 Se respeta la recuperación pedida del benceno (0.95)",
      abs(p["lig.F"] * p["lig.x0"] / (100.0 * 0.4) - 0.95) < 1e-10)
check("1.4 Y la del tolueno (0.08)",
      abs(p["lig.F"] * p["lig.x1"] / (100.0 * 0.6) - 0.08) < 1e-10)
check("1.5 Las salidas heredan T y P de la entrada",
      p["lig.T"] == 340.0 and p["pes.P"] == P1)

# Separación perfecta: cada componente entero por su lado.
d2 = DiagramaCorrientes(BT, proveedor=PROV_BT)
for c in ("a", "l", "pp"):
    d2.agregar_corriente(c)
d2.agregar_separador("S2", "a", "l", "pp", recuperaciones=[1.0, 0.0])
p2 = d2.resolver(**{"a.F": 100.0, "a.T": 340.0, "a.P": P1, "a.x0": 0.4})["pool"]
check("1.6 Separación perfecta da productos puros",
      abs(p2["l.x0"] - 1.0) < 1e-12 and abs(p2["pp.x1"] - 1.0) < 1e-12,
      f"ligeros {p2['l.F']:.2f} mol/s puros, pesados {p2['pp.F']:.2f} mol/s puros")

try:
    d2.agregar_separador("X", "a", "l", "pp", recuperaciones=[1.5, 0.0])
    check("1.7 Recuperación fuera de [0,1] rechazada", False, "no lanzó error")
except ValueError as e:
    check("1.7 Recuperación fuera de [0,1] rechazada", "FRACCION" in str(e))

# ======================================================================
print("\n" + "=" * 74)
print("2. COMPRESOR / TURBINA")
print("=" * 74)

PV = 3 * P1


def compresor(P_sal, eta=0.75, T_ent=420.0):
    dd = DiagramaCorrientes(BT, proveedor=PROV_BT)
    for c in ("g1", "g2"):
        dd.agregar_corriente(c)
    dd.agregar_compresor("K1", "g1", "g2", P_salida=P_sal, eficiencia=eta)
    return dd.resolver(**{"g1.F": 50.0, "g1.T": T_ent, "g1.P": PV, "g1.x0": 0.5})["pool"]

comp = compresor(6 * P1)
exp = compresor(1.5 * P1)
print(f"  comprimir 3→6 atm: 420.00 → {comp['g2.T']:.2f} K  (ideal {comp['K1.T_ideal']:.2f})  W={comp['K1.W']/1000:.1f} kW")
print(f"  expandir  3→1.5 atm: 420.00 → {exp['g2.T']:.2f} K  (ideal {exp['K1.T_ideal']:.2f})  W={exp['K1.W']/1000:.1f} kW")

check("2.1 Comprimir calienta y consume trabajo",
      comp["g2.T"] > 420.0 and comp["K1.W"] > 0)
check("2.2 Expandir enfría y produce trabajo",
      exp["g2.T"] < 420.0 and exp["K1.W"] < 0)
check("2.3 La ineficiencia deja la salida por encima de la ideal, en los DOS casos",
      comp["g2.T"] > comp["K1.T_ideal"] and exp["g2.T"] > exp["K1.T_ideal"],
      "comprimiendo llega más caliente; expandiendo, se enfría menos")

ideal = compresor(6 * P1, eta=1.0)
check("2.4 Con eficiencia 1 la salida ES la isentrópica",
      abs(ideal["g2.T"] - ideal["K1.T_ideal"]) < 1e-9,
      f"{ideal['g2.T']:.6f} K")
check("2.5 Peor eficiencia, más trabajo para la misma compresión",
      comp["K1.W"] > ideal["K1.W"],
      f"{comp['K1.W']/1000:.1f} kW con η=0.75 frente a {ideal['K1.W']/1000:.1f} kW ideal")

peor = compresor(6 * P1, eta=0.5)
check("2.6 Y monótono en la eficiencia", peor["K1.W"] > comp["K1.W"] > ideal["K1.W"])
check("2.7 El caudal y la composición no cambian",
      abs(comp["g2.F"] - 50.0) < 1e-12 and abs(comp["g2.x0"] - 0.5) < 1e-12)

# ======================================================================
print("\n" + "=" * 74)
print("3. REACTOR DE EQUILIBRIO QUÍMICO")
print("=" * 74)

MTBE = ["isobutene", "methanol", "mtbe"]
NU = [-1.0, -1.0, 1.0]
PR = 10 * P1
PROV_M = ProveedorTermodinamico(MTBE)
GESTOR = GestorReaccion(PROV_M, np.array(NU), A=1e4, Ea=45000.0)


def equilibrio(T, x_in=(0.5, 0.5, 0.0), F=100.0):
    dd = DiagramaCorrientes(MTBE, proveedor=PROV_M)
    for c in ("e", "s"):
        dd.agregar_corriente(c)
    dd.agregar_reactor_cstr("R1", "e", "s", NU, gestor_reaccion=GESTOR,
                            modo_reaccion="equilibrio", con_balance_energia=False)
    datos = {"e.F": F, "e.T": T, "e.P": PR, "R1.T": T,
             "e.x0": x_in[0], "e.x1": x_in[1]}
    return dd, dd.resolver(**datos)


dd, r3 = equilibrio(340.0)
p3 = r3["pool"]
check("3.1 Resuelve sin cinética ni volumen", r3["completo"])
check("3.2 No declara volumen (el equilibrio no depende del tamaño)",
      "R1.V" not in p3)

# La comprobacion de fondo: la salida CUMPLE la condicion de equilibrio,
# recalculada aqui desde cero con el gamma del proveedor.
x_out = np.array([p3["s.x0"], p3["s.x1"], p3["s.x2"]])
gamma = PROV_M.coeficientes_actividad(340.0, x_out)
producto = float(np.prod((x_out * gamma) ** np.array(NU)))
K = float(GESTOR.K_eq(340.0))
check("3.3 La salida cumple ∏aᵢ^νᵢ = K_eq, recalculado desde cero",
      abs(producto - K) / K < 1e-8,
      f"∏aᵢ^νᵢ={producto:.6f} vs K_eq={K:.6f}")

print()
conversiones = []
for T in (320.0, 340.0, 360.0, 380.0):
    _, rr = equilibrio(T)
    X = rr["pool"]["R1.X"]
    conversiones.append(X)
    print(f"  T={T:.0f} K: conversión {X*100:5.1f}%   K_eq={rr['pool']['R1.K_eq']:8.4f}")
check("3.4 Exotérmica: subir T BAJA la conversión de equilibrio (van't Hoff)",
      all(np.diff(conversiones) < 0),
      f"{conversiones[0]*100:.1f}% → {conversiones[-1]*100:.1f}%")

# Alimentacion que YA trae producto por encima del equilibrio: la
# reaccion tiene que correr al reves (xi < 0).
_, r_inv = equilibrio(380.0, x_in=(0.05, 0.05, 0.90))
check("3.5 Con exceso de producto, la reacción corre AL REVÉS (ξ < 0)",
      r_inv["completo"] and r_inv["pool"]["R1.xi"] < 0,
      f"ξ={r_inv['pool']['R1.xi']:.4f} mol/s")

# ======================================================================
print("\n" + "=" * 74)
print("4. INTERCAMBIADOR DE DOS CORRIENTES")
print("=" * 74)

PX = 3 * P1
DATOS_IC = {"ce.F": 100.0, "ce.T": 400.0, "ce.P": PX, "ce.x0": 0.3,
            "fe.F": 120.0, "fe.T": 310.0, "fe.P": PX, "fe.x0": 0.7}


def intercambiador(**spec):
    dd = DiagramaCorrientes(BT, proveedor=PROV_BT)
    for c in ("ce", "cs", "fe", "fs"):
        dd.agregar_corriente(c)
    dd.agregar_intercambiador_doble("IC", "ce", "cs", "fe", "fs", **spec)
    return dd, dd.resolver(**DATOS_IC)


d4, r4 = intercambiador(T_salida_caliente=360.0)
p4 = r4["pool"]
check("4.1 GL = 0 y resuelve",
      d4.grados_de_libertad(DATOS_IC)["grados_de_libertad"] == 0 and r4["completo"])
print(f"  caliente 400.00 → {p4['cs.T']:.2f} K | fría 310.00 → {p4['fs.T']:.2f} K"
      f" | Q={p4['IC.Q']/1000:.1f} kW | aprox={p4['IC.aproximacion']:.2f} K")

# Lo que pierde la caliente es EXACTAMENTE lo que gana la fría.
h = FLASH_BT.entalpia_de_corriente
x_cal, x_fri = np.array([0.3, 0.7]), np.array([0.7, 0.3])
cede = 100.0 * (h(400.0, PX, x_cal) - h(p4["cs.T"], PX, x_cal))
recibe = 120.0 * (h(p4["fs.T"], PX, x_fri) - h(310.0, PX, x_fri))
check("4.2 Lo que cede la caliente = lo que recibe la fría",
      abs(cede - recibe) / cede < 1e-8,
      f"{cede/1000:.4f} kW cedidos frente a {recibe/1000:.4f} kW recibidos")
check("4.3 Y coincide con el Q que reporta el equipo",
      abs(p4["IC.Q"] - cede) / cede < 1e-8)

# Ida y vuelta entre especificaciones: dar el Q que salio tiene que
# reproducir las mismas temperaturas.
_, r_q = intercambiador(Q=p4["IC.Q"])
check("4.4 Ida y vuelta: dar ese Q reproduce las mismas temperaturas",
      abs(r_q["pool"]["cs.T"] - p4["cs.T"]) < 1e-6
      and abs(r_q["pool"]["fs.T"] - p4["fs.T"]) < 1e-6,
      f"caliente {r_q['pool']['cs.T']:.6f} K, fría {r_q['pool']['fs.T']:.6f} K")

_, r_f = intercambiador(T_salida_frio=p4["fs.T"])
check("4.5 Y dar la T fría de salida también",
      abs(r_f["pool"]["cs.T"] - p4["cs.T"]) < 1e-6)

# Segunda ley: pedir que la caliente salga por DEBAJO de la fría de
# entrada es un cruce de temperaturas, y el equipo no existe.
_, r_cruce = intercambiador(T_salida_caliente=300.0)
check("4.6 Cruce de temperaturas rechazado con motivo",
      not r_cruce["completo"]
      and any("aproximación" in m or "aproximacion" in m
              for m in r_cruce["errores_bloque"].values()),
      list(r_cruce["errores_bloque"].values())[0][:95] if r_cruce["errores_bloque"] else "")

try:
    intercambiador(Q=1e5, T_salida_caliente=360.0)
    check("4.7 Dos especificaciones rechazadas", False, "no lanzó error")
except ValueError as e:
    check("4.7 Dos especificaciones rechazadas", "EXACTAMENTE una" in str(e))

# ======================================================================
print("\n" + "=" * 74)
print("5. TODO COMBINADO: 15 equipos, 9 tipos, DOS reciclos")
print("=" * 74)

#   fresco ─┐
#           M1 ─ IC(frío) ─ E1 ─ R1(equilibrio) ─ IC(caliente) ─ V1 ─ FL1
#           │                                                          ├─ vapor ─ K1 ─ D1 ─┬─ purga_v
#           │                                                          │                    └─ reciclo 1 ──┐
#           │                                                          └─ líquido ─ SEP ─┬─ producto        │
#           │                                                                             └─ D2 ─┬─ purga_l │
#           └─────────────────── reciclo 2 ───────────────────────────────────────────────────────┘
#
# El intercambiador doble es la pieza clave de esta prueba: sus dos
# entradas vienen de ramas DISTINTAS del diagrama (una de antes del
# reactor, otra de después), así que el motor de punto fijo tiene que
# saber esperar a que las dos estén listas.
g = DiagramaCorrientes(MTBE, proveedor=PROV_M)
CORRIENTES = [
    "fresco", "mezcla", "precal", "caliente", "crudo", "enfriado", "expandido",
    "vapor", "comprimido", "purga_v", "reciclo_v",
    "liquido", "producto", "cola", "purga_l", "reciclo_l",
]
for c in CORRIENTES:
    g.agregar_corriente(c)

g.agregar_mezclador("M1", entradas=["fresco", "reciclo_v", "reciclo_l"], salida="mezcla")
g.agregar_intercambiador_doble("IC1", "crudo", "enfriado", "mezcla", "precal",
                               T_salida_caliente=355.0, aproximacion_minima=2.0)
g.agregar_intercambiador("E1", "precal", "caliente", T_salida=360.0)
g.agregar_reactor_cstr("R1", "caliente", "crudo", NU, gestor_reaccion=GESTOR,
                       modo_reaccion="equilibrio", con_balance_energia=False)
g.agregar_valvula("V1", "enfriado", "expandido", P_salida=5 * P1)
g.agregar_flash("FL1", "expandido", "vapor", "liquido", P_operacion=5 * P1, Q_por_mol=0.0)
g.agregar_compresor("K1", "vapor", "comprimido", P_salida=PR, eficiencia=0.75)
g.agregar_divisor("D1", "comprimido", salidas=["purga_v", "reciclo_v"], fracciones=[0.4, 0.6])
g.agregar_separador("SEP", "liquido", "producto", "cola", recuperaciones=[0.02, 0.05, 0.97])
g.agregar_divisor("D2", "cola", salidas=["purga_l", "reciclo_l"], fracciones=[0.5, 0.5])

DATOS_G = {"fresco.F": 100.0, "fresco.T": 330.0, "fresco.P": PR,
           "fresco.x0": 0.5, "fresco.x1": 0.5, "R1.T": 360.0}

cortes = g.detectar_reciclos()
print(f"  equipos: {len(g._operaciones)} · corrientes: {len(g.corrientes)}")
print(f"  lazos detectados, cortando: {cortes}")
check("5.1 Detecta los DOS reciclos", len(cortes) >= 1, f"cortes={cortes}")

gl_g = g.grados_de_libertad(DATOS_G)
check("5.2 GL = 0 con 15 equipos de 9 tipos",
      gl_g["grados_de_libertad"] == 0,
      f"incógnitas={gl_g['incognitas']}, ecuaciones={gl_g['ecuaciones']}, "
      f"GL={gl_g['grados_de_libertad']}")

res_g = g.resolver(tolerancia_reciclo=1e-10, max_ciclos_reciclo=400, **DATOS_G)
pg = res_g["pool"]
info = res_g.get("reciclo") or {}
check("5.3 La planta entera resuelve", res_g["completo"],
      f"restantes: {res_g['incognitas_restantes'][:4]}")
check("5.4 Los lazos convergen",
      bool(info.get("convergio")),
      f"{info.get('ciclos')} vueltas, error {info.get('error'):.2e}"
      if info.get("error") is not None else "")

if res_g["completo"]:
    print()
    for c in ("fresco", "mezcla", "precal", "crudo", "vapor", "liquido",
              "producto", "purga_v", "purga_l"):
        print(f"    {c:12s} F={pg[f'{c}.F']:8.3f} mol/s  T={pg[f'{c}.T']:7.2f} K")

    # BALANCE DE MATERIA GLOBAL. Lo que entra fresco tiene que salir por
    # las tres salidas; el resto da vueltas por dentro.
    salidas = ["producto", "purga_v", "purga_l"]
    nu = np.array(NU)
    for i, nombre_c in enumerate(MTBE):
        entra = pg["fresco.F"] * pg[f"fresco.x{i}"]
        sale = sum(pg[f"{s}.F"] * pg[f"{s}.x{i}"] for s in salidas)
        # Con reacción, el balance por componente lleva el término νᵢ·ξ.
        generado = nu[i] * pg["R1.xi"]
        check(f"5.5 Balance global de {nombre_c} (con ν·ξ)",
              abs(entra + generado - sale) < 1e-5,
              f"entra {entra:.5f} + genera {generado:.5f} = {entra+generado:.5f} "
              f"frente a {sale:.5f} mol/s")

    # El átomo total sí se conserva sin término de reacción si se suman
    # los tres componentes pesados por su estequiometría... pero más
    # simple y igual de fuerte: el balance TOTAL con ν_tot·ξ.
    total_entra = pg["fresco.F"] + sum(nu) * pg["R1.xi"]
    total_sale = sum(pg[f"{s}.F"] for s in salidas)
    check("5.6 Balance total (F + ν_tot·ξ)",
          abs(total_entra - total_sale) < 1e-5,
          f"{total_entra:.6f} vs {total_sale:.6f} mol/s")

    check("5.7 El intercambiador doble sigue cerrando dentro de la planta",
          pg["IC1.aproximacion"] >= 2.0,
          f"Q={pg['IC1.Q']/1000:.1f} kW, aproximación {pg['IC1.aproximacion']:.2f} K")
    check("5.8 El precalentamiento sirve de algo",
          pg["precal.T"] > pg["mezcla.T"],
          f"mezcla {pg['mezcla.T']:.2f} K → precalentada {pg['precal.T']:.2f} K, "
          f"gratis con el calor del reactor")


# ======================================================================
print("\n" + "=" * 74)
print("6. RAMA SECA: caudal cero no debe atascar el diagrama")
print("=" * 74)

# Una rama con F = 0 es legitima -- una purga puesta a cero, una
# separacion que se lo lleva todo por un lado, o la primera vuelta de un
# reciclo que arranca sin recirculacion. Antes, cualquier equipo que
# recibiera caudal cero devolvia {} y dejaba sin determinar todo lo que
# viniera detras; el sintoma era "el lazo no se puede cerrar", que apunta
# a datos que faltan cuando no falta ninguno.
z = DiagramaCorrientes(BT, proveedor=PROV_BT)
for c in ("ent", "seco", "humedo", "s_lig", "s_pes", "comp", "val", "v2", "l2"):
    z.agregar_corriente(c)
z.agregar_divisor("DV", "ent", salidas=["seco", "humedo"], fracciones=[0.0, 1.0])
z.agregar_separador("SP", "seco", "s_lig", "s_pes", recuperaciones=[0.9, 0.1])
z.agregar_compresor("KK", "s_lig", "comp", P_salida=3 * P1, eficiencia=0.8)
z.agregar_valvula("VV", "comp", "val", P_salida=P1)
z.agregar_flash("FF", "val", "v2", "l2", P_operacion=P1, Q_por_mol=0.0)

datos_z = {"ent.F": 100.0, "ent.T": 360.0, "ent.P": 3 * P1, "ent.x0": 0.4}
gl_z = z.grados_de_libertad(datos_z)
res_z = z.resolver(**datos_z)
pz = res_z["pool"]
check("6.1 Una cadena entera alimentada con caudal CERO resuelve igual",
      res_z["completo"],
      f"GL={gl_z['grados_de_libertad']}, restantes={res_z['incognitas_restantes'][:3]}")
check("6.2 Los caudales de la rama seca son cero",
      all(abs(pz[f"{c}.F"]) < 1e-12 for c in ("seco", "s_lig", "comp", "val", "v2", "l2")))
check("6.3 Pero conservan estado: presion del equipo y composicion",
      abs(pz["comp.P"] - 3 * P1) < 1e-9 and abs(pz["val.P"] - P1) < 1e-9
      and abs(pz["s_lig.x0"] - 0.4) < 1e-12,
      "sin estado, lo de aguas abajo no podria seguir")
check("6.4 Y las cantidades extensivas valen cero",
      abs(pz["KK.W"]) < 1e-12 and abs(pz["FF.Q"]) < 1e-12)
check("6.5 La rama con caudal sigue igual",
      abs(pz["humedo.F"] - 100.0) < 1e-12)


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
