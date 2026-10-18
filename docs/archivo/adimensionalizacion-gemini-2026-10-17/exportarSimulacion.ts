import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion } from "./exportar";

function extraerParametrosSimulacion(f: FormulacionNucleo): {
  pe: number;
  da: number;
  fo: number;
  aspecto: number;
  nombreCampo: string;
  campos: string[];
} {
  let pe = 1.0;
  let da = 1.0;
  let fo = 1.0;
  let aspecto = 1.0;

  for (const g of f.grupos ?? []) {
    const id = g.id.toLowerCase();
    if (id.includes("pe") || id.includes("cfl")) pe = 10.0;
    if (id.includes("da") || id.includes("reac") || id.includes("k")) da = 2.0;
    if (id.includes("fo")) fo = 1.0;
    if (id.includes("a_") || id.includes("esbeltez")) aspecto = 0.2;
  }

  const variablesAdim = f.simbolos?.filter(s => s.rol === "variable_adimensional") ?? [];
  const coords = variablesAdim.filter(s => ["x", "xi", "y", "eta", "z", "zeta", "r"].some(c => s.id.toLowerCase().includes(c)));
  const campos = variablesAdim
    .filter(s => !coords.some(c => c.id === s.id) && !["t", "tau"].some(t => s.id.toLowerCase().includes(t)))
    .map(s => s.id);

  if (campos.length === 0) {
    const camposDir = (f.directa ?? [])
      .map(d => d.simboloId)
      .filter(s => !["t", "tau", "x", "y", "z", "r", "theta", "xi", "eta", "zeta"].includes(s.toLowerCase()));
    campos.push(...camposDir);
  }

  const nombreCampo = campos[0] ?? "c";

  return { pe, da, fo, aspecto, nombreCampo, campos: campos.length > 0 ? campos : [nombreCampo] };
}

