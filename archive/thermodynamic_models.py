import numpy as np

class NRTL:
    def __init__(self, R=8.314462618):
        """
        Inicializa el modelo NRTL. 
        Asegúrate de que la constante de los gases (R) coincida con 
        las unidades de energía de la base de datos de Yaws (J/mol*K o cal/mol*K).
        """
        self.R = R

    def calcular_gamma(self, x, T, delta_g, alpha):
        """
        Calcula el vector de coeficientes de actividad usando álgebra matricial pura.
        
        Parámetros:
        x       : Array 1D de fracciones molares [N]
        T       : Escalar de temperatura en Kelvin
        delta_g : Matriz 2D (N x N) de diferencias de energía (g_ij - g_jj)
        alpha   : Matriz 2D (N x N) del parámetro de no-aleatoriedad
        
        Retorna:
        gamma   : Array 1D de coeficientes de actividad [N]
        """
        # Aseguramos que x sea un array de numpy
        x = np.asarray(x, dtype=float)
        
        # 1. Matriz de energías adimensionales (tau)
        tau = delta_g / (self.R * T)
        
        # 2. Matriz del factor de Boltzmann (G)
        # alpha * tau es un producto de Hadamard (elemento a elemento)
        G = np.exp(-alpha * tau)
        
        # 3. Vectores intermedios r y s
        # Usamos el producto punto (dot) de la transpuesta para sumar sobre j
        r = np.dot(G.T, x)
        s = np.dot((G * tau).T, x)
        
        # 4. Cálculo del término local (s/r)
        # La división es elemento a elemento
        termino_local = s / r
        
        # 5. Cálculo del término de corrección espacial
        # Separamos la sumatoria en dos productos matriciales limpios
        termino_cruzado_1 = np.dot(G * tau, x / r)
        termino_cruzado_2 = np.dot(G, x * s / (r**2))
        
        # 6. Logaritmo del coeficiente de actividad y exponencial final
        ln_gamma = termino_local + termino_cruzado_1 - termino_cruzado_2
        
        return np.exp(ln_gamma)
    import numpy as np

# (AQUÍ VA LA CLASE NRTL QUE DEFINIMOS EN EL MENSAJE ANTERIOR)

# --- PRUEBA DEL MOTOR NRTL ---
if __name__ == "__main__":
    # Instanciamos el modelo con R en J/(mol*K)
    modelo_nrtl = NRTL(R=8.31446)
    
    # Condiciones de operación
    T_operacion = 350.0 # Kelvin
    x_mezcla = np.array([0.4, 0.6]) # Fracciones molares (Deben sumar 1.0)
    
    # Matrices de parámetros (Ejemplo ficticio para un sistema binario)
    # La diagonal principal SIEMPRE debe ser 0.
    delta_g = np.array([
        [0.0,    2500.0],  # delta_g_11, delta_g_12 (J/mol)
        [1200.0, 0.0   ]   # delta_g_21, delta_g_22 (J/mol)
    ])
    
    alpha = np.array([
        [0.0, 0.3],  # alpha_11, alpha_12
        [0.3, 0.0]   # alpha_21, alpha_22
    ])
    
    # Ejecutamos el cálculo matricial
    gamma = modelo_nrtl.calcular_gamma(x_mezcla, T_operacion, delta_g, alpha)
    
    # Imprimimos resultados
    np.set_printoptions(precision=4)
    print("--- RESULTADOS PRUEBA NRTL ---")
    print(f"Temperatura: {T_operacion} K")
    print(f"Composición (x): {x_mezcla}")
    print(f"Coeficientes de Actividad (gamma): {gamma}")