"""Repository inventory for the cleanup (phase 1).

Lists every file that git tracks or would track (plus the ignored files that
sit in working folders), classifies it, counts how many other files mention
it, and proposes an English destination path. It moves nothing.

Usage:
    python tools/repo_cleanup/inventory.py            writes docs/repository-cleanup/inventory.csv
    python tools/repo_cleanup/inventory.py --summary  also prints the summary tables

The proposal is a first draft for review: names come from GLOSSARY word by
word, so word order sometimes needs a manual fix (see OVERRIDES). Every token
that the glossary does not know is reported, so nothing is translated by guess.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "repository-cleanup" / "inventory.csv"

# Spanish word -> English word. Lowercase; applied token by token.
GLOSSARY = {
    "abierta": "open", "abierto": "open", "absorbedor": "absorber", "acciones": "actions", "accion": "action",
    "acetona": "acetone", "acopladas": "coupled", "acoplado": "coupled", "acoplada": "coupled", "acoplados": "coupled",
    "acoplamiento": "coupling", "actual": "current", "actualizar": "update", "adaptadores": "adapters",
    "adiabatica": "adiabatic", "adim": "nondim", "adimensional": "dimensionless",
    "adimensionalizacion": "nondimensionalization", "afin": "affine", "agotado": "depleted", "agotamiento": "depletion",
    "agua": "water", "aguas": "waters", "aire": "air", "ajuste": "fit", "ajustes": "settings", "alcance": "scope",
    "algebra": "algebra", "almacen": "store", "almacenamiento": "storage", "ambigua": "ambiguous", "ampliados": "extended",
    "analisis": "analysis", "analizar": "analyze", "antes": "before", "antiguo": "legacy", "aportaciones": "contributions",
    "archivo": "archive", "arquitectura": "architecture", "articulo": "paper", "asignacion": "assignment",
    "asintotica": "asymptotic", "auditar": "audit", "auditoria": "audit", "ausente": "absent", "automatica": "automatic",
    "automatico": "automatic", "avance": "progress", "aviso": "notice", "avisos": "notices", "ayudas": "hints",
    "bajo": "low", "balance": "balance", "balancear": "balance", "balanceo": "balancing", "balances": "balances",
    "barra": "bar", "base": "base", "bases": "bases", "bateria": "battery", "benceno": "benzene", "bifasico": "two_phase",
    "bifurcaciones": "bifurcations", "binaria": "binary", "binario": "binary", "biblioteca": "library", "bloque": "block",
    "borrador": "draft", "buscador": "search", "cabe": "cabe", "caida": "drop", "calculadora": "calculator",
    "calculo": "calculation", "calentado": "heated", "calentamiento": "heating", "caliente": "hot", "calidad": "quality",
    "calor": "heat", "cambio": "change", "cambios": "changes", "campo": "field", "campos": "fields", "capa": "layer",
    "capacidad": "capacity", "capacidades": "capabilities", "casos": "cases", "caso": "case", "catalogo": "catalog",
    "caudal": "flow", "cadena": "chain", "cerrada": "closed", "cerrado": "closed", "cerrados": "closed",
    "certificacion": "certification", "cientifico": "scientific", "cierre": "closure", "cierres": "closures",
    "cinetica": "kinetics", "cineticas": "kinetics", "cinetico": "kinetic", "circuitos": "circuits",
    "clasificador": "classifier", "coherencia": "consistency", "coexistencia": "coexistence", "columna": "column",
    "combustion": "combustion", "comparacion": "comparison", "comparador": "comparator", "comparar": "compare",
    "compartible": "shareable", "compacto": "compact", "competencia": "competition", "compilador": "compiler",
    "compilar": "compile", "completa": "complete", "componentes": "components", "composicion": "composition",
    "comprimido": "compressed", "comprobacion": "check", "comprobar": "check", "comun": "common", "con": "with",
    "condensacion": "condensation", "condensar": "condense", "condiciones": "conditions", "conductancia": "conductance",
    "conexion": "connection", "conexiones": "connections", "configuracion": "settings", "conflicto": "conflict",
    "consecutiva": "consecutive", "consolidacion": "consolidation", "constante": "constant", "construir": "build",
    "constructor": "builder", "consulta": "query", "consultas": "queries", "contacto": "contact",
    "contenedor": "container", "contenedores": "containers", "contexto": "context", "continuidad": "continuity",
    "continuo": "continuous", "contradictoria": "contradictory", "contradictorio": "contradictory",
    "contraste": "contrast", "contrastes": "contrasts", "contrato": "contract", "contratos": "contracts",
    "contribucion": "contribution", "control": "control", "coordenadas": "coordinates", "coordinacion": "coordination",
    "correccion": "correction", "correcciones": "corrections", "corriente": "stream", "corrientes": "streams",
    "corte": "slice", "craqueo": "cracking", "crear": "create", "critica": "critical", "cuaderno": "notebook",
    "cuaternario": "quaternary", "cumple": "complies", "curvas": "curves", "datos": "data", "dato": "datum",
    "de": "", "decantador": "decanter", "decision": "decision", "declarados": "declared", "definicion": "definition",
    "definir": "define", "deja": "stops", "del": "", "densidad": "density", "dependencias": "dependencies",
    "derivacion": "derivation", "desactualizada": "outdated", "desarrollo": "development", "descargar": "download",
    "descripcion": "description", "desde": "from", "desglose": "breakdown", "destilacion": "distillation",
    "destino": "target", "destinos": "targets", "detalles": "details", "detenido": "stopped", "diagnostico": "diagnostics",
    "diagnosticos": "diagnostics", "diagrama": "diagram", "diagramas": "diagrams", "diferencia": "difference",
    "diferencias": "differences", "difusivo": "diffusive", "dimensionado": "sizing", "dimensional": "dimensional",
    "dimensiones": "dimensions", "dinamica": "dynamics", "dinamico": "dynamic", "dinamicos": "dynamic",
    "directo": "direct", "diseno": "design", "distinta": "different", "distintas": "different", "doble": "double",
    "documento": "document", "documentos": "documents", "dominio": "domain", "dominios": "domains", "dos": "two",
    "dual": "dual", "e": "and", "ebullicion": "boiling", "ecuacion": "equation", "ecuaciones": "equations",
    "edicion": "editing", "editado": "edited", "editar": "edit", "editor": "editor", "ejecucion": "run",
    "ejecuciones": "runs", "ejecutable": "executable", "ejecutado": "executed", "ejecutados": "executed",
    "ejemplo": "example", "ejemplos": "examples", "el": "", "elegir": "choose", "elemento": "element", "empaquetado": "packaging",
    "en": "in", "encadenada": "chained", "encargo": "assignment", "encendida": "on", "energia": "energy",
    "enlace": "link", "ensamblado": "assembled", "ensamblaje": "assembly", "ensambladas": "assembled", "ensayo": "trial",
    "entalpia": "enthalpy", "entrada": "inlet", "entrante": "incoming", "entrega": "delivery", "entregados": "delivered",
    "entregas": "deliveries", "equilibrio": "equilibrium", "equipo": "equipment", "error": "error", "errores": "errors",
    "escalada": "scaled", "escalon": "step", "escenario": "scenario", "escenarios": "scenarios", "escrito": "written",
    "espacio": "space", "espera": "wait", "especie": "species", "especies": "species", "especificacion": "specification",
    "especificaciones": "specifications", "especifico": "specific", "estabilidad": "stability", "estacionario": "steady",
    "estacionarios": "steady", "estado": "state", "estequiometria": "stoichiometry", "estilos": "styles",
    "estructura": "structure", "estudio": "study", "estudios": "studies", "etanol": "ethanol", "evaluable": "evaluable",
    "evento": "event", "eventos": "events", "evidencias": "evidence", "experimentar": "experiment",
    "experimento": "experiment", "experimentos": "experiments", "expansion": "expansion", "exploracion": "exploration",
    "explorar": "explore", "explicito": "explicit", "exportar": "export", "expresiones": "expressions",
    "extraccion": "extraction", "familias": "families", "fase": "phase", "faltante": "missing", "ficha": "card",
    "fija": "fixed", "finales": "final", "final": "final", "fiabilidad": "reliability", "fisica": "physics",
    "flujo": "flow", "fluida": "fluid", "fluido": "fluid", "fluidos": "fluids", "fondo": "background", "forma": "shape",
    "formacion": "formation", "formatear": "format", "formato": "format", "formula": "formula",
    "formulacion": "formulation", "formulaciones": "formulations", "fracciones": "fractions", "fraccion": "fraction",
    "frontera": "boundary", "fronteras": "boundaries", "fuente": "source", "fuentes": "sources", "fuera": "outside",
    "funcion": "function", "fundamental": "fundamental", "fundamentales": "fundamental", "fundamento": "foundation",
    "fundamentos": "foundations", "fusion": "melting", "generador": "generator", "generar": "generate",
    "geometria": "geometry", "gestor": "manager", "glosario": "glossary", "grafica": "chart", "graficas": "charts",
    "grafico": "chart", "graficos": "charts", "grupo": "group", "grupos": "groups", "guarda": "guard", "guardada": "saved",
    "guia": "guide", "hacia": "towards", "hexano": "hexane", "hielo": "ice", "historial": "history", "hoja": "sheet",
    "hojas": "sheets", "huella": "fingerprint", "ideal": "ideal", "ideales": "ideal", "iguales": "equal",
    "impuesta": "imposed", "impuesto": "imposed", "importacion": "import", "incidencia": "incident",
    "incoherencias": "inconsistencies", "incompatible": "incompatible", "incompleta": "incomplete",
    "incompleto": "incomplete", "inconsistente": "inconsistent", "incorrecta": "incorrect", "indeterminada": "underdetermined",
    "indeterminado": "underdetermined", "indicador": "indicator", "informe": "report", "ingenieria": "engineering",
    "inicial": "initial", "iniciales": "initial", "inicio": "start", "insercion": "insertion", "inspector": "inspector",
    "integracion": "integration", "integrado": "integrated", "integrador": "integrator", "integridad": "integrity",
    "interaccion": "interaction", "interactivo": "interactive", "intercambios": "exchanges", "interfaces": "interfaces",
    "interfaz": "interface", "intervalo": "interval", "invalida": "invalid", "inventario": "inventory", "inverso": "inverse",
    "investigacion": "research", "isomerizacion": "isomerization", "isoterma": "isothermal", "laboratorio": "lab",
    "lanzador": "launcher", "lateral": "side", "lectura": "reading", "lector": "reader", "leeme": "readme",
    "limite": "limit", "lineal": "linear", "liquido": "liquid", "listo": "ready", "llenado": "filling",
    "locales": "local", "logaritmico": "logarithmic", "longitud": "length", "lote": "batch", "mantenimiento": "maintenance",
    "mapa": "map", "masa": "mass", "masica": "mass", "matematico": "mathematical", "materia": "matter",
    "material": "material", "materiales": "material", "medio": "medium", "menu": "menu", "mesa": "bench", "mesas": "benches",
    "metadatos": "metadata", "metanol": "methanol", "metodo": "method", "metodos": "methods", "mezcla": "mixture",
    "mezclas": "mixtures", "migracion": "migration", "migrar": "migrate", "minutos": "minutes", "modal": "modal",
    "modelo": "model", "modelos": "models", "modo": "mode", "modular": "modular", "molar": "molar", "momento": "momentum",
    "monofasico": "single_phase", "montaje": "setup", "motor": "engine", "motores": "engines", "muestra": "sample",
    "muestras": "samples", "multicomponente": "multicomponent", "multifasica": "multiphase", "multifasico": "multiphase",
    "multifasicos": "multiphase", "multifisica": "multiphysics", "multifisico": "multiphysics", "navegacion": "navigation",
    "navegador": "browser", "negativo": "negative", "neta": "net", "no": "no", "nodos": "nodes", "nombre": "name",
    "nombres": "names", "nucleo": "core", "nuevas": "new", "nuevo": "new", "numerica": "numerical", "numerico": "numerical",
    "numero": "number", "olla": "pot", "ollas": "pots", "operacion": "operation", "operaciones": "operations",
    "operadores": "operators", "orden": "order", "organizar": "arrange", "orientacion": "guidance", "origen": "origin",
    "orquestador": "orchestrator", "panel": "panel", "paneles": "panels", "papeles": "roles", "par": "pair",
    "paralela": "parallel", "parametrica": "parametric", "parametros": "parameters", "parcial": "partial",
    "pared": "wall", "pasar": "handoff", "paquete": "package", "paquetes": "packages", "pendiente": "pending",
    "pendientes": "pending", "periodica": "periodic", "persistencia": "persistence", "persistente": "persistent",
    "perturbaciones": "disturbances", "peticion": "request", "planta": "plant", "plantillas": "templates",
    "pliegues": "folds", "por": "by", "portada": "home", "potencia": "power", "preacondicionamiento": "preconditioning",
    "preparacion": "preparation", "preparado": "prepared", "preparar": "prepare", "presentacion": "presentation",
    "presion": "pressure", "primer": "first", "primero": "first", "proceso": "process", "procedencia": "provenance",
    "profundizacion": "deep_dive", "progreso": "progress", "prohibido": "forbidden", "propiedad": "property",
    "propiedades": "properties", "proveedor": "provider", "proximo": "next", "prueba": "test", "pruebas": "tests",
    "publicacion": "publication", "publicado": "published", "puente": "bridge", "puertos": "ports", "punto": "point",
    "puntuales": "pointwise", "pura": "pure", "puro": "pure", "puros": "pure", "racional": "rational", "rama": "branch",
    "rango": "range", "reaccion": "reaction", "reacciones": "reactions", "reactiva": "reactive", "reactivo": "reactive",
    "reactivos": "reactive", "reactor": "reactor", "reactores": "reactors", "real": "real", "recarga": "reload",
    "recipiente": "vessel", "reciclo": "recycle", "reconstruccion": "rebuild", "recorrido": "walkthrough",
    "recuento": "count", "red": "network", "redundante": "redundant", "referencia": "reference",
    "referencias": "references", "refinamiento": "refinement", "region": "region", "registrado": "registered",
    "reglas": "rules", "regimenes": "regimes", "regresion": "regression", "relacion": "relation",
    "relaciones": "relations", "reparto": "split", "reporte": "report", "repositorio": "repository",
    "requiere": "requires", "residuales": "residue", "resolucion": "solution", "resolver": "solve",
    "respuesta": "response", "restaurado": "restored", "resultado": "result", "resultados": "results",
    "resumen": "summary", "reutilizacion": "reuse", "reutilizar": "reuse", "revision": "review", "rigida": "rigid",
    "rigido": "rigid", "ruta": "route", "salida": "outlet", "saturacion": "saturation", "seguro": "safe",
    "segundo": "second", "seleccion": "selection", "selector": "selector", "sensibilidad": "sensitivity",
    "serie": "series", "serpentin": "coil", "servicio": "service", "servicios": "services", "servidores": "servers",
    "siguiente": "next", "simbolo": "symbol", "simetrias": "symmetries", "simple": "simple", "simulacion": "simulation",
    "simulaciones": "simulations", "simulado": "simulated", "simulador": "simulator", "sin": "without",
    "sincronizar": "sync", "sistema": "system", "sobrecalentado": "superheated", "sobreespecificada": "overspecified",
    "solicitud": "request", "solicitudes": "requests", "solo": "only", "sonda": "probe", "sondas": "probes",
    "subespacio": "subspace", "suites": "suites", "suma": "sum", "suministro": "supply", "supercritico": "supercritical",
    "superviviente": "surviving", "supuestos": "assumptions", "suave": "smooth", "sustancia": "substance",
    "sustancias": "substances", "sustitucion": "substitution", "sustituciones": "substitutions", "tabla": "table",
    "tablero": "dashboard", "tanque": "tank", "tanques": "tanks", "tasa": "rate", "tema": "theme", "temas": "themes",
    "temperatura": "temperature", "temporal": "transient", "termica": "thermal", "termicas": "thermal",
    "termico": "thermal", "termicos": "thermal", "termo": "thermo", "termodinamica": "thermodynamics",
    "termodinamicas": "thermodynamic", "termodinamico": "thermodynamic", "termodinamicos": "thermodynamic",
    "terminos": "terms", "ternario": "ternary", "texto": "text", "tiempo": "time", "tipo": "type", "todo": "all",
    "tolueno": "toluene", "topologia": "topology", "trabajo": "work", "transferencia": "transfer",
    "transferir": "transfer", "transformacion": "transformation", "transformaciones": "transformations",
    "traza": "trace", "trazabilidad": "traceability", "trayectoria": "trajectory", "tres": "three", "triple": "triple",
    "ubicacion": "placement", "ubic": "placement", "un": "one", "una": "one", "unidad": "unit", "unidades": "units",
    "uno": "one", "uso": "usage", "vaciado": "draining", "validacion": "validation", "validar": "validate",
    "valor": "value", "valores": "values", "vapor": "vapor", "variable": "variable", "variables": "variables",
    "varias": "multiple", "verificar": "verify", "versiones": "versions", "vertical": "vertical", "vinculada": "linked",
    "visual": "visual", "vista": "view", "vistas": "views", "vivo": "live", "volcar": "dump", "volumen": "volume",
    "volumenes": "volumes", "volumetrica": "volumetric", "volumetrico": "volumetric", "y": "and",
    "rechazo": "rejection", "demostracion": "demo", "cobertura": "coverage", "signo": "sign", "criterio": "criterion",
    "cliente": "client", "elv": "vle", "ell": "lle", "mc": "mc", "ids": "ids", "global": "global", "nav": "nav", "scene": "scene",
    "candidata": "candidate", "cambio_fase": "phase_change", "matematicas": "math", "codigo": "code",
}
# Tokens that are already English, proper names, acronyms or symbols.
KEEP = set("""
a b c e f h k m n p q t u v x z id ui api app core docs tests backend frontend thermodynamics config readme agents claude
gemini codex unifac nrtl iapws lle ell vl lv ll llv slv uv ph tp mf txy pxy xy pi nu tau kw kg pa bar atm h0 h1 h3 if97
ih mesh fug cstr pfr flash mccabe thiele ponchon savarit dortmund chemsep brusselator rayleigh hess lie latex katex
json http pdf css tex md py ts tsx mjs init main page layout route module globals favicon next eslint postcss tsconfig
vercel package lock requirements run roadmap checklist flowsheet engine general ideal original panel modal provider
use globe window file shot redesign components schemas settings topology thermodynamic models equations etl yaws
butanol up integration skills skill workflows solver solvers benchmark heteroazeotropo xilenos err out stdout stderr
examples studies lab history verification nondimensionalization archive guides legacy engines plan reversible scripts
audits contracts types public fixtures assembly packaging shared handbook of and physi if windows misc column simulations
env tools repo cleanup inventory evidence qa papers frontend v2 f2 iapws95 repository t0 u0
""".split())
DIRECTORIES = [  # (old prefix, new prefix) - most specific first
    ("frontend/app/motor/", "frontend/app/engine/"), ("frontend/app/laboratorio/", "frontend/app/lab/"),
    ("frontend/app/adimensionalizacion/", "frontend/app/nondimensionalization/"),
    ("frontend/app/columna/", "frontend/app/column/"), ("frontend/app/configuracion/", "frontend/app/settings/"),
    ("frontend/app/simulaciones/", "frontend/app/simulations/"), ("frontend/app/termodinamica/", "frontend/app/thermodynamics/"),
    ("frontend/motores/", "frontend/engines/"), ("frontend/componentes/", "frontend/shared/"),
    ("frontend/documentos/", "docs/frontend/"),
    ("docs/ejemplos/", "docs/examples/"), ("docs/contratos/", "docs/contracts/types/"),
    ("docs/archivo/", "docs/history/archive/"), ("docs/auditoria_motor_2026_10_11/", "docs/history/audits/engine-2026-10-11/"),
    ("tests/fixtures_ensamblaje/", "tests/fixtures/assembly/"), ("empaquetado/", "packaging/"),
    ("archive/", "legacy/archive/"), ("api/", "legacy/api/"),
]
HISTORY_PREFIXES = ("ENTREGA", "INTEGRACION", "INCIDENCIA", "ENCARGO", "SIGUIENTE", "PASAR", "CORRECCION", "AUDITORIA",
                    "RECORRIDO", "INICIO", "COORDINACION", "CONSOLIDACION", "PENDIENTES", "PLAN", "PREPARACION",
                    "REVISION", "PRUEBAS", "ESTADO", "ESCENARIOS", "CONTRATO_CLAUDE", "CONTINUIDAD")
OVERRIDES = {  # explicit names where word-by-word order reads badly
    "ARCHITECTURE.md": "ARCHITECTURE.md",
    "docs/history/build-log.md": "docs/history/roadmap-2025.md",
    "docs/engine/engine-map.md": "docs/engine/engine-map.md",
    "docs/engine/multiphysics-roadmap.md": "docs/engine/multiphysics-roadmap.md",
    "docs/engine/engine-checklist.md": "docs/engine/engine-checklist.md",
    "docs/nondimensionalization/scope.md": "docs/nondimensionalization/scope.md",
    "docs/nondimensionalization/continuity.md": "docs/nondimensionalization/continuity.md",
    "docs/contracts/nondimensionalization-core.md": "docs/contracts/nondimensionalization-core.md",
    "docs/contracts/common-model.md": "docs/contracts/common-model.md",
    "docs/contracts/thermodynamic-layer.md": "docs/contracts/thermodynamic-layer.md",
    "docs/contracts/units-service.md": "docs/contracts/units-service.md",
    "docs/contracts/results-format.md": "docs/contracts/results-format.md",
    "docs/engine/vertical-slice.md": "docs/engine/vertical-slice.md",
    "docs/engine/balance-engine.md": "docs/engine/balance-engine.md",
    "docs/engine/multiphysics-battery.md": "docs/engine/multiphysics-battery.md",
    "frontend/app/motor/hojasMotor.ts": "frontend/app/engine/engineSheets.ts",
    "frontend/app/motor/resolverEngine.ts": "frontend/app/engine/solveOnEngine.ts",
    "frontend/app/motor/ResolverHoja.tsx": "frontend/app/engine/SolveSheet.tsx",
    "frontend/app/motor/HojaGuardada.tsx": "frontend/app/engine/SavedSheet.tsx",
    "frontend/app/motor/TermodinamicaHoja.tsx": "frontend/app/engine/SheetThermodynamics.tsx",
    "frontend/app/motor/ubicacionEcuaciones.ts": "frontend/app/engine/equationPlacement.ts",
    "frontend/app/motor/recorridoTermodinamico.ts": "frontend/app/engine/thermodynamicDerivation.ts",
    "backend/main.py": "backend/main.py", "main.py": "examples/reactive_column.py",
    "ARQUITECTURA_INTEGRACION_MULTIFISICA.md": "docs/history/multiphysics-integration-architecture.md",
    "docs/history/frontend/multiphysics-integration-architecture.md": "docs/history/frontend/multiphysics-integration-architecture.md",
    "docs/papers/nondimensionalization-paper.md": "docs/papers/nondimensionalization-paper.md",
    "docs/papers/nondimensionalization-paper.tex": "docs/papers/nondimensionalization-paper.tex",
    "frontend/documentos/adimensionalizacion/main.tex": "docs/papers/nondimensionalization-paper-frontend.tex",
    "docs/engine/open-boundary-water-air-design.md": "docs/engine/open-boundary-water-air-design.md",
    "docs/engine/property-catalog.md": "docs/engine/property-catalog.md",
    "docs/engine/equilibrium-diagrams.md": "docs/engine/equilibrium-diagrams.md",
    "docs/engine/dynamic-assembly.md": "docs/engine/dynamic-assembly.md",
    "docs/engine/multiphase-equilibrium.md": "docs/engine/multiphase-equilibrium.md",
    "docs/engine/thermodynamics-h0-h1.md": "docs/engine/thermodynamics-h0-h1.md",
    "docs/engine/thermodynamics-h3.md": "docs/engine/thermodynamics-h3.md",
    "docs/engine/thermodynamics-n-components.md": "docs/engine/thermodynamics-n-components.md",
    "docs/engine/unifac.md": "docs/engine/unifac.md",
    "docs/engine/multiphase-consolidation.md": "docs/engine/multiphase-consolidation.md",
    "docs/10-destilacion-reactiva.md": "docs/guides/10-reactive-distillation.md",
    "docs/engine/matter-coupling.md": "docs/engine/matter-coupling.md",
    "docs/engine/decision-components-ports-sources.md": "docs/engine/decision-components-ports-sources.md",
    "docs/engine/control-volume-definition.md": "docs/engine/control-volume-definition.md",
    "docs/engine/energy-foundation.md": "docs/engine/energy-foundation.md",
    "docs/engine/matter-test-sheets.md": "docs/engine/matter-test-sheets.md",
    "docs/engine/multicomponent-test-sheets.md": "docs/engine/multicomponent-test-sheets.md",
    "docs/engine/fundamental-equations.md": "docs/engine/fundamental-equations.md",
    "docs/engine/energy-equations-refinement.md": "docs/engine/energy-equations-refinement.md",
    "docs/engine/sheet-solver.md": "docs/engine/sheet-solver.md",
    "docs/engine/balances-ui.md": "docs/engine/balances-ui.md",
    "frontend/CONTRATO_BACKEND_TRAZABILIDAD.md": "docs/contracts/backend-traceability.md",
    "frontend/CONTRATO_LABORATORIO_TERMODINAMICA.md": "docs/contracts/lab-thermodynamics.md",
    "frontend/CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md": "docs/history/frontend/dynamic-studies-contract-claude.md",
    "frontend/SUPUESTOS_POR_VOLUMEN_CLAUDE.md": "docs/history/frontend/per-volume-assumptions-claude.md",
    "docs/ENTREGA_LABORATORIO_CODEX.md": "docs/history/lab-delivery-codex.md",
    "docs/history/audits/engine-audit-2026-10-11.md": "docs/history/audits/engine-audit-2026-10-11.md",
    "docs/01-arquitectura.md": "docs/guides/01-architecture.md",
}
TEXT_EXT = {".md", ".py", ".ts", ".tsx", ".mjs", ".js", ".json", ".yml", ".yaml", ".ps1", ".css", ".txt", ".tex", ".toml", ".cfg"}
GENERATED_EXT = {".png", ".jpg", ".jpeg", ".log", ".tsbuildinfo"}

def git_lines(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()

def words(name):
    return re.findall(r"\d+[A-Za-z]+(?=$|[-_.])|[A-Z]?[a-zà-ÿ]+\d*|[A-Z]+\d*(?![a-z])|\d+", name)

def translate_words(ws, unknown):
    out = []
    for w in ws:
        low = w.lower()
        if low[:1].isdigit() or low in KEEP:  # numbers and quantities such as 25c, 1bar
            out.append(w); continue
        if low in GLOSSARY:
            t = GLOSSARY[low]
            if t:
                out.append(t)
            continue
        unknown[low] += 1
        out.append(w)
    return out

def restyle(original, translated):
    """Rebuild a name in the same style as the original (camelCase, PascalCase, snake, kebab, UPPER)."""
    parts = [p for t in translated for p in t.split("_")]
    if not parts:
        return original
    if original.isupper() and len(parts) == 1:
        return parts[0].upper()  # LEEME -> README
    if "-" in original:
        return "-".join(p.lower() for p in parts)
    if "_" in original and original.upper() == original:
        return "-".join(p.lower() for p in parts)  # UPPER_SNAKE docs become kebab-case
    if "_" in original:
        return "_".join(p.lower() for p in parts)
    if original[:1].isupper():
        return "".join(p[:1].upper() + p[1:] for p in parts)
    first, *rest = parts
    return first.lower() + "".join(p[:1].upper() + p[1:] for p in rest)

def translate_segment(seg, unknown):
    if seg.startswith("[") or seg.startswith(".") or seg.startswith("__"):
        return seg
    m = re.match(r"^(.*?)((?:\.[A-Za-z0-9]+)*)$", seg)
    stem, ext = m.group(1), m.group(2)
    if not stem:
        return seg
    tokens = re.split(r"([-_.])", stem)
    if stem.upper() == stem and "_" in stem or "-" in stem or "_" in stem:
        new = restyle(stem, translate_words(words(stem), unknown))
    else:
        new = restyle(stem, translate_words(words(stem), unknown))
    return new + ext

def category(path, status):
    p = Path(path)
    name, ext = p.name, p.suffix.lower()
    if ext in GENERATED_EXT or name.startswith("qa-"):
        return "generated"
    if re.match(r"frontend/(qa_|auditoria_experimentar)", path):
        return "evidence"
    if path.startswith("books/") or ext == ".pdf":
        return "local-reference"
    if re.match(r"frontend/(verificar|auditar)_", path) or re.match(r"tests/(validar|auditoria|generar)_", path):
        return "test"
    if ext == ".md":
        top = name.split("_")[0].split(".")[0]
        if name in ("README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "LEEME.md") or path in OVERRIDES:
            return "doc-current"
        if any(name.startswith(h) for h in HISTORY_PREFIXES) or path.startswith("docs/archivo/"):
            return "doc-history"
        return "doc-current"
    if path.startswith("docs/ejemplos/"):
        return "example"
    if ext in {".py", ".ts", ".tsx", ".mjs", ".js", ".css", ".ps1"}:
        return "code"
    return "other"

def destination(path, cat, unknown):
    if path in OVERRIDES:
        return OVERRIDES[path]
    if cat == "generated":
        return "(delete or move to .tmp/)"
    if cat == "evidence":
        return "/".join(translate_segment(x, unknown) for x in ("docs/history/qa/" + path.split("/", 1)[1].removeprefix("qa_")).split("/"))
    if cat == "local-reference":
        return "(keep outside git; local only)"
    new = path
    for old, rep in DIRECTORIES:
        if new.startswith(old):
            new = rep + new[len(old):]
            break
    name = Path(path).name
    if cat == "doc-history" and not path.startswith("docs/archivo/"):
        new = "docs/history/" + ("frontend/" if path.startswith("frontend/") else "") + name
    elif cat == "doc-current" and path.startswith("frontend/") and path.count("/") == 1 and name not in ("README.md", "AGENTS.md", "CLAUDE.md"):
        new = "docs/engine/" + name
    elif re.match(r"docs/\d\d-", path):
        new = "docs/guides/" + name
    elif cat == "test" and path.startswith("frontend/"):
        new = "frontend/verification/" + name
    elif re.match(r"frontend/(sincronizar|preparar|compilar|shot|navegador)", path):
        new = "frontend/scripts/" + name
    elif re.match(r"ejemplo_[^/]+\.py$", path):
        new = "examples/" + name
    elif path.startswith("docs/ejemplos/") and path.count("/") == 2:
        prefix = name.split("-")[0]
        group = {"estudio": "studies", "laboratorio": "lab", "motor": "engine", "adimensionalizacion": "nondimensionalization"}.get(prefix, "misc")
        new = f"docs/examples/{group}/{name}"
    parts = new.split("/")
    return "/".join(translate_segment(s, unknown) for s in parts)

def main():
    tracked = set(git_lines("ls-files"))
    modified = {l[3:] for l in git_lines("status", "--porcelain=v1") if l[:2].strip() and not l.startswith("??")}
    untracked = set(git_lines("ls-files", "-o", "--exclude-standard"))
    ignored = {f for f in git_lines("ls-files", "-o", "-i", "--exclude-standard")
               if not re.search(r"node_modules/|\.next/|__pycache__/|\.tmp/|\.pyc$", f)}
    files = sorted(f for f in tracked | untracked | ignored if not re.search(r"(^|/)(node_modules|\.next|\.tmp)/", f))

    # Reference index: which files mention each token (file names, module stems).
    mentions = defaultdict(set)
    for f in files:
        fp = ROOT / f
        if fp.suffix.lower() not in TEXT_EXT or not fp.exists() or fp.stat().st_size > 3_000_000:
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for tok in set(re.findall(r"[\w.\-\[\]]+", text)):
            mentions[tok].add(f)
            for sub in tok.split("."):
                mentions[sub].add(f)

    unknown = Counter()
    rows = []
    for f in files:
        status = "modified" if f in modified else "tracked" if f in tracked else "ignored" if f in ignored else "untracked"
        cat = category(f, status)
        p = Path(f)
        refs = mentions.get(p.name, set()) | (mentions.get(p.stem, set()) if cat in ("code", "test") and len(p.stem) > 4 else set())
        refs.discard(f)
        dest = destination(f, cat, unknown)
        rows.append({"path": f, "status": status, "category": cat, "references": len(refs),
                     "proposed": dest, "changes": "no" if dest == f else "yes"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    print(f"{len(rows)} files -> {OUT.relative_to(ROOT)}")
    if "--summary" in sys.argv:
        by = Counter((r["category"], r["status"]) for r in rows)
        for (c, s), n in sorted(by.items()):
            print(f"  {c:16} {s:10} {n}")
        print("unknown tokens:", " ".join(f"{t}:{n}" for t, n in unknown.most_common()))

if __name__ == "__main__":
    main()