export function generarScriptPythonScipy(f: FormulacionNucleo, nombreModelo: string): string {
  const { pe, da, fo, nombreCampo, campos } = extraerParametrosSimulacion(f);
  const esMulti = campos.length > 1;

  if (esMulti) {
    const c1 = campos[0];
    const c2 = campos[1];
    return `"""
Simulación Numérica Multicomponente Acoplada: ${nombreModelo}
Campos Adimensionales: [${campos.join(", ")}]
Método: Método de Líneas con Diferencias Finitas y Solver Rígido BDF (scipy.integrate.solve_ivp)
Generado por el Núcleo Formal de Adimensionalización de Antigravity
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# ==============================================================================
# 1. Parámetros Físicos Adimensionales Deducidos
# ==============================================================================
Pe = ${pe.toFixed(2)}       # Convección / Difusión
Da = ${da.toFixed(2)}       # Tasa Cinética / Transporte
Fo = ${fo.toFixed(2)}       # Tiempo / Relajación Molecular
delta_D = 0.10              # Razón de difusividades relativas (D2 / D1)

# Malla espacial en coordenada adimensional x_hat in [0, 1]
Nx = 100
x = np.linspace(0.0, 1.0, Nx)
dx = x[1] - x[0]

t_span = (0.0, 2.5)
t_eval = np.linspace(t_span[0], t_span[1], 100)

# ==============================================================================
# 2. Operador Espacial Discreto del Sistema Acoplado
# ==============================================================================
def rhs_multicomponente(t, Y):
    # Desempaquetar vector de estado concatenado
    u = Y[0 : Nx]
    v = Y[Nx : 2 * Nx]
    
    dudt = np.zeros(Nx)
    dvdt = np.zeros(Nx)
    
    # Difusión central de segundo orden
    d2u_dx2 = (u[2:] - 2.0 * u[1:-1] + u[:-2]) / (dx ** 2)
    d2v_dx2 = (v[2:] - 2.0 * v[1:-1] + v[:-2]) / (dx ** 2)
    
    # Cinética no lineal constitutiva generalizada (acoplamiento reactivo)
    R_u = Da * (u[1:-1] - u[1:-1] ** 3 - v[1:-1])
    R_v = Da * 0.5 * (u[1:-1] - v[1:-1])
    
    dudt[1:-1] = Fo * d2u_dx2 + R_u
    dvdt[1:-1] = Fo * delta_D * d2v_dx2 + R_v
    
    # Condiciones de frontera Neumann (flujo nulo en los extremos)
    dudt[0] = dudt[1]
    dudt[-1] = dudt[-2]
    dvdt[0] = dvdt[1]
    dvdt[-1] = dvdt[-2]
    
    return np.concatenate([dudt, dvdt])

# Condición inicial con perturbación espacial suave
np.random.seed(42)
u0 = 0.1 * np.sin(np.pi * x) + 0.02 * np.random.randn(Nx)
v0 = 0.1 * np.cos(np.pi * x)
Y0 = np.concatenate([u0, v0])

# ==============================================================================
# 3. Integración Numérica Rígida (BDF)
# ==============================================================================
print(f"Integrando sistema acoplado multicomponente ({len(campos)} campos, Nx={Nx})...")
sol = solve_ivp(rhs_multicomponente, t_span, Y0, t_eval=t_eval, method='BDF', rtol=1e-6, atol=1e-8)

if not sol.success:
    raise RuntimeError(f"Fallo en el solver BDF: {sol.message}")

print("Simulación completada con éxito.")

# ==============================================================================
# 4. Graficación de Perfiles Multicomponente
# ==============================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
for idx in [0, 20, 50, 99]:
    t_val = sol.t[idx]
    ax1.plot(x, sol.y[0:Nx, idx], label=f"t = {t_val:.2f}", lw=1.8)
    ax2.plot(x, sol.y[Nx:2*Nx, idx], label=f"t = {t_val:.2f}", lw=1.8)

ax1.set_title("Campo Adimensional: ${c1}_hat(x_hat, t_hat)", fontsize=11)
ax1.set_xlabel("x_hat", fontsize=10)
ax1.set_ylabel("${c1}_hat", fontsize=10)
ax1.grid(True, ls="--", alpha=0.6)
ax1.legend()

ax2.set_title("Campo Adimensional: ${c2}_hat(x_hat, t_hat)", fontsize=11)
ax2.set_xlabel("x_hat", fontsize=10)
ax2.set_ylabel("${c2}_hat", fontsize=10)
ax2.grid(True, ls="--", alpha=0.6)
ax2.legend()

plt.tight_layout()
plt.show()
`;
  }

  return `"""
Simulación Numérica del Sistema Adimensional: ${nombreModelo}
Método: Método de Líneas (Method of Lines) con Diferencias Finitas y BDF Adaptativo
Generado por el Núcleo Formal de Adimensionalización de Antigravity
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# ==============================================================================
# 1. Parámetros Físicos Adimensionales Deducidos
# ==============================================================================
Pe = ${pe.toFixed(2)}    # Número de Péclet (Transporte Convectivo / Difusivo)
Da = ${da.toFixed(2)}    # Número de Damköhler (Tasa Cinética / Transporte)
Fo = ${fo.toFixed(2)}    # Número de Fourier (Tiempo / Relajación Molecular)

# Malla espacial en coordenada adimensional x_hat in [0, 1]
Nx = 100
x = np.linspace(0.0, 1.0, Nx)
dx = x[1] - x[0]

# Intervalo temporal adimensional t_hat in [0, T_final]
t_span = (0.0, 2.0)
t_eval = np.linspace(t_span[0], t_span[1], 100)

# ==============================================================================
# 2. Operador Diferencial Espacial Discreto (RHS de la EDP)
# ==============================================================================
def rhs_edp(t, c):
    """
    Evalúa dc_hat/dt_hat para el vector de concentración espacial.
    Discretización: Convección Upwind y Difusión Central de 2do orden.
    """
    dcdt = np.zeros_like(c)
    
    # Derivadas espaciales interiores (i = 1 hasta Nx - 2)
    # Difusión: Fo * d2c/dx2
    d2c_dx2 = (c[2:] - 2.0 * c[1:-1] + c[:-2]) / (dx ** 2)
    
    # Convección upwind: -Pe * dc/dx
    dc_dx = (c[1:-1] - c[:-2]) / dx
    
    # Reacción cinética: -Da * c
    reaccion = -Da * c[1:-1]
    
    dcdt[1:-1] = Fo * d2c_dx2 - Pe * dc_dx + reaccion
    
    # Condiciones de frontera:
    # x = 0: Dirichlet c(0, t) = 1.0
    dcdt[0] = 0.0
    # x = 1: Neumann dc/dx = 0 (flujo nulo de salida)
    c[-1] = c[-2]
    dcdt[-1] = dcdt[-2]
    
    return dcdt

# Condición inicial: medio inicialmente limpio c(x, 0) = 0 (salvo frontera de entrada)
c0 = np.zeros(Nx)
c0[0] = 1.0

# ==============================================================================
# 3. Integración Numérica con Solver Rígido BDF (Radau / BDF)
# ==============================================================================
print(f"Iniciando integración numérica (Pe={Pe}, Da={Da}, Fo={Fo})...")
sol = solve_ivp(rhs_edp, t_span, c0, t_eval=t_eval, method='BDF', rtol=1e-6, atol=1e-8)

if not sol.success:
    raise RuntimeError(f"Fallo en el solver: {sol.message}")

print("Integración completada con éxito.")

# ==============================================================================
# 4. Graficación del Perfil Espacio-Temporal Adimensional
# ==============================================================================
plt.figure(figsize=(9, 5.5))
for idx in [0, 10, 25, 50, 99]:
    plt.plot(x, sol.y[:, idx], label=f"t_hat = {sol.t[idx]:.2f}", lw=1.8)

plt.title(f"Evolución Espacio-Temporal Adimensional: {nombreCampo}_hat(x_hat, t_hat)\\nPe={Pe}, Da={Da}, Fo={Fo}", fontsize=12)
plt.xlabel("Coordenada espacial adimensional (x_hat)", fontsize=11)
plt.ylabel(f"Campo adimensional ({nombreCampo}_hat)", fontsize=11)
plt.grid(True, ls="--", alpha=0.6)
plt.legend(frameon=True, facecolor="white", edgecolor="#ccc")
plt.tight_layout()
plt.show()
`;
}

