import numpy as np
from scipy.optimize import fsolve
import matplotlib.pyplot as plt
import ternary
import plotly.graph_objects as go

class ThermodynamicEngine:
    def __init__(self, nu, alpha, K_R):
        self.nu = np.asarray(nu, dtype=float)
        self.alpha = np.asarray(alpha, dtype=float)
        self.K_R = float(K_R)
        
        self.nu_tot = np.sum(self.nu)
        
        if np.isclose(self.nu_tot, 0.0):
            self.is_equimolar = True
            self.x_pi = np.full_like(self.nu, np.inf)
        else:
            self.is_equimolar = False
            self.x_pi = self.nu / self.nu_tot
    
    def print_topology(self):
        print(f"Stequiometric Vector (nu): {self.nu}")
        print(f"Moles Totales (nu_tot): {self.nu_tot}")
        print(f"Polo Geométrico (x_pi): {self.x_pi}")
        print(f"¿Es Equimolar?: {self.is_equimolar}\n")
        
    def calculate_physical_jump(self, x_liquido):
        x_liquido = np.asarray(x_liquido, dtype=float)
        numerador = self.alpha * x_liquido
        denominador = np.sum(numerador)
        x_condensado = numerador / denominador
        return x_condensado
    
    def residual_quimico(self, z, x_condensado):
        x_futuro = (x_condensado + z * self.nu) / (1 + z * self.nu_tot)
        x_seguro = np.abs(x_futuro)
        
        potencias_reactivos = np.where(self.nu < 0, np.abs(self.nu), 0)
        potencias_productos = np.where(self.nu > 0, self.nu, 0)
        
        reactivos = np.prod(np.power(x_seguro, potencias_reactivos))
        productos = np.prod(np.power(x_seguro, potencias_productos))
        
        return productos - self.K_R * reactivos
        
    def calculate_chemical_jump(self, x_condensado):
        z_inicial = 0.0
        z_solucion = fsolve(self.residual_quimico, z_inicial, args=(x_condensado,))[0]
        x_final = (x_condensado + z_solucion * self.nu) / (1 + z_solucion * self.nu_tot)
        return x_final
    
    def draw_reactive_line(self, x_inicial, max_etapas=50, tolerancia=1e-6):
        k_componentes = len(x_inicial)
        trayectoria = np.zeros((max_etapas, k_componentes))
        x_actual = np.asarray(x_inicial, dtype=float)
        
        for etapa in range(max_etapas):
            trayectoria[etapa] = x_actual
            
            x_condensado = self.calculate_physical_jump(x_actual)
            x_siguiente = self.calculate_chemical_jump(x_condensado)
            
            distancia = np.linalg.norm(x_siguiente - x_actual)
            if distancia < tolerancia:
                return trayectoria[:etapa+1]
            
            x_actual = x_siguiente
            
        print("Advertencia: Se alcanzó el máximo de etapas sin converger.")
        return trayectoria

    def plot_ternary(self, n_puntos=100, max_etapas=100):
        """Genera y renderiza el mapa topológico en 2D para 3 componentes."""
        if len(self.nu) != 3:
            raise ValueError("plot_ternary solo es válido para sistemas de 3 componentes.")
            
        puntos_iniciales = np.random.dirichlet((1, 1, 1), size=n_puntos)
        
        figura, tax = ternary.figure(scale=1.0)
        figura.set_size_inches(10, 8)
        tax.boundary(linewidth=2.0)
        tax.gridlines(multiple=0.1, color="gray", linestyle="--", linewidth=0.5)
        
        # 1. Trayectorias Reactivas (Líneas Azules)
        for x_ini in puntos_iniciales:
            matriz_historial = self.draw_reactive_line(x_inicial=x_ini, max_etapas=max_etapas)
            tax.plot(matriz_historial, linewidth=1.5, color="blue", alpha=0.5)
            tax.scatter([matriz_historial[0]], marker='s', color='green', s=30, zorder=3)
            tax.scatter([matriz_historial[-1]], marker='*', color='red', s=80, zorder=3)

        # 2. Curva de Equilibrio Químico (Línea Negra)
        curva_equilibrio = []
        fracciones_A = np.linspace(0.001, 0.999, 150)
        
        for fa in fracciones_A:
            def buscar_equilibrio(fb_array):
                fb = fb_array[0]
                fc = 1.0 - fa - fb
                x_prueba = np.array([fa, fb, fc])
                x_seguro = np.abs(x_prueba)
                potencias_reactivos = np.where(self.nu < 0, np.abs(self.nu), 0)
                potencias_productos = np.where(self.nu > 0, self.nu, 0)
                reactivos = np.prod(np.power(x_seguro, potencias_reactivos))
                productos = np.prod(np.power(x_seguro, potencias_productos))
                return productos - self.K_R * reactivos

            try:
                fb_solucion = fsolve(buscar_equilibrio, 0.5)[0]
                fc_solucion = 1.0 - fa - fb_solucion
                if (0.0 <= fb_solucion <= 1.0) and (0.0 <= fc_solucion <= 1.0):
                    curva_equilibrio.append([fa, fb_solucion, fc_solucion])
            except:
                pass
                
        if curva_equilibrio:
            tax.plot(curva_equilibrio, color="black", linewidth=2.5, label="Equilibrio Químico", zorder=4)

        # 3. Líneas Estequiométricas (Punteadas Rojas)
        fracciones_base_A = np.linspace(0.05, 0.95, 12)
        for fa in fracciones_base_A:
            x_base = np.array([fa, 0.0, 1.0 - fa])
            z_valores = np.linspace(-0.5, 0.5, 200)
            linea_punteada = []
            
            for z in z_valores:
                x_z = (x_base + z * self.nu) / (1 + z * self.nu_tot)
                if np.all(x_z >= -1e-6) and np.all(x_z <= 1 + 1e-6):
                    linea_punteada.append(x_z)
                    
            if len(linea_punteada) > 1:
                tax.plot(linea_punteada, color="red", linestyle=":", linewidth=2, alpha=0.6)
                
        tax.right_corner_label("Comp. A (Volátil)", fontsize=12)
        tax.top_corner_label("Comp. B", fontsize=12)
        tax.left_corner_label("Comp. C (Pesado)", fontsize=12)
        tax.get_axes().axis('off')
        tax.clear_matplotlib_ticks()
        plt.title(f"Topología de Destilación Reactiva ({n_puntos} Líneas)", fontsize=14)
        plt.show()

    def plot_quaternary(self, n_puntos=150, max_etapas=150):
        """Genera y renderiza el gemelo digital en 3D para 4 componentes usando GPU/Plotly."""
        if len(self.nu) != 4:
            raise ValueError("plot_quaternary solo es válido para sistemas de 4 componentes.")
            
        # Geometría y Proyección Interna
        V_a = np.array([0.0, 0.0, 0.0])
        V_b = np.array([1.0, 0.0, 0.0])
        V_c = np.array([0.5, np.sqrt(3)/2, 0.0])
        V_d = np.array([0.5, np.sqrt(3)/6, np.sqrt(6)/3])
        matriz_vertices = np.vstack((V_a, V_b, V_c, V_d))

        def proyectar_a_3D(matriz_fracciones):
            return np.dot(matriz_fracciones, matriz_vertices)

        figura_3d = go.Figure()

        # 1. Aristas y Etiquetas
        aristas = [(V_a, V_b), (V_b, V_c), (V_c, V_a), (V_a, V_d), (V_b, V_d), (V_c, V_d)]
        for p1, p2 in aristas:
            figura_3d.add_trace(go.Scatter3d(
                x=[p1[0], p2[0]], y=[p1[1], p2[1]], z=[p1[2], p2[2]],
                mode='lines', line=dict(color='black', width=4),
                showlegend=False, hoverinfo='skip'
            ))

        etiquetas_vertices = ["Comp. A", "Comp. B", "Comp. C", "Comp. D"]
        coords_vertices = [V_a, V_b, V_c, V_d]
        for coord, texto in zip(coords_vertices, etiquetas_vertices):
            figura_3d.add_trace(go.Scatter3d(
                x=[coord[0]], y=[coord[1]], z=[coord[2]],
                mode='text', text=[texto], textposition="top center",
                showlegend=False
            ))

        # 2. Trayectorias Reactivas (Líneas Azules)
        puntos_iniciales = np.random.dirichlet((1, 1, 1, 1), size=n_puntos)
        
        for x_ini in puntos_iniciales:
            historial_4D = self.draw_reactive_line(x_inicial=x_ini, max_etapas=max_etapas)
            historial_3D = proyectar_a_3D(historial_4D)
            X, Y, Z = historial_3D[:, 0], historial_3D[:, 1], historial_3D[:, 2]
            
            figura_3d.add_trace(go.Scatter3d(
                x=X, y=Y, z=Z, mode='lines',
                line=dict(color='blue', width=2), opacity=0.6, showlegend=False
            ))
            figura_3d.add_trace(go.Scatter3d(
                x=[X[0], X[-1]], y=[Y[0], Y[-1]], z=[Z[0], Z[-1]],
                mode='markers',
                marker=dict(color=['green', 'red'], size=[3, 6], symbol=['square', 'diamond']),
                showlegend=False
            ))

        # 3. Líneas Estequiométricas y Polo (Equimolar vs No Equimolar)
        if not self.is_equimolar:
            polo_4D = np.array([self.x_pi])
            polo_3D = proyectar_a_3D(polo_4D)[0]
            
            figura_3d.add_trace(go.Scatter3d(
                x=[polo_3D[0]], y=[polo_3D[1]], z=[polo_3D[2]],
                mode='markers+text',
                marker=dict(color='black', size=6, symbol='circle-open'),
                text=['π (Polo Geométrico)'], textposition="top right", showlegend=False
            ))
            
            for x_ini in puntos_iniciales:
                punto_ini_3D = proyectar_a_3D(np.array([x_ini]))[0]
                figura_3d.add_trace(go.Scatter3d(
                    x=[punto_ini_3D[0], polo_3D[0]], 
                    y=[punto_ini_3D[1], polo_3D[1]], 
                    z=[punto_ini_3D[2], polo_3D[2]],
                    mode='lines', line=dict(color='gray', width=1.5, dash='dot'),
                    opacity=0.4, showlegend=False
                ))
        else:
            for x_ini in puntos_iniciales:
                # Cálculo de límites universales para sistemas equimolares
                z_max = min([x_ini[i]/abs(self.nu[i]) if self.nu[i] < 0 else np.inf for i in range(4)])
                z_min = max([-x_ini[i]/self.nu[i] if self.nu[i] > 0 else -np.inf for i in range(4)])
                
                ext_1 = x_ini + z_min * self.nu
                ext_2 = x_ini + z_max * self.nu
                segmento_3D = proyectar_a_3D(np.array([ext_1, ext_2]))
                
                figura_3d.add_trace(go.Scatter3d(
                    x=segmento_3D[:, 0], y=segmento_3D[:, 1], z=segmento_3D[:, 2],
                    mode='lines', line=dict(color='red', width=2, dash='dot'),
                    opacity=0.4, showlegend=False
                ))

        figura_3d.update_layout(
            scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
            margin=dict(l=0, r=0, b=0, t=30),
            title="Gemelo Digital 3D de Destilación Reactiva"
        )
        figura_3d.show()


# =============================================================================================
# BLOQUE DE EJECUCIÓN LIMPIO
# =============================================================================================

if __name__ == "__main__":
    # --- PRUEBA TERNARIA (2D) ---
    print("Iniciando simulación del Sistema Ternario (2D)...")
    sistema_1 = ThermodynamicEngine(nu=[-1, -2, 1], alpha=[3, 2, 1], K_R=4)
    sistema_1.print_topology()
    sistema_1.plot_ternary(n_puntos=100)

    # --- PRUEBA CUATERNARIA NO EQUIMOLAR (3D Cónica) ---
    print("Iniciando simulación del Sistema Cuaternario No Equimolar (3D)...")
    sistema_3 = ThermodynamicEngine(nu=[-1, 2, 2, 1], alpha=[1, 4, 3, 2], K_R=2)
    sistema_3.print_topology()
    sistema_3.plot_quaternary(n_puntos=100)