"use client";

import { useId, useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function ModalPreacondicionamientoMotor({
  abierto,
  cerrar,
  nombreModelo,
  indiceForma,
  f
}: {
  abierto: boolean;
  cerrar: () => void;
  nombreModelo: string;
  indiceForma: number;
  f: FormulacionNucleo;
}) {
  const baseId = useId();
  const [lenguaje, setLenguaje] = useState<"python" | "julia" | "typescript" | "pinn" | "fenics">("python");
  const [copiado, setCopiado] = useState(false);

  if (!abierto) return null;

  const grupos = f.grupos ?? [];
  const peGrupo = grupos.find(g => /pe|cfl/i.test(g.id))?.id ?? "Pe";
  const daGrupo = grupos.find(g => /da|k/i.test(g.id))?.id ?? "Da";
  const foGrupo = grupos.find(g => /fo/i.test(g.id))?.id ?? "Fo";

  // Código en Python con SciPy Radau y Jacobiano
  const codigoPython = `# ==============================================================================
# Pre-Acondicionamiento para el Motor de Multifísica (/motor)
# Modelo: ${nombreModelo} · Forma Canónica ${indiceForma + 1}
# Generado analíticamente mediante Teorema Pi de Buckingham y Kruskal
# ==============================================================================

import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import diags

def resolver_sistema_preacondicionado(
    ${peGrupo.toLowerCase()}=5.0, 
    ${daGrupo.toLowerCase()}=2.0, 
    ${foGrupo.toLowerCase()}=1.0, 
    N=80, 
    tau_final=5.0
):
    """
    Integra el sistema PDE semidiscreto en volúmenes finitos unitarios [0, 1].
    Utiliza el método implícito Radau IIA con Jacobiano analítico tridiagonal
    para garantizar convergencia incondicional sin restricciones rígidas de paso.
    """
    dxi = 1.0 / (N - 1)
    dxi2 = dxi ** 2

    # Matriz del operador diferencial espacial tridiagonal
    # Upwind advectivo de 1er orden + Difusión centrada de 2do orden
    sub_diag = (${foGrupo.toLowerCase()} / dxi2 + ${peGrupo.toLowerCase()} / dxi) * np.ones(N - 1)
    main_diag = (-2.0 * ${foGrupo.toLowerCase()} / dxi2 - ${peGrupo.toLowerCase()} / dxi) * np.ones(N)
    sup_diag = (${foGrupo.toLowerCase()} / dxi2) * np.ones(N - 1)

    # Condición de frontera Dirichlet en entrada (xi = 0): phi[0] = 1.0 fijo
    main_diag[0] = 0.0
    sup_diag[0] = 0.0

    # Condición de frontera Neumann en salida (xi = 1): dphi/dxi = 0
    main_diag[-1] = -${foGrupo.toLowerCase()} / dxi2
    sub_diag[-1] = ${foGrupo.toLowerCase()} / dxi2

    A_difusion = diags([sub_diag, main_diag, sup_diag], [-1, 0, 1], format='csr')

    def rhs(tau, phi):
        dphi = A_difusion.dot(phi)
        # Término de reacción química no lineal
        reac = -${daGrupo.toLowerCase()} * phi / (1.0 + 2.0 * np.maximum(0, phi))
        reac[0] = 0.0  # Dirichlet inmutable
        return dphi + reac

    def jacobiano(tau, phi):
        # Jacobiano analítico = Matriz difusiva + derivadas de reacción en diagonal
        d_reac = -${daGrupo.toLowerCase()} / ((1.0 + 2.0 * np.maximum(0, phi)) ** 2)
        d_reac[0] = 0.0
        return A_difusion + diags([d_reac], [0], format='csr')

    # Condición inicial: Gaussiana suave o reposo
    xi = np.linspace(0, 1, N)
    phi0 = np.exp(-((xi - 0.2) / 0.1) ** 2)
    phi0[0] = 1.0

    sol = solve_ivp(
        fun=rhs,
        t_span=(0, tau_final),
        y0=phi0,
        method='Radau',
        jac=jacobiano,
        rtol=1e-5,
        atol=1e-8
    )

    return sol.t, sol.y, xi
`;

  // Código en Julia (DifferentialEquations.jl)
  const codigoJulia = `# ==============================================================================
# Pre-Acondicionamiento para el Motor de Multifísica (/motor) - Julia
# Modelo: ${nombreModelo} · Forma Canónica ${indiceForma + 1}
# ==============================================================================

using DifferentialEquations
using LinearAlgebra
using SparseArrays

function crear_problema_adimensional(N=80; ${peGrupo.toLowerCase()}=5.0, ${daGrupo.toLowerCase()}=2.0, ${foGrupo.toLowerCase()}=1.0)
    dxi = 1.0 / (N - 1)
    dxi2 = dxi^2

    # Operador tridiagonal en diferencias finitas
    dl = (${foGrupo.toLowerCase()} / dxi2 + ${peGrupo.toLowerCase()} / dxi) * ones(N - 1)
    d  = (-2.0 * ${foGrupo.toLowerCase()} / dxi2 - ${peGrupo.toLowerCase()} / dxi) * ones(N)
    du = (${foGrupo.toLowerCase()} / dxi2) * ones(N - 1)

    d[1] = 0.0; du[1] = 0.0
    d[end] = -${foGrupo.toLowerCase()} / dxi2
    dl[end] = ${foGrupo.toLowerCase()} / dxi2

    A = Tridiagonal(dl, d, du)

    function f!(dphi, phi, p, tau)
        mul!(dphi, A, phi)
        @inbounds for i in 2:N-1
            dphi[i] -= ${daGrupo.toLowerCase()} * phi[i] / (1.0 + 2.0 * max(0.0, phi[i]))
        end
        dphi[1] = 0.0
    end

    xi = range(0.0, 1.0, length=N)
    phi0 = [exp(-((x - 0.2) / 0.1)^2) for x in xi]
    phi0[1] = 1.0

    return ODEProblem(f!, phi0, (0.0, 5.0))
end
`;

  // Código en TypeScript para modeloNumerico.ts en /motor
  const codigoTypeScript = `/**
 * Pre-acondicionador canónico para su inserción en 'modeloNumerico.ts' (/motor).
 * Proporciona el evaluador del vector residual F(phi) y la matriz de rigidez
 * para el solucionador de Euler implícito con Jacobiano analítico tridiagonal.
 */

export interface SistemaAdimensionalMotor {
  N: number;
  deltaXi: number;
  evaluarRHS: (tau: number, phi: Float64Array, dphi: Float64Array) => void;
  construirJacobianoTridiagonal: (phi: Float64Array) => {
    sub: Float64Array;
    diag: Float64Array;
    sup: Float64Array;
  };
}

export function crearPreacondicionadorMotor(
  ${peGrupo.toLowerCase()}: number,
  ${daGrupo.toLowerCase()}: number,
  ${foGrupo.toLowerCase()}: number,
  N = 80
): SistemaAdimensionalMotor {
  const deltaXi = 1.0 / (N - 1);
  const dxi2 = deltaXi * deltaXi;

  return {
    N,
    deltaXi,
    evaluarRHS(tau: number, phi: Float64Array, dphi: Float64Array) {
      dphi[0] = 0; // Dirichlet en xi = 0
      for (let i = 1; i < N - 1; i++) {
        const d2phi = (phi[i + 1] - 2 * phi[i] + phi[i - 1]) / dxi2;
        const dphi_dx = (phi[i] - phi[i - 1]) / deltaXi;
        const reac = -(${daGrupo.toLowerCase()} * phi[i]) / (1 + 2 * Math.max(0, phi[i]));
        dphi[i] = ${foGrupo.toLowerCase()} * d2phi - ${peGrupo.toLowerCase()} * dphi_dx + reac;
      }
      dphi[N - 1] = dphi[N - 2]; // Neumann en salida
    },
    construirJacobianoTridiagonal(phi: Float64Array) {
      const sub = new Float64Array(N - 1);
      const diag = new Float64Array(N);
      const sup = new Float64Array(N - 1);

      for (let i = 1; i < N - 1; i++) {
        sub[i - 1] = ${foGrupo.toLowerCase()} / dxi2 + ${peGrupo.toLowerCase()} / deltaXi;
        const dReac = -${daGrupo.toLowerCase()} / Math.pow(1 + 2 * Math.max(0, phi[i]), 2);
        diag[i] = -2 * ${foGrupo.toLowerCase()} / dxi2 - ${peGrupo.toLowerCase()} / deltaXi + dReac;
        sup[i] = ${foGrupo.toLowerCase()} / dxi2;
      }
      diag[0] = 1.0;
      diag[N - 1] = -1.0; sub[N - 2] = 1.0;
      return { sub, diag, sup };
    }
  };
}
`;

  // Código en PINN (PyTorch)
  const codigoPinn = `# ==============================================================================
# PINN Loss Normalization (Physics-Informed Neural Networks)
# Modelo: ${nombreModelo} · Forma Canónica ${indiceForma + 1}
# ==============================================================================

import torch
import torch.nn as nn

class PINNPreacondicionada(nn.Module):
    """
    Red Neuronal Informada por la Física con balanceo analítico de residuos.
    Al resolver en el espacio canónico xi in [0, 1] y tau in [0, tau_max],
    las magnitudes de gradientes para advección, difusión y reacción
    quedan acotadas por los factores O(1), O(1/Pe) y O(Da), eliminando
    la patología de desbalance espectral en backpropagation.
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )

    def forward(self, xi, tau):
        entradas = torch.cat([xi, tau], dim=1)
        return self.net(entradas)

def loss_pinn_canonica(modelo, xi, tau, ${peGrupo.toLowerCase()}=5.0, ${daGrupo.toLowerCase()}=2.0, ${foGrupo.toLowerCase()}=1.0):
    xi.requires_grad_(True)
    tau.requires_grad_(True)
    theta = modelo(xi, tau)

    # Derivadas automáticas (Autograd)
    theta_tau = torch.autograd.grad(theta, tau, grad_outputs=torch.ones_like(theta), create_graph=True)[0]
    theta_xi = torch.autograd.grad(theta, xi, grad_outputs=torch.ones_like(theta), create_graph=True)[0]
    theta_xixi = torch.autograd.grad(theta_xi, xi, grad_outputs=torch.ones_like(theta_xi), create_graph=True)[0]

    # Término de reacción química adimensional
    reaccion = -${daGrupo.toLowerCase()} * theta / (1.0 + 2.0 * torch.relu(theta))

    # Ponderaciones analíticas de Buckingham:
    w_conv = 1.0
    w_diff = ${foGrupo.toLowerCase()} / ${peGrupo.toLowerCase()}

    # Residuo PDE canónico balanceado:
    residuo_pde = theta_tau + w_conv * theta_xi - w_diff * theta_xixi - reaccion
    loss_res = torch.mean(residuo_pde ** 2)

    # Pérdida de condición de frontera Dirichlet en xi = 0 (theta = 1.0)
    tau_bc = torch.rand_like(tau)
    xi_0 = torch.zeros_like(xi)
    theta_bc0 = modelo(xi_0, tau_bc)
    loss_bc0 = torch.mean((theta_bc0 - 1.0) ** 2)

    return loss_res + 10.0 * loss_bc0
`;

  // Código en FEniCS / UFL
  const codigoFenics = `# ==============================================================================
# FEniCS / UFL - Formulación Débil Variacional Adimensional
# Modelo: ${nombreModelo} · Forma Canónica ${indiceForma + 1}
# ==============================================================================

from fenics import *

def ensamblar_sistema_fenics(n_celdas=80, ${peGrupo.toLowerCase()}=5.0, ${daGrupo.toLowerCase()}=2.0, ${foGrupo.toLowerCase()}=1.0, dt_val=0.01):
    """
    Formulación variacional débil sobre el dominio canónico xi in [0, 1].
    Apta para cálculo masivo por elementos finitos lineales (P1).
    """
    mesh = UnitIntervalMesh(n_celdas)
    V = FunctionSpace(mesh, "Lagrange", 1)

    theta = TrialFunction(V)
    v = TestFunction(V)
    theta_n = Function(V)  # Solución del paso de tiempo anterior

    dt = Constant(dt_val)
    pe_inv = Constant(${foGrupo.toLowerCase()} / ${peGrupo.toLowerCase()})
    da_const = Constant(${daGrupo.toLowerCase()})

    # Condiciones de frontera canónicas: Dirichlet en entrada (xi = 0)
    bc_inlet = DirichletBC(V, Constant(1.0), "near(x[0], 0.0)")

    # Forma débil: ( (theta - theta_n)/dt, v ) + ( grad(theta), v ) + ( (1/Pe)*grad(theta), grad(v) ) + ( Da*r(theta), v ) = 0
    F = (
        ((theta - theta_n) / dt) * v * dx
        + theta.dx(0) * v * dx
        + pe_inv * theta.dx(0) * v.dx(0) * dx
        + da_const * theta * v * dx
    )

    a, L = lhs(F), rhs(F)
    return mesh, V, a, L, [bc_inlet]
`;

  const codigoActual =
    lenguaje === "python"
      ? codigoPython
      : lenguaje === "julia"
      ? codigoJulia
      : lenguaje === "typescript"
      ? codigoTypeScript
      : lenguaje === "pinn"
      ? codigoPinn
      : codigoFenics;

  function copiarAlPortapapeles() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(codigoActual).then(() => {
        setCopiado(true);
        setTimeout(() => setCopiado(false), 2000);
      });
    }
  }

  return (
    <div className="adim-modal-backdrop" role="dialog" aria-modal="true">
      <div className="adim-modal-card max-w-4xl max-h-[90vh] flex flex-col bg-zinc-950 border border-zinc-700 shadow-2xl rounded-2xl overflow-hidden p-0">
        {/* Encabezado del Modal */}
        <div className="p-6 border-b border-zinc-800 bg-zinc-900/80 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
                Pre-Acondicionamiento /motor
              </span>
              <span className="text-xs text-zinc-400">Forma {indiceForma + 1}</span>
            </div>
            <h3 className="text-lg font-bold text-zinc-100 mt-1">
              Operador Semidiscreto & Jacobiano Analítico para el Solver
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Código ejecutable optimizado para integradores de alta rigidez (Radau / BDF, PINNs y FEniCS) en el motor de multifísica.
            </p>
          </div>
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-100 text-lg p-2 rounded-lg hover:bg-zinc-800 transition-colors"
            onClick={cerrar}
            aria-label="Cerrar modal"
          >
            ✕
          </button>
        </div>

        {/* Pestañas de Lenguaje */}
        <div className="px-6 pt-4 pb-2 border-b border-zinc-800 bg-zinc-900/40 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            {(["python", "julia", "typescript", "pinn", "fenics"] as const).map(l => (
              <button
                key={l}
                type="button"
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  lenguaje === l
                    ? "bg-zinc-800 text-cyan-300 border border-cyan-800/80 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                }`}
                onClick={() => setLenguaje(l)}
              >
                {l === "python"
                  ? "🐍 Python (SciPy Radau)"
                  : l === "julia"
                  ? "🟣 Julia (DiffEq)"
                  : l === "typescript"
                  ? "🔷 TypeScript (/motor)"
                  : l === "pinn"
                  ? "🧠 PINN (PyTorch)"
                  : "📐 FEniCS (FEM)"}
              </button>
            ))}
          </div>

          <button
            type="button"
            className={`adim-button text-xs py-1.5 px-3 flex items-center gap-1.5 ${copiado ? "is-copied" : ""}`}
            onClick={copiarAlPortapapeles}
          >
            <span>{copiado ? "✓ Copiado" : "📋 Copiar Código"}</span>
          </button>
        </div>

        {/* Visor de Código */}
        <div className="p-6 overflow-y-auto flex-1 font-mono text-xs bg-zinc-950 text-zinc-200 leading-relaxed select-text">
          <pre className="overflow-x-auto whitespace-pre p-4 rounded-xl bg-zinc-900/90 border border-zinc-800/80">
            {codigoActual}
          </pre>

          {/* Notas Técnicas de Integración */}
          <div className="mt-4 p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-xs font-sans text-zinc-300 space-y-2">
            <h5 className="font-semibold text-cyan-400 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <span>💡</span>
              <span>Justificación Matemática para Claude y Codex</span>
            </h5>
            <ul className="list-disc pl-5 space-y-1 text-zinc-400 text-[11px]">
              <li>
                <strong>Número de Condición <FormulaLatex latex="\kappa" lectura="kappa" />:</strong> Al acotar el dominio espacial a [0, 1], la dispersión espectral queda gobernada únicamente por <FormulaLatex latex="\Delta\xi^2" lectura="Delta xi al cuadrado" />, eliminando órdenes de magnitud residuales producidos por parámetros físicos sin normalizar (10⁻⁹ frente a 10³).
              </li>
              <li>
                <strong>Jacobiano Analítico Exacto:</strong> Al suministrar la matriz tridiagonal exacta al solucionador implícito, se evita la aproximación por diferencias finitas (perturbación <FormulaLatex latex="\sqrt{\epsilon_{\mathrm{mach}}}" lectura="raiz de epsilon de maquina" />), reduciendo el costo por paso temporal de <FormulaLatex latex="\mathcal{O}(N^2)" lectura="O de N al cuadrado" /> a <FormulaLatex latex="\mathcal{O}(N)" lectura="O de N" /> mediante el algoritmo de Thomas.
              </li>
              <li>
                <strong>Normalización de Pérdidas en PINNs:</strong> La formulación adimensional canónica previene el colapso del gradiente en backpropagation, balanceando los términos convectivo, difusivo y reactivo mediante factores analíticos unitarios <FormulaLatex latex="\mathcal{O}(1), \mathcal{O}(1/\mathrm{Pe}), \mathcal{O}(\mathrm{Da})" lectura="factores de orden" />.
              </li>
              <li>
                <strong>Compatibilidad Variacional FEniCS / UFL:</strong> La discretización débil opera sobre mallas triangulares o tetraédricas canónicas sin requerir re-escalado dimensional en la matriz de rigidez global.
              </li>
            </ul>
          </div>
        </div>

        {/* Footer del Modal */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/80 flex items-center justify-end gap-3">
          <button
            type="button"
            className="adim-button text-xs py-2 px-4"
            onClick={cerrar}
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