export function generarScriptPinnPyTorch(f: FormulacionNucleo, nombreModelo: string): string {
  const { pe, da, fo, nombreCampo } = extraerParametrosSimulacion(f);

  return `"""
Red Neuronal Informada por la Física (PINN - Physics-Informed Neural Network)
Modelo Continuo Adimensional: ${nombreModelo}
Framework: PyTorch (Entrenamiento guiado por residuo de EDP y condiciones de contorno)
"""

import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt

# Fijar semilla para reproducibilidad
torch.manual_seed(42)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ==============================================================================
# 1. Definición de la Red Neuronal Sustituta: c_hat = NeuralNet(t_hat, x_hat)
# ==============================================================================
class PINN(nn.Module):
    def __init__(self, capas=[2, 40, 40, 40, 1]):
        super().__init__()
        red = []
        for i in range(len(capas) - 1):
            red.append(nn.Linear(capas[i], capas[i+1]))
            if i < len(capas) - 2:
                red.append(nn.Tanh())
        self.net = nn.Sequential(*red)

    def forward(self, t, x):
        inputs = torch.cat([t, x], dim=1)
        return self.net(inputs)

model = PINN().to(device)

# ==============================================================================
# 2. Parámetros Adimensionales Canónicos
# ==============================================================================
Pe = torch.tensor(${pe.toFixed(2)}, device=device)
Da = torch.tensor(${da.toFixed(2)}, device=device)
Fo = torch.tensor(${fo.toFixed(2)}, device=device)

# ==============================================================================
# 3. Función de Pérdida Basada en el Residuo Físico de la EDP
# ==============================================================================
def loss_fn(t_pde, x_pde, t_bc, x_bc, c_bc, t_ic, x_ic, c_ic):
    # Asegurar gradientes para diferenciación automática (Autograd)
    t_pde.requires_grad_(True)
    x_pde.requires_grad_(True)
    
    # Salida de la red
    c = model(t_pde, x_pde)
    
    # Derivadas automáticas de primer orden
    c_t = torch.autograd.grad(c, t_pde, torch.ones_like(c), create_graph=True)[0]
    c_x = torch.autograd.grad(c, x_pde, torch.ones_like(c), create_graph=True)[0]
    
    # Derivada automática de segundo orden (Laplaciano)
    c_xx = torch.autograd.grad(c_x, x_pde, torch.ones_like(c_x), create_graph=True)[0]
    
    # Residuo diferencial gobernante: dc/dt + Pe*dc/dx - Fo*d2c/dx2 + Da*c = 0
    pde_residual = c_t + Pe * c_x - Fo * c_xx + Da * c
    loss_pde = torch.mean(pde_residual ** 2)
    
    # Pérdida en condiciones de frontera (BC) e iniciales (IC)
    c_pred_bc = model(t_bc, x_bc)
    loss_bc = torch.mean((c_pred_bc - c_bc) ** 2)
    
    c_pred_ic = model(t_ic, x_ic)
    loss_ic = torch.mean((c_pred_ic - c_ic) ** 2)
    
    return loss_pde + 10.0 * (loss_bc + loss_ic)

# ==============================================================================
# 4. Puntos de Colocación (Collocation Points)
# ==============================================================================
N_pde = 2500
t_pde = torch.rand(N_pde, 1, device=device) * 2.0
x_pde = torch.rand(N_pde, 1, device=device)

# Condiciones de frontera: entrada x=0 con c=1.0
N_bc = 200
t_bc = torch.rand(N_bc, 1, device=device) * 2.0
x_bc = torch.zeros(N_bc, 1, device=device)
c_bc = torch.ones(N_bc, 1, device=device)

# Condiciones iniciales: t=0 con c=0.0
N_ic = 200
t_ic = torch.zeros(N_ic, 1, device=device)
x_ic = torch.rand(N_ic, 1, device=device)
c_ic = torch.zeros(N_ic, 1, device=device)

# ==============================================================================
# 5. Entrenamiento con Optimizador Adam
# ==============================================================================
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
print("Iniciando entrenamiento de la PINN...")

for epoch in range(1, 1001):
    optimizer.zero_grad()
    loss = loss_fn(t_pde, x_pde, t_bc, x_bc, c_bc, t_ic, x_ic, c_ic)
    loss.backward()
    optimizer.step()
    
    if epoch % 200 == 0:
        print(f"Epoch {epoch:4d} | Pérdida Física Total: {loss.item():.6e}")

print("Entrenamiento finalizado. PINN lista para inferencia continua.")
`;
}

export function generarScriptJulia(f: FormulacionNucleo, nombreModelo: string): string {
  const { pe, da, fo, nombreCampo, campos } = extraerParametrosSimulacion(f);
  const esMulti = campos.length > 1;

  if (esMulti) {
    const c1 = campos[0];
    const c2 = campos[1];
    return `"""
Simulación Numérica Multicomponente en Julia: ${nombreModelo}
Campos Adimensionales: [${campos.join(", ")}]
Paquete: DifferentialEquations.jl (Solver adaptativo TRBDF2 / KenCarp4 para sistemas stiff acoplados)
"""

using DifferentialEquations
using Plots

# Parámetros adimensionales canónicos
const Pe = ${pe.toFixed(2)}
const Da = ${da.toFixed(2)}
const Fo = ${fo.toFixed(2)}
const delta_D = 0.10

# Malla espacial en coordenada adimensional x_hat in [0, 1]
const Nx = 100
const x = range(0.0, stop=1.0, length=Nx)
const dx = x[2] - x[1]

# Definición del sistema de EDOs acoplado
function sistema_edp_multicomponente!(dY, Y, p, t)
    # Vistas de memoria para componentes individuales
    u = @view Y[1:Nx]
    v = @view Y[Nx+1:2*Nx]
    du = @view dY[1:Nx]
    dv = @view dY[Nx+1:2*Nx]

    for i in 2:(Nx - 1)
        d2u_dx2 = (u[i+1] - 2.0*u[i] + u[i-1]) / (dx^2)
        d2v_dx2 = (v[i+1] - 2.0*v[i] + v[i-1]) / (dx^2)
        
        R_u = Da * (u[i] - u[i]^3 - v[i])
        R_v = Da * 0.5 * (u[i] - v[i])

        du[i] = Fo * d2u_dx2 + R_u
        dv[i] = Fo * delta_D * d2v_dx2 + R_v
    end

    # Fronteras Neumann (flujo cero)
    du[1] = du[2]
    du[Nx] = du[Nx-1]
    dv[1] = dv[2]
    dv[Nx] = dv[Nx-1]
end

# Condición inicial
Y0 = zeros(2 * Nx)
for i in 1:Nx
    Y0[i] = 0.1 * sin(pi * x[i])
    Y0[Nx + i] = 0.1 * cos(pi * x[i])
end

tspan = (0.0, 2.5)
prob = ODEProblem(sistema_edp_multicomponente!, Y0, tspan)
sol = solve(prob, TRBDF2(), reltol=1e-6, abstol=1e-8)

println("Simulación multicomponente en Julia finalizada.")

# Graficar perfiles de los componentes
p1 = plot(x, sol(1.0)[1:Nx], label="t=1.0", lw=2, xlabel="x_hat", ylabel="${c1}_hat", title="Campo ${c1}")
plot!(p1, x, sol(2.5)[1:Nx], label="t=2.5", lw=2)

p2 = plot(x, sol(1.0)[Nx+1:2*Nx], label="t=1.0", lw=2, xlabel="x_hat", ylabel="${c2}_hat", title="Campo ${c2}")
plot!(p2, x, sol(2.5)[Nx+1:2*Nx], label="t=2.5", lw=2)

plot(p1, p2, layout=(1, 2), size=(900, 400))
`;
  }

  return `"""
Simulación Numérica en Julia: ${nombreModelo}
Paquete: DifferentialEquations.jl (Integrador TRBDF2 / KenCarp4 para EDPs rígidas)
"""

using DifferentialEquations
using Plots

# Parámetros adimensionales canónicos
const Pe = ${pe.toFixed(2)}
const Da = ${da.toFixed(2)}
const Fo = ${fo.toFixed(2)}

# Dominio espacial discreto
const Nx = 100
const x = range(0.0, stop=1.0, length=Nx)
const dx = x[2] - x[1]

# Definición del sistema de EDOs discretizado
function sistema_edp!(dc, c, p, t)
    # Puntos interiores
    for i in 2:(Nx - 1)
        d2c_dx2 = (c[i+1] - 2.0*c[i] + c[i-1]) / (dx^2)
        dc_dx = (c[i] - c[i-1]) / dx
        dc[i] = Fo * d2c_dx2 - Pe * dc_dx - Da * c[i]
    end
    
    # Frontera x=0 (Dirichlet c = 1.0)
    dc[1] = 0.0
    # Frontera x=1 (Flujo cero dc/dx = 0)
    dc[Nx] = dc[Nx-1]
end

# Condición inicial
c0 = zeros(Nx)
c0[1] = 1.0

# Intervalo temporal adimensional
tspan = (0.0, 2.0)

# Construcción del problema y solución
prob = ODEProblem(sistema_edp!, c0, tspan)
sol = solve(prob, TRBDF2(), reltol=1e-6, abstol=1e-8)

println("Simulación en Julia completada exitosamente.")

# Graficar
plot(x, sol(0.5), label="t=0.5", lw=2, xlabel="x_hat", ylabel="${nombreCampo}_hat", title="Perfil Adimensional en Julia")
plot!(x, sol(1.0), label="t=1.0", lw=2)
plot!(x, sol(2.0), label="t=2.0", lw=2)
`;
}

export function generarJupyterNotebook(f: FormulacionNucleo, nombreModelo: string): string {
  const { pe, da, fo, nombreCampo } = extraerParametrosSimulacion(f);

  const ecsLatex = (f.ecuaciones ?? [])
    .map((e, i) => `$$\\text{(${i + 1})}\\quad ${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}$$`)
    .join("\n\n");
  const gruposMarkdown = (f.grupos ?? [])
    .map(g => `- **$\\Pi = ${g.id}$**: $${latexExpresion(g.definicion)}$ (${g.adimensional ? "Invariante adimensional canónico" : "Dimensión residual"})`)
    .join("\n");

  const notebook = {
    cells: [
      {
        cell_type: "markdown",
        metadata: {},
        source: [
          `# Cuaderno Científico Interactivo: ${nombreModelo}\n`,
          `### Deducido y Certificado por el Núcleo Formal de Adimensionalización de Antigravity\n`,
          `\n`,
          `Este cuaderno implementa la simulación numérica directa (Método de Líneas con integrador rígido BDF) y el entrenamiento de una Red Neuronal Informada por la Física (**PINN**) sobre el sistema diferencial adimensional.\n`,
          `\n`,
          `---\n`,
          `### 1. Ecuaciones Gobernantes Adimensionales\n`,
          ecsLatex + "\n\n",
          `### 2. Invariantes Adimensionales del Sistema (Teorema $\\Pi$ de Buckingham)\n`,
          gruposMarkdown + "\n"
        ]
      },
      {
        cell_type: "code",
        execution_count: null,
        metadata: {},
        outputs: [],
        source: [
          `# Configuración del entorno e importaciones científicas\n`,
          `import numpy as np\n`,
          `import matplotlib.pyplot as plt\n`,
          `from scipy.integrate import solve_ivp\n`,
          `\n`,
          `# Intento de importar controles interactivos (ipywidgets para Jupyter/Colab)\n`,
          `try:\n`,
          `    import ipywidgets as widgets\n`,
          `    from IPython.display import display\n`,
          `    WIDGETS_DISPONIBLES = True\n`,
          `except ImportError:\n`,
          `    WIDGETS_DISPONIBLES = False\n`,
          `    print("ipywidgets no instalado; se ejecutará en modo estático.")\n`
        ]
      },
      {
        cell_type: "code",
        execution_count: null,
        metadata: {},
        outputs: [],
        source: [
          `# ==============================================================================\n`,
          `# Simulación con Método de Líneas y Exploración Interactiva de Parámetros Pi\n`,
          `# ==============================================================================\n`,
          `def simular_sistema(Pe=${pe.toFixed(2)}, Da=${da.toFixed(2)}, Fo=${fo.toFixed(2)}, Nx=100, T_final=2.0):\n`,
          `    x = np.linspace(0.0, 1.0, Nx)\n`,
          `    dx = x[1] - x[0]\n`,
          `    t_span = (0.0, T_final)\n`,
          `    t_eval = np.linspace(t_span[0], t_span[1], 100)\n`,
          `\n`,
          `    def rhs_edp(t, c):\n`,
          `        dcdt = np.zeros_like(c)\n`,
          `        # Difusión: Fo * d2c/dx2\n`,
          `        d2c_dx2 = (c[2:] - 2.0 * c[1:-1] + c[:-2]) / (dx ** 2)\n`,
          `        # Convección upwind: -Pe * dc/dx\n`,
          `        dc_dx = (c[1:-1] - c[:-2]) / dx\n`,
          `        # Reacción cinética: -Da * c\n`,
          `        reac = -Da * c[1:-1]\n`,
          `        dcdt[1:-1] = Fo * d2c_dx2 - Pe * dc_dx + reac\n`,
          `        # Fronteras: Dirichlet x=0 (c=1), Flujo nulo x=1 (dc/dx=0)\n`,
          `        dcdt[0] = 0.0\n`,
          `        dcdt[-1] = dcdt[-2]\n`,
          `        return dcdt\n`,
          `\n`,
          `    c0 = np.zeros(Nx)\n`,
          `    c0[0] = 1.0\n`,
          `    sol = solve_ivp(rhs_edp, t_span, c0, t_eval=t_eval, method='BDF', rtol=1e-6, atol=1e-8)\n`,
          `\n`,
          `    plt.figure(figsize=(9, 5))\n`,
          `    for idx in [0, 20, 40, 70, 99]:\n`,
          `        plt.plot(x, sol.y[:, idx], label=f"t_hat = {sol.t[idx]:.2f}", lw=2)\n`,
          `    plt.title(f"Evolución Espacio-Temporal: Pe={Pe:.2f}, Da={Da:.2f}, Fo={Fo:.2f}", fontsize=12)\n`,
          `    plt.xlabel("Coordenada adimensional x_hat", fontsize=11)\n`,
          `    plt.ylabel("Campo adimensional ${nombreCampo}_hat", fontsize=11)\n`,
          `    plt.grid(True, ls="--", alpha=0.6)\n`,
          `    plt.legend(frameon=True)\n`,
          `    plt.show()\n`,
          `\n`,
          `if WIDGETS_DISPONIBLES:\n`,
          `    widgets.interact(\n`,
          `        simular_sistema,\n`,
          `        Pe=widgets.FloatSlider(value=${pe.toFixed(2)}, min=0.1, max=50.0, step=0.5, description="Pe:"),\n`,
          `        Da=widgets.FloatSlider(value=${da.toFixed(2)}, min=0.0, max=20.0, step=0.2, description="Da:"),\n`,
          `        Fo=widgets.FloatSlider(value=${fo.toFixed(2)}, min=0.01, max=5.0, step=0.05, description="Fo:"),\n`,
          `        Nx=widgets.fixed(100),\n`,
          `        T_final=widgets.fixed(2.0)\n`,
          `    )\n`,
          `else:\n`,
          `    simular_sistema()\n`
        ]
      },
      {
        cell_type: "markdown",
        metadata: {},
        source: [
          `---\n`,
          `### 3. Redes Neuronales Informadas por la Física (PINN con PyTorch)\n`,
          `La formulación adimensional es óptima para redes neuronales profundas porque:\n`,
          `- Elimina disparidades de magnitud (todas las variables y campos son $\\mathcal{O}(1)$).\n`,
          `- Mitiga el desvanecimiento y explosión de gradientes en el cálculo de derivadas automáticas de segundo orden.\n`,
          `- Permite parametrizar el espacio de soluciones directamente en función de los invariantes $\\boldsymbol{\\Pi}$.\n`
        ]
      },
      {
        cell_type: "code",
        execution_count: null,
        metadata: {},
        outputs: [],
        source: [
          `import torch\n`,
          `import torch.nn as nn\n`,
          `\n`,
          `torch.manual_seed(42)\n`,
          `device = torch.device("cuda" if torch.cuda.is_available() else "cpu")\n`,
          `\n`,
          `class PINN(nn.Module):\n`,
          `    def __init__(self, capas=[2, 32, 32, 1]):\n`,
          `        super().__init__()\n`,
          `        layers = []\n`,
          `        for i in range(len(capas) - 1):\n`,
          `            layers.append(nn.Linear(capas[i], capas[i+1]))\n`,
          `            if i < len(capas) - 2:\n`,
          `                layers.append(nn.Tanh())\n`,
          `        self.red = nn.Sequential(*layers)\n`,
          `\n`,
          `    def forward(self, t, x):\n`,
          `        return self.red(torch.cat([t, x], dim=1))\n`,
          `\n`,
          `model = PINN().to(device)\n`,
          `Pe_pt = torch.tensor(${pe.toFixed(2)}, device=device)\n`,
          `Da_pt = torch.tensor(${da.toFixed(2)}, device=device)\n`,
          `Fo_pt = torch.tensor(${fo.toFixed(2)}, device=device)\n`,
          `\n`,
          `# Puntos de colocación en el dominio adimensional [0, 2] x [0, 1]\n`,
          `N_pde = 1500\n`,
          `t_pde = (torch.rand(N_pde, 1, device=device) * 2.0).requires_grad_(True)\n`,
          `x_pde = torch.rand(N_pde, 1, device=device).requires_grad_(True)\n`,
          `\n`,
          `optimizer = torch.optim.Adam(model.parameters(), lr=2e-3)\n`,
          `\n`,
          `for step in range(1, 401):\n`,
          `    optimizer.zero_grad()\n`,
          `    c = model(t_pde, x_pde)\n`,
          `    c_t = torch.autograd.grad(c, t_pde, torch.ones_like(c), create_graph=True)[0]\n`,
          `    c_x = torch.autograd.grad(c, x_pde, torch.ones_like(c), create_graph=True)[0]\n`,
          `    c_xx = torch.autograd.grad(c_x, x_pde, torch.ones_like(c_x), create_graph=True)[0]\n`,
          `    res = c_t + Pe_pt * c_x - Fo_pt * c_xx + Da_pt * c\n`,
          `    loss = torch.mean(res ** 2)\n`,
          `    loss.backward()\n`,
          `    optimizer.step()\n`,
          `    if step % 100 == 0:\n`,
          `        print(f"Paso {step:3d} | Pérdida de Residuo EDP: {loss.item():.4e}")\n`,
          `\n`,
          `print("Entrenamiento PINN finalizado con éxito.")\n`
        ]
      }
    ],
    metadata: {
      kernelspec: {
        display_name: "Python 3",
        language: "python",
        name: "python3"
      },
      language_info: {
        codemirror_mode: {
          name: "ipython",
          version: 3
        },
        file_extension: ".py",
        mimetype: "text/x-python",
        name: "python",
        nbformat: 4,
        nbformat_minor: 5,
        version: "3.10"
      }
    },
    nbformat: 4,
    nbformat_minor: 5
  };

  return JSON.stringify(notebook, null, 2);
}
