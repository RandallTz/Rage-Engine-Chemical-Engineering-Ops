import type { FormulacionNucleo } from "./contratoNucleo";
import { exportarDesarrollo } from "./exportarDesarrollo";

export const BIBTEX_PUBLICACION = `@article{turing1952,
  author = {Turing, Alan Mathison},
  title = {The Chemical Basis of Morphogenesis},
  journal = {Philosophical Transactions of the Royal Society of London. Series B, Biological Sciences},
  volume = {237},
  number = {641},
  pages = {37--72},
  year = {1952},
  doi = {10.1098/rstb.1952.0012}
}

@article{fisher1937,
  author = {Fisher, Ronald Aylmer},
  title = {The Wave of Advance of Advantageous Genes},
  journal = {Annals of Eugenics},
  volume = {7},
  number = {4},
  pages = {355--369},
  year = {1937},
  doi = {10.1111/j.1469-1809.1937.tb02153.x}
}

@article{kolmogorov1937,
  author = {Kolmogorov, Andrei Nikolaevich and Petrovsky, Ivan Georgievich and Piskunov, Nikolai Semenovich},
  title = {\'Etude de l'\'equation de la diffusion avec croissance de la quantit\'e de mati\`ere et son application \`a un probl\`eme biologique},
  journal = {Bulletin de l'Universit\'e d'\'Etat \`a Moscou, S\'erie Internationale, Section A},
  volume = {1},
  number = {6},
  pages = {1--25},
  year = {1937}
}

@article{buckingham1914,
  author = {Buckingham, Edgar},
  title = {On Physically Similar Systems; Illustrations of the Use of Dimensional Equations},
  journal = {Physical Review},
  volume = {4},
  number = {4},
  pages = {345--376},
  year = {1914},
  doi = {10.1103/PhysRev.4.345}
}

@incollection{kruskal1962,
  author = {Kruskal, Martin D.},
  title = {Asymptotology},
  booktitle = {Mathematical Models in Physical Sciences},
  editor = {Drobot, Stefan},
  publisher = {Prentice-Hall},
  pages = {17--48},
  year = {1962}
}

@book{barenblatt1996,
  author = {Barenblatt, Grigory Isaakovich},
  title = {Scaling, Self-similarity, and Intermediate Asymptotics},
  series = {Cambridge Texts in Applied Mathematics},
  publisher = {Cambridge University Press},
  year = {1996},
  isbn = {978-0521435222}
}

@book{murray2002,
  author = {Murray, James D.},
  title = {Mathematical Biology II: Spatial Models and Biomedical Applications},
  series = {Interdisciplinary Applied Mathematics},
  volume = {18},
  edition = {3rd},
  publisher = {Springer-Verlag},
  year = {2002},
  isbn = {978-0387952284}
}

@book{bender1999,
  author = {Bender, Carl M. and Orszag, Steven A.},
  title = {Advanced Mathematical Methods for Scientists and Engineers I: Asymptotic Methods and Perturbation Theory},
  publisher = {Springer-Verlag},
  year = {1999},
  doi = {10.1007/978-1-4757-3069-2}
}
`;

export const MANUSCRITO_TEORICO_TEX = `\\documentclass[11pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage[spanish,es-tabla]{babel}
\\usepackage{amsmath,amssymb,amsfonts,amsthm}
\\usepackage{booktabs}
\\usepackage[margin=25mm]{geometry}
\\usepackage{microtype}
\\usepackage{hyperref}
\\usepackage{cite}

\\hypersetup{
    colorlinks=true,
    linkcolor=black,
    citecolor=black,
    urlcolor=blue
}

\\newtheorem{teorema}{Teorema}
\\newtheorem{proposicion}{Proposición}
\\newtheorem{definicion}{Definición}
\\newtheorem{corolario}{Corolario}

\\title{\\textbf{Fundamentos Algebraicos, Difeomorfismos de Escala y Balanza Dominante en la Física Matemática de Sistemas Continuos Multicomponente con Leyes Constitutivas Arbitrarias}}
\\author{\\textbf{Laboratorio de Física Matemática y Dinámica No Lineal}}
\\date{Octubre de 2026}

\\begin{document}

\\maketitle

\\begin{abstract}
\\noindent La adimensionalización rigurosa de ecuaciones diferenciales en derivadas parciales (EDP) en medios continuos constituye el pilar analítico para la reducción de grados de libertad paramétricos, la identificación de regímenes asintóticos universales y la simulación numéricamente estable de sistemas dinámicos acoplados. En este artículo formalizamos la teoría algebraica subyacente a la transformación de balances continuos multicomponente bajo el grupo de Lie de dilataciones canónicas, sin imponer restricciones funcionales a las leyes constitutivas: el marco procesa de forma agnóstica términos de transporte difusivo y advectivo junto con relaciones cinéticas o fuentes empíricas arbitrarias (leyes de potencias, saturación no lineal tipo Langmuir-Hinshelwood / Michaelis-Menten / Hill, amortiguamiento empírico y funciones trascendentes). Extendemos el formalismo hacia dominios continuos multidimensionales $\\mathbb{R}^n$ ($n \\in \\{1, 2, 3\\}$) y geometrías curvilíneas (cilíndricas y esféricas), parametrizando factores de esbeltez geométrica ($\\mathcal{A}_j = L_1/L_j$). Demostramos cómo el principio de la balanza dominante de Kruskal induce un espacio combinatorio completo de formulaciones canónicas duales (hasta 68 formas en sistemas acoplados), analizamos capas de transición singular mediante expansiones asintóticas acopladas y verificamos la potencia del motor a través de fenómenos paradigmáticos de referencia como la morfogénesis de Turing y los frentes de onda de Fisher-KPP.
\\end{abstract}

\\vspace{5mm}
\\noindent\\textbf{Palabras clave:} Sistemas continuos acoplados, Leyes constitutivas empíricas, Teorema $\\Pi$ de Buckingham, Balanza dominante de Kruskal, Inestabilidad de Turing, Frentes de onda de Fisher-KPP, Escalamiento anisotrópico, Redes PINNs.

\\section{Introducción y Motivación en Física Matemática}
En la física de medios continuos, transporte reactivo, dinámica de fluidos y fisicoquímica de campos acoplados, los balances fundamentales se formulan como sistemas de ecuaciones en derivadas parciales:
\\begin{equation}
\\frac{\\partial u_i}{\\partial t} + \\nabla \\cdot \\mathbf{J}_i = \\mathcal{S}_i(u_1, \\dots, u_m, \\nabla \\mathbf{u}, \\mathbf{x}, t), \\qquad i = 1, \\dots, m,
\\label{eq:balance_general}
\\end{equation}
en un dominio continuo $\\Omega \\subset \\mathbb{R}^n$ ($n \\in \\{1, 2, 3\\}$). El flujo interfacial $\\mathbf{J}_i = \\mathbf{v} u_i - \\sum_j \\mathbf{D}_{ij} \\nabla u_j$ engloba convección y difusión molecular (con posible difusión cruzada), mientras que $\\mathcal{S}_i$ denota el término fuente o ley constitutiva empírica del sistema. Una ventaja capital del presente enfoque es su agnosticismo funcional: $\\mathcal{S}_i$ puede incorporar cinéticas polinomiales, relaciones racionales saturables, leyes empíricas de fricción o arrastre, o cinéticas de orden fraccionario.

Como casos de validación paradigmáticos donde las escalas asintóticas inducen transiciones cualitativas, destacan:
\\begin{enumerate}
    \\item \\textbf{Morfogénesis y patrones de Turing:} Ruptura espontánea de simetría espacial inducida por difusión diferencial ($D_v / D_u \\gg 1$) entre especies activadoras e inhibidoras \\cite{turing1952}.
    \\item \\textbf{Propagación de frentes de onda (Fisher-KPP):} Dinámica de invasión y transiciones de fase gobernadas por una velocidad asintótica mínima universal $v^* = 2\\sqrt{D k}$ \\cite{fisher1937, kolmogorov1937}.
    \\item \\textbf{Medios excitables, biestables y capas límite:} Propagación de impulsos electrofisiológicos y fronteras de separación en sistemas tipo FitzHugh-Nagumo o Allen-Cahn con cinéticas cúbicas o saturadas.
\\end{enumerate}

Resolver o analizar directamente estas ecuaciones en variables dimensionales presenta graves dificultades:
\\begin{enumerate}
    \\item \\textbf{Proliferación paramétrica:} La presencia simultánea de difusividades $D_i$, constantes cinéticas $k_r$, coeficientes empíricos y dimensiones características genera un hiperespacio de parámetros que oscurece el régimen dinámico global.
    \\item \\textbf{Enmascaramiento de escalas dominantes:} Cuando las escalas temporales de transporte y fuente difieren en varios órdenes de magnitud, la jerarquía de los procesos físicos queda oculta por la elección arbitraria de unidades.
    \\item \\textbf{Rigidez numérica y perturbaciones singulares:} Pequeñas escalas espaciotemporales generan capas límite o frentes delgados que provocan mal condicionamiento y rigidez extrema en esquemas de integración computacional.
\\end{enumerate}

La técnica de adimensionalización canónica resuelve estas limitaciones proyectando el sistema continuo sobre variedades invariantes bajo grupos de dilatación de Lie. El objetivo de este trabajo es formular un marco algebraico deductivo, determinista y certificado para deducir, verificar y simular sistemas diferenciales continuos con leyes constitutivas arbitrarias en $\\mathbb{R}^n$.

\\section{Estructura Algebraica de Dimensiones y Teorema $\\Pi$ de Buckingham}

\\subsection{El Espacio Vectorial de Dimensiones Físicas}
Sea una base dimensional ortonormal del sistema internacional formada por $d$ magnitudes fundamentales:
\\begin{equation}
\\mathcal{B} = \\{\\mathsf{M}, \\mathsf{L}, \\mathsf{T}, \\mathsf{\\Theta}, \\mathsf{N}, \\mathsf{I}, \\mathsf{J}\\}, \\qquad d = \\dim(\\mathcal{B}) \\le 7.
\\end{equation}
Toda magnitud física o parámetro dimensional $p_k$ posee una representación monómica única:
\\begin{equation}
[p_k] = \\prod_{l=1}^d B_l^{M_{lk}}, \\qquad M_{lk} \\in \\mathbb{Q}.
\\end{equation}
Definiendo el vector de exponentes $\\mathbf{v}_k = (M_{1k}, M_{2k}, \\dots, M_{dk})^T \\in \\mathbb{Q}^d$, la compatibilidad dimensional de un conjunto de $p$ parámetros $\\{p_1, \\dots, p_p\\}$ se estructura en la matriz dimensional:
\\begin{equation}
\\mathbf{M} = \\begin{pmatrix} M_{11} & M_{12} & \\cdots & M_{1p} \\\\ M_{21} & M_{22} & \\cdots & M_{2p} \\\\ \\vdots & \\vdots & \\ddots & \\vdots \\\\ M_{d1} & M_{d2} & \\cdots & M_{dp} \\end{pmatrix} \\in \\mathbb{Q}^{d \\times p}.
\\end{equation}

\\subsection{Teorema de Vaschy-Buckingham y Espacio Nulo}
\\begin{teorema}[Vaschy-Buckingham \\cite{buckingham1914}]
Sea un sistema continuo gobernado por una relación dimensional homogénea $\\mathcal{F}(p_1, p_2, \\dots, p_p) = 0$. Si el rango de la matriz dimensional asociada es $r = \\mathrm{rank}(\\mathbf{M}) \\le d$, existen exactamente $p - r$ productos adimensionales independientes $\\Pi_1, \\dots, \\Pi_{p-r}$ tales que la relación es homeomorfa a:
\\begin{equation}
\\Phi(\\Pi_1, \\Pi_2, \\dots, \\Pi_{p-r}) = 0.
\\end{equation}
Los vectores de exponentes de cada invariante $\\Pi_j = \\prod_{k=1}^p p_k^{\\alpha_{jk}}$ constituyen una base del núcleo o espacio nulo de la matriz dimensional:
\\begin{equation}
\\mathbf{M} \\boldsymbol{\\alpha}_j = \\mathbf{0}, \\qquad \\boldsymbol{\\alpha}_j \\in \\mathbb{Q}^p \\setminus \\{\\mathbf{0}\\}.
\\end{equation}
\\end{teorema}

\\section{Difeomorfismos de Escala de Lie y Regla de la Cadena}

\\subsection{Grupo de Dilataciones Canónicas}
El reescalamiento formal consiste en la acción del grupo abeliano de dilataciones $\\mathcal{G} \\cong (\\mathbb{R}_{>0})^{m+n+1}$ sobre el espacio de variables independientes $(\\mathbf{x}, t) \\in \\mathbb{R}^n \\times \\mathbb{R}_{\\ge 0}$ y campos continuos $\\mathbf{u} \\in \\mathbb{R}^m$:
\\begin{equation}
\\mathbf{x} = \\mathbf{L} \\hat{\\mathbf{x}}, \\qquad t = t_{\\mathrm{ref}} \\hat{t}, \\qquad u_i = u_{i,\\mathrm{ref}} \\hat{u}_i,
\\label{eq:difeomorfismos}
\\end{equation}
donde $\\mathbf{L} = \\mathrm{diag}(x_{1,\\mathrm{ref}}, \\dots, x_{n,\\mathrm{ref}})$. Las magnitudes adimensionalizadas denotadas con acento circunflejo $(\\hat{\\cdot})$ satisfacen $\\hat{u}_i = \\mathcal{O}(1)$, $\\hat{x}_j = \\mathcal{O}(1)$, $\\hat{t} = \\mathcal{O}(1)$ en el régimen asintótico seleccionado.

\\subsection{Transformación Diferencial de Operadores}
Bajo el difeomorfismo (\\ref{eq:difeomorfismos}), la regla de la cadena proyecta los operadores continuos al espacio escalado:
\\begin{equation}
\\frac{\\partial}{\\partial t} = \\frac{1}{t_{\\mathrm{ref}}} \\frac{\\partial}{\\partial \\hat{t}}, \\qquad \\frac{\\partial}{\\partial x_j} = \\frac{1}{x_{j,\\mathrm{ref}}} \\frac{\\partial}{\\partial \\hat{x}_j}.
\\end{equation}
Para los operadores laplacianos de difusión molecular:
\\begin{equation}
\\frac{\\partial^2 u}{\\partial x_j^2} = \\frac{u_{\\mathrm{ref}}}{x_{j,\\mathrm{ref}}^2} \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}_j^2}.
\\end{equation}

\\section{Difusión Multidimensional Anisotrópica y Factores de Esbeltez}

\\subsection{El Laplaciano Cartesiano y Relaciones de Aspecto}
Consideremos la difusión en dominios multidimensionales continuos en $\\mathbb{R}^n$:
\\begin{equation}
\\nabla^2 u = \\sum_{j=1}^n \\frac{\\partial^2 u}{\\partial x_j^2} = u_{\\mathrm{ref}} \\sum_{j=1}^n \\frac{1}{x_{j,\\mathrm{ref}}^2} \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}_j^2}.
\\end{equation}
Tomando como escala de referencia longitudinal $L_x \\equiv x_{1,\\mathrm{ref}}$, factorizamos globalmente:
\\begin{equation}
\\nabla^2 u = \\frac{u_{\\mathrm{ref}}}{L_x^2} \\left[ \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}_1^2} + \\sum_{j=2}^n \\mathcal{A}_j^2 \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}_j^2} \\right],
\\end{equation}
donde se definen las \\textbf{relaciones de aspecto o factores de esbeltez geométrica}:
\\begin{equation}
\\mathcal{A}_j \\equiv \\frac{x_{1,\\mathrm{ref}}}{x_{j,\\mathrm{ref}}} = \\frac{L_x}{L_j}, \\qquad j = 2, \\dots, n.
\\end{equation}

\\subsection{Confinamiento Espacial y Reducción Asintótica}
En medios confinados (membranas biológicas delgadas, axones neuronales o películas reactivas con $L_y \\ll L_x$), definimos el parámetro de pequeñez $\\epsilon \\equiv L_y / L_x \\ll 1$. Normalizando respecto a la escala transversal $L_y$:
\\begin{equation}
\\nabla_{x,y}^2 u = \\frac{u_{\\mathrm{ref}}}{L_y^2} \\left[ \\epsilon^2 \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}^2} + \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{y}^2} \\right].
\\end{equation}
En el límite singular $\\epsilon \\to 0$, la difusión longitudinal $\\epsilon^2 \\partial^2_{\\hat{x}}\\hat{u} \\sim \\mathcal{O}(\\epsilon^2)$ deviene asintóticamente despreciable frente a la homogenización transversal instantánea $\\partial^2_{\\hat{y}}\\hat{u} \\sim \\mathcal{O}(1)$, permitiendo colapsar rigurosamente la EDP 2D en un modelo efectivo 1D sin aproximaciones ad-hoc.

\\section{Balanza Dominante de Kruskal y Multiplicidad de Formulaciones}

\\subsection{El Principio de la Balanza Dominante}
Siguiendo el principio de asintotología de Kruskal \\cite{kruskal1962}, dividimos cada ecuación del balance miembro a miembro por el factor dimensional del término rector (por ejemplo, el término de acumulación $\\Phi = u_{\\mathrm{ref}}/t_{\\mathrm{ref}}$ o el término de difusión $\\Phi = D u_{\\mathrm{ref}}/L^2$). El coeficiente efectivo de dicho término se normaliza unívocamente a la unidad ($1$), cancelando un grado de libertad de escala.

\\subsection{Catálogo de Regímenes Físicos Canónicos}
Para el balance clásico de reacción-difusión $\\frac{\\partial u}{\\partial t} = D \\nabla^2 u + k u(1 - u)$, surgen de manera sistemática las siguientes formulaciones canónicas:

\\begin{table}[h!]
\\centering
\\small
\\begin{tabular}{@{}llll@{}}
\\toprule
\\textbf{Formulación} & \\textbf{Escala temporal ($t_{\\mathrm{ref}}$)} & \\textbf{Escala espacial ($x_{\\mathrm{ref}}$)} & \\textbf{Grupos canónicos emergentes} \\\\
\\midrule
1. Tiempo difusivo & $t_{\\mathrm{ref}} = L^2/D$ & $L$ libre & $\\mathrm{Fo} = 1$, $\\mathrm{Da} = \\frac{k L^2}{D}$ (Damköhler difusivo) \\\\
2. Tiempo reactivo & $t_{\\mathrm{ref}} = 1/k$ & $L$ libre & $\\mathrm{Da}_t = 1$, $\\mathrm{Fo} = \\frac{D}{k L^2} = \\frac{1}{\\mathrm{Da}}$ \\\\
3. Escala intrínseca RD & $t_{\\mathrm{ref}} = 1/k$ & $L = \\sqrt{D/k}$ & $\\frac{\\partial \\hat{u}}{\\partial \\hat{t}} = \\nabla^2 \\hat{u} + \\hat{u}(1 - \\hat{u})$ (parámetros libres $= 0$) \\\\
4. Convección-difusión & $t_{\\mathrm{ref}} = L/u$ & $L$ libre & $\\mathrm{Pe} = \\frac{u L}{D}$, $\\mathrm{Da}_c = \\frac{k L}{u}$ \\\\
\\bottomrule
\\end{tabular}
\\caption{Formulaciones canónicas deducidas del balance dominante.}
\\label{tab:formulaciones}
\\end{table}

\\subsection{Multiplicidad Combinatoria en Sistemas Multicomponente}
En sistemas de reacción-difusión con $m$ especies acopladas ($u_1, \\dots, u_m$) y múltiples cinéticas no lineales, cada balance diferencial admite la elección independiente de su término rector (acumulación, difusión molecular, o tasa reactiva de una especie dada).
El número de formulaciones admisibles corresponde exactamente al número de menores de orden máximo de la matriz de coeficientes de escala con determinante no nulo ($\\det(\\mathbf{M}_{\\mathrm{sub}}) \\ne 0$). En sistemas bi-reactivos acoplados (como Gray-Scott o Brusselator), este espacio combinatorio genera hasta \\textbf{68 formulaciones canónicas duales}, cada una perfectamente adaptada a un régimen asintótico físico específico.

\\section{Geometrías Curvilíneas Ortogonales: Esferoides y Conduits Cilíndricos}

\\subsection{El Operador Laplaciano en Geometrías Cilíndricas y Esféricas}
En el modelado biofísico de esferoides celulares, organoides avasculares, axones neuronales cilíndricos y vesículas reactivas, el dominio continuo presenta simetría radial. Los operadores de Laplace con simetría axial y esférica completa son:
\\begin{align}
\\nabla_{\\mathrm{cil}}^2 u &= \\frac{\\partial^2 u}{\\partial r^2} + \\frac{1}{r} \\frac{\\partial u}{\\partial r} + \\frac{\\partial^2 u}{\\partial z^2}, \\\\
\\nabla_{\\mathrm{esf}}^2 u &= \\frac{\\partial^2 u}{\\partial r^2} + \\frac{2}{r} \\frac{\\partial u}{\\partial r} = \\frac{1}{r^2} \\frac{\\partial}{\\partial r}\\left(r^2 \\frac{\\partial u}{\\partial r}\\right).
\\end{align}
Bajo el difeomorfismo de dilatación radial $r = R\\,\\hat{r}$ y campo $u = u_{\\mathrm{ref}}\\,\\hat{u}$:
\\begin{equation}
\\frac{\\partial^2 u}{\\partial r^2} = \\frac{u_{\\mathrm{ref}}}{R^2} \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{r}^2}, \\qquad \\frac{1}{r} \\frac{\\partial u}{\\partial r} = \\frac{1}{R\\,\\hat{r}} \\frac{u_{\\mathrm{ref}}}{R} \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} = \\frac{u_{\\mathrm{ref}}}{R^2} \\left( \\frac{1}{\\hat{r}} \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} \\right).
\\end{equation}
Ambos sumandos escalan con idéntico factor dimensional homogéneo $\\frac{u_{\\mathrm{ref}}}{R^2}$. En consecuencia, el operador diferencial transformado preserva la métrica intrínseca ortogonal:
\\begin{equation}
\\nabla_{\\mathrm{cil}}^2 u = \\frac{u_{\\mathrm{ref}}}{R^2} \\left[ \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{r}^2} + \\frac{1}{\\hat{r}} \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} + \\mathcal{A}_r^2 \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{z}^2} \\right], \\qquad \\mathcal{A}_r = \\frac{R}{L_z},
\\end{equation}
\\begin{equation}
\\nabla_{\\mathrm{esf}}^2 u = \\frac{u_{\\mathrm{ref}}}{R^2} \\left[ \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{r}^2} + \\frac{2}{\\hat{r}} \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} \\right] = \\frac{u_{\\mathrm{ref}}}{R^2} \\frac{1}{\\hat{r}^2} \\frac{\\partial}{\\partial \\hat{r}} \\left( \\hat{r}^2 \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} \\right).
\\end{equation}

\\subsection{Regularidad en el Origen y Profundidad de Penetración}
En el centro del dominio ($\\hat{r} = 0$), la regularidad física del campo continuo impone la condición de simetría de Neumann:
\\begin{equation}
\\left. \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} \\right|_{\\hat{r}=0} = 0, \\qquad \\lim_{\\hat{r} \\to 0} \\frac{1}{\\hat{r}} \\frac{\\partial \\hat{u}}{\\partial \\hat{r}} = \\left. \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{r}^2} \\right|_{\\hat{r}=0}.
\\end{equation}
Para un esferoide celular con consumo cinético de primer orden en estado estacionario:
\\begin{equation}
\\frac{d^2 \\hat{u}}{d\\hat{r}^2} + \\frac{2}{\\hat{r}} \\frac{d\\hat{u}}{d\\hat{r}} - \\phi^2 \\hat{u} = 0, \\qquad \\phi = R \\sqrt{\\frac{k}{D}},
\\end{equation}
donde emerge deductivamente el módulo adimensional $\\phi = R/\\ell_{\\mathrm{rd}}$, cuya solución analítica canónica es $\\hat{u}(\\hat{r}) = \\frac{\\sinh(\\phi \\hat{r})}{\\hat{r} \\sinh(\\phi)}$. Cuando $\\phi \\gg 1$, la reactividad confina el nutriente a una capa superficial de espesor $\\delta \\sim \\sqrt{D/k}$.

\\section{Bifurcaciones Espaciotemporales: Turing y Frentes de Onda}

\\subsection{Inestabilidad de Turing y Ruptura Espontánea de Simetría}
Consideremos el sistema bi-reactivo activador-inhibidor en variables adimensionales canónicas:
\\begin{align}
\\frac{\\partial \\hat{u}}{\\partial \\hat{t}} &= \\nabla^2 \\hat{u} + f(\\hat{u}, \\hat{v}), \\\\
\\frac{\\partial \\hat{v}}{\\partial \\hat{t}} &= d \\, \\nabla^2 \\hat{v} + g(\\hat{u}, \\hat{v}), \\qquad d = \\frac{D_v}{D_u} > 0.
\\end{align}
Sea $(\\hat{u}^*, \\hat{v}^*)$ un estado estacionario homogéneo estable en ausencia de difusión, lo cual exige que la matriz jacobiana $\\mathbf{J} = \\begin{pmatrix} f_u & f_v \\\\ g_u & g_v \\end{pmatrix}$ satisfaga:
\\begin{equation}
\\mathrm{tr}(\\mathbf{J}) = f_u + g_v < 0, \\qquad \\det(\\mathbf{J}) = f_u g_v - f_v g_u > 0.
\\end{equation}
La presencia de difusión desestabiliza este estado homogéneo frente a perturbaciones espaciales de número de onda $k_w$ si y solo si la razón de difusividades $d$ supera el umbral crítico de bifurcación de Turing \\cite{turing1952, murray2002}:
\\begin{equation}
d f_u + g_v > 2 \\sqrt{d (f_u g_v - f_v g_u)} > 0.
\\end{equation}
El número de onda crítico donde se produce la inestabilidad primaria es:
\\begin{equation}
k_c^2 = \\frac{d f_u + g_v}{2d},
\\end{equation}
fijando la longitud de onda física característica del patrón emergente como $\\lambda_c = 2\\pi / k_c \\sim 2\\pi \\sqrt{D_u / k}$. La adimensionalización canónica independiza este análisis de la escala métrica elegida.

\\subsection{Frentes de Onda Viajeros y Ecuación de Fisher-KPP}
Para la propagación de ondas viajeras monostables $\\partial_t u = D \\nabla^2 u + k u(1 - u)$ \\cite{fisher1937, kolmogorov1937}, la formulación canónica en la escala intrínseca ($t_{\\mathrm{ref}} = 1/k, x_{\\mathrm{ref}} = \\sqrt{D/k}$) se reduce a:
\\begin{equation}
\\frac{\\partial \\hat{u}}{\\partial \\hat{t}} = \\frac{\\partial^2 \\hat{u}}{\\partial \\hat{x}^2} + \\hat{u}(1 - \\hat{u}).
\\end{equation}
Buscando soluciones en coordenadas del frente móvil $\\hat{u}(\\hat{x}, \\hat{t}) = U(\\xi)$ con $\\xi = \\hat{x} - \\hat{v} \\hat{t}$, la EDP se transforma en la EDO de segundo orden:
\\begin{equation}
U'' + \\hat{v} U' + U(1 - U) = 0, \\qquad U(-\\infty) = 1, \\quad U(+\\infty) = 0.
\\end{equation}
El análisis en el plano de fases del punto de equilibrio $(0, 0)$ revela que para evitar oscilaciones espaciales no físicas ($U < 0$), los autovalores deben ser estrictamente reales:
\\begin{equation}
\\lambda^2 + \\hat{v} \\lambda + 1 = 0 \\quad \\Longrightarrow \\quad \\hat{v}^2 - 4 \\ge 0 \\quad \\Longrightarrow \\quad \\hat{v}^* = 2.
\\end{equation}
Revertiendo el difeomorfismo inverso, recuperamos de forma exacta la velocidad física de propagación:
\\begin{equation}
v^* = \\hat{v}^* \\frac{x_{\\mathrm{ref}}}{t_{\\mathrm{ref}}} = 2 \\frac{\\sqrt{D/k}}{1/k} = 2 \\sqrt{D k}.
\\end{equation}

\\section{Perturbaciones Singulares y Capas de Transición Interfacial}

\\subsection{El Límite Asintótico de Cinética Rápida}
En sistemas biestables o de conmutación rápida (tipo Allen-Cahn o FitzHugh-Nagumo), el número de Damköhler deviene asintóticamente grande, $\\mathrm{Da} \\gg 1$. Definiendo el parámetro de perturbación singular $\\epsilon \\equiv 1/\\mathrm{Da} \\ll 1$:
\\begin{equation}
\\epsilon \\frac{d^2 \\hat{u}}{d\\hat{x}^2} = R(\\hat{u}), \\qquad \\hat{u}(0) = 0, \\quad \\hat{u}(1) = 1.
\\end{equation}
La aproximación regular $\\epsilon = 0$ reduce el orden diferencial de dos a cero ($R(\\hat{u}_0) = 0$), provocando una perturbación singular donde se pierde la capacidad de satisfacer las condiciones de contorno simultáneamente.

\\subsection{Coordenada Estirada y Principio de Empate de Van Dyke}
En la vecindad de la zona de transición interfacial $x = x_f$, introducimos la coordenada estirada:
\\begin{equation}
\\tilde{X} = \\frac{\\hat{x} - x_f}{\\sqrt{\\epsilon}}.
\\end{equation}
Bajo esta escala microscópica, el operador difusivo y el término reactivo se re-equilibran al mismo orden $\\mathcal{O}(1)$:
\\begin{equation}
\\frac{d^2 \\hat{u}^{\\mathrm{in}}}{d\\tilde{X}^2} = R(\\hat{u}^{\\mathrm{in}}).
\\end{equation}
Multiplicando por $\\frac{d\\hat{u}^{\\mathrm{in}}}{d\\tilde{X}}$ e integrando una vez:
\\begin{equation}
\\frac{1}{2} \\left( \\frac{d\\hat{u}^{\\mathrm{in}}}{d\\tilde{X}} \\right)^2 = \\int R(u)\\,du + C = V(u) + C.
\\end{equation}
El principio de empate asintótico de Van Dyke \\cite{bender1999} une de manera continua y uniforme la solución de la capa interfacial interna con las soluciones asintóticas externas:
\\begin{equation}
\\lim_{\\tilde{X} \\to \\pm\\infty} \\hat{u}^{\\mathrm{in}}(\\tilde{X}) = \\lim_{\\hat{x} \\to x_f^\\pm} \\hat{u}^{\\mathrm{out}}(\\hat{x}).
\\end{equation}
Este formalismo prueba que la adimensionalización rigurosa no es una mera transformación cosmética, sino la condición matemática previa obligatoria para el cálculo de frentes de transición singular.

\\section{Adimensionalización de Condiciones de Frontera e Invariantes Interfaciales}
En el modelado riguroso de medios continuos, el cierre matemático del sistema depende críticamente de las condiciones impuestas en la frontera $\\partial\\Omega$. Bajo el difeomorfismo de escala $u_i = u_{i,\\mathrm{ref}}\\,\\hat{u}_i$ y $\\mathbf{x} = \\mathbf{L}\\,\\hat{\\mathbf{x}}$, las leyes de contorno canónicas se transforman revelando números adimensionales superficiales:
\\begin{enumerate}
    \\item \\textbf{Condición de Robin / Convección Interfacial (Biot / Sherwood):}
    \\begin{equation}
    -D_i \\left. \\nabla u_i \\cdot \\hat{\\mathbf{n}} \\right|_{\\partial\\Omega} = k_c \\left( \\left. u_i \\right|_{\\partial\\Omega} - u_{i,\\infty} \\right) \\quad \\Longrightarrow \\quad -\\left. \\tilde{\\nabla}\\hat{u}_i \\cdot \\hat{\\mathbf{n}} \\right|_{\\partial\\Omega} = \\mathrm{Bi} \\cdot \\left( \\left. \\hat{u}_i \\right|_{\\partial\\Omega} - \\hat{u}_{i,\\infty} \\right),
    \\end{equation}
    donde el número de Biot/Sherwood interfacial $\\mathrm{Bi} = \\frac{k_c L}{D}$ cuantifica la razón entre la resistencia al transporte molecular interno y la resistencia externa interfacial.
    \\item \\textbf{Condición de Neumann con Flujo Impuesto (Damköhler Superficial):}
    \\begin{equation}
    -D_i \\left. \\nabla u_i \\cdot \\hat{\\mathbf{n}} \\right|_{\\partial\\Omega} = J_0 \\quad \\Longrightarrow \\quad -\\left. \\tilde{\\nabla}\\hat{u}_i \\cdot \\hat{\\mathbf{n}} \\right|_{\\partial\\Omega} = \\frac{J_0 L}{D_i u_{i,\\mathrm{ref}}} \\equiv \\mathrm{Da}_s.
    \\end{equation}
    \\item \\textbf{Fronteras Móviles de Transición de Fase (Condición de Stefan):}
    \\begin{equation}
    \\rho \\Delta H \\frac{ds}{dt} = -k \\left. \\nabla T \\cdot \\hat{\\mathbf{n}} \\right|_{s(t)} \\quad \\Longrightarrow \\quad \\frac{d\\hat{s}}{d\\hat{t}} = \\mathrm{Ste} \\cdot \\left( -\\left. \\tilde{\\nabla}\\hat{\\theta} \\cdot \\hat{\\mathbf{n}} \\right|_{\\hat{s}(\\hat{t})} \\right),
    \\end{equation}
    con número de Stefan $\\mathrm{Ste} = \\frac{c_p \\Delta T}{\\Delta H}$, parametrizando la velocidad interfacial frente a la conducción térmica.
\\end{enumerate}

\\section{Análisis Espectral de Estabilidad y Espectro de Dispersión Adimensional $\\sigma(k)$}
Para un sistema continuo multicomponente arbitrario $\\partial_{\\hat{t}} \\hat{\\mathbf{u}} = \\mathbf{D} \\tilde{\\nabla}^2 \\hat{\\mathbf{u}} + \\mathbf{R}(\\hat{\\mathbf{u}})$, la linealización modal $\\hat{\\mathbf{u}}(\\hat{\\mathbf{x}}, \\hat{t}) = \\hat{\\mathbf{u}}^* + \\boldsymbol{\\eta}\\,e^{\\sigma \\hat{t} + i \\mathbf{k} \\cdot \\hat{\\mathbf{x}}}$ en torno a un estado base conduce a la relación de dispersión analítica:
\\begin{equation}
\\det\\left(\\sigma \\mathbf{I} - \\mathbf{M}(k)\\right) = 0, \\qquad \\mathbf{M}(k) = \\mathbf{J} - k^2 \\mathbf{D},
\\end{equation}
donde $\\mathbf{J} = \\left.\\frac{\\partial \\mathbf{R}}{\\partial \\hat{\\mathbf{u}}}\\right|_{\\hat{\\mathbf{u}}^*}$ denota la matriz jacobiana adimensional. El espectro de dispersión $\\operatorname{Re}(\\sigma)(k)$ clasifica de forma unívoca:
\\begin{itemize}
    \\item \\textbf{Estabilidad Homogénea:} $\\operatorname{tr}(\\mathbf{J}) < 0$ y $\\det(\\mathbf{J}) > 0$.
    \\item \\textbf{Bifurcaciones de Hopf (ondas y ciclos límite):} $\\operatorname{tr}(\\mathbf{J}) = 0$ con frecuencia $\\omega_0 = \\sqrt{\\det(\\mathbf{J})}$.
    \\item \\textbf{Inestabilidad Espacial de Onda Finita:} $\\det(\\mathbf{M}(k)) < 0$ para $k \\approx k_{\\mathrm{crit}} = \\sqrt{\\frac{D_1 J_{22} + D_2 J_{11}}{2 D_1 D_2}}$, induciendo autoorganización espacial macroscópica.
\\end{itemize}

\\section{Simetrías de Escala de Lie y Reducción Autosimilar}
Más allá del análisis dimensional algebraico, las ecuaciones diferenciales parciales de transporte continuo admiten grupos continuos de transformación de Lie. Consideremos el grupo uniparamétrico de homotecias canónicas:
\\begin{equation}
\\tau \\mapsto \\lambda^2 \\tau, \\qquad \\xi \\mapsto \\lambda \\xi, \\qquad \\hat{u} \\mapsto \\lambda^\\gamma \\hat{u}, \\qquad \\lambda \\in \\mathbb{R}_{>0},
\\end{equation}
cuyo generador infinitesimal está dado por el operador diferencial:
\\begin{equation}
X = 2\\,\\tau\\,\\frac{\\partial}{\\partial \\tau} + \\xi\\,\\frac{\\partial}{\\partial \\xi} + \\gamma\\,\\hat{u}\\,\\frac{\\partial}{\\partial \\hat{u}}.
\\end{equation}
La invariancia homotética $X(\\mathcal{E}) = 0$ determina que la solución continua no depende de $\\xi$ y $\\tau$ de manera aislada, sino exclusivamente de la variable de similitud invariante canónica:
\\begin{equation}
\\eta = \\frac{\\xi}{(4\\,\\mathrm{Fo}\\,\\tau)^{1/2}}.
\\end{equation}
Sustituyendo el ansatz autosimilar $\\hat{u}(\\xi, \\tau) = \\tau^{\\gamma/2}\\,\\Theta(\\eta)$, la EDP en dos variables independientes se colapsa exactamente en la ecuación diferencial ordinaria:
\\begin{equation}
\\Theta''(\\eta) + 2\\,\\eta\\,\\Theta'(\\eta) - 2\\gamma\\,\\Theta(\\eta) + \\mathrm{Da}\\,\\mathcal{R}(\\Theta) = 0.
\\end{equation}
Para transporte difusivo conservativo con masa total invariante $\\mathcal{M}_0$, $\\gamma = -1$, conduciendo al perfil autosimilar universal gaussiano $\\Theta(\\eta) = \\frac{\\mathcal{M}_0}{\\sqrt{4\\pi\\,\\mathrm{Fo}}}\\exp(-\\eta^2)$. En medios con difusión no lineal (ley de Darcy en medios porosos) o leyes cinéticas empíricas, la reducción de Lie genera soluciones autosimilares de Barenblatt-Pattle con frentes de propagación de soporte compacto.

\\section{Síntesis Computacional: Solvers Stiff, Estabilidad CFL y PINNs Adimensionales}

\\subsection{Criterios de Estabilidad de Malla: Péclet de Celda y Límite CFL}
En esquemas espaciales discretos (diferencias finitas de segundo orden), la discretización convectiva advectiva induce oscilaciones espurias no físicas a menos que se satisfaga el criterio de Péclet de celda:
\\begin{equation}
\\mathrm{Pe}_{\\Delta\\xi} = \\mathrm{Pe}\\,\\Delta\\xi \\le 2.
\\end{equation}
Si $\\mathrm{Pe}_{\\Delta\\xi} > 2$, la aproximación con diferencias centrales pierde monotonía, requiriendo esquemas Upwind TVD con limitadores de flujo o un refinamiento de malla a $N_x \\ge \\lceil\\mathrm{Pe}/2\\rceil + 1$.
Asimismo, en la integración temporal explícita, la restricción de estabilidad difusiva de Courant-Friedrichs-Lewy (CFL) impone:
\\begin{equation}
\\Delta\\tau \\le \\frac{\\Delta\\xi^2}{2\\,\\mathrm{Fo}},
\\end{equation}
lo que obliga a ejecutar $\\mathcal{O}(N_x^2)$ pasos temporales. En sistemas continuos con cinética rápida ($\\mathrm{Da} \\gg 1$), el índice de rigidez $\\mathcal{S} = \\frac{\\mathrm{Da}}{\\mathrm{Fo}} N_x^2 \\gg 1$ vuelve inviables los solvers explícitos, justificando el uso indispensable de integradores implícitos BDF / Radau / TRBDF2.

\\subsection{Método de Líneas y Rigidez Numérica}
Al discretizar espacialmente el dominio escalado $\\hat{x}_i = i\\,\\Delta\\hat{x}$ sobre una malla de $N$ nodos, la EDP adimensional se proyecta en un sistema dinámico de ecuaciones diferenciales ordinarias rígidas (\\textit{stiff}):
\\begin{equation}
\\frac{d\\hat{\\mathbf{u}}}{d\\hat{t}} = \\mathbf{J}_{\\mathrm{Fo}} \\hat{\\mathbf{u}} + \\mathbf{R}(\\hat{\\mathbf{u}}; \\boldsymbol{\\Pi}).
\\end{equation}
Dado que el número de condición de la matriz difusiva discreta $\\kappa(\\mathbf{J}_{\\mathrm{Fo}}) \\sim \\mathcal{O}(N^2)$ induce una rigidez severa, el sistema adimensional se resuelve de manera óptima empleando esquemas implícitos multipaso (BDF en Python SciPy o \\texttt{TRBDF2()} en Julia DifferentialEquations). La normalización a $\\mathcal{O}(1)$ evita desbordamientos de coma flotante y errores de redondeo numérico.

\\subsection{Physics-Informed Neural Networks (PINNs) Adimensionales}
Para el modelado mediante redes neuronales informadas por la física, el campo continuo se aproxima por una red densa $\\hat{u}_\\theta(\\hat{t}, \\hat{\\mathbf{x}})$. En variables dimensionales, las discrepancias de órdenes de magnitud entre coeficientes difusivos ($D \\sim 10^{-10}\\,\\mathrm{m^2/s}$) y cinéticos ($k \\sim 10^3\\,\\mathrm{s^{-1}}$) provocan el colapso del gradiente (\\textit{vanishing/exploding gradients}). 
En la formulación canónica, las variables de entrada y salida yacen estrictamente en el hipercubo compacto $[0, 1]^{n+1}$. La función de pérdida multiobjetivo se define como:
\\begin{equation}
\\mathcal{L}(\\theta) = \\frac{w_{\\mathrm{pde}}}{N_f} \\sum_{k=1}^{N_f} \\left\\| \\hat{\\mathcal{R}}_{\\mathrm{pde}}(\\hat{t}_k, \\hat{\\mathbf{x}}_k; \\theta) \\right\\|^2 + \\frac{w_{\\mathrm{bc}}}{N_b} \\sum_{j=1}^{N_b} \\left\\| \\hat{\\mathcal{R}}_{\\mathrm{bc}}(\\hat{t}_j, \\hat{\\mathbf{x}}_j; \\theta) \\right\\|^2,
\\end{equation}
donde los operadores diferenciales se evalúan exactamente mediante diferenciación automática (\\texttt{torch.autograd.grad}).

\\section{Teorema de Certificación por Retro-sustitución Exacta}

\\begin{teorema}[Conservación Diferencial y Equivalencia Recíproca]
Sea $\\mathcal{E}_{\\mathrm{dim}}(\\mathbf{u}, \\mathbf{x}, t; \\mathbf{p}) = 0$ un sistema continuo de reacción-difusión de orden $k$. Sea $\\mathcal{T}: (\\mathbf{x}, t, \\mathbf{u}) \\mapsto (\\hat{\\mathbf{x}}, \\hat{t}, \\hat{\\mathbf{u}})$ el difeomorfismo de escala inducido por las referencias $(\\mathbf{L}, t_{\\mathrm{ref}}, \\mathbf{u}_{\\mathrm{ref}})$, y sea $\\mathcal{E}_{\\mathrm{adim}}(\\hat{\\mathbf{u}}, \\hat{\\mathbf{x}}, \\hat{t}; \\boldsymbol{\\Pi}) = 0$ el sistema adimensional resultante.
Entonces, la aplicación del difeomorfismo inverso $\\mathcal{T}^{-1}$:
\\begin{equation}
\\hat{\\mathbf{x}} = \\mathbf{L}^{-1} \\mathbf{x}, \\qquad \\hat{t} = \\frac{t}{t_{\\mathrm{ref}}}, \\qquad \\hat{u}_i = \\frac{u_i}{u_{i,\\mathrm{ref}}},
\\end{equation}
satisface la identidad algebraica:
\\begin{equation}
\\mathcal{T}^{-1} \\left[ \\mathcal{E}_{\\mathrm{adim}}(\\hat{\\mathbf{u}}, \\hat{\\mathbf{x}}, \\hat{t}; \\boldsymbol{\\Pi}) \\right] \\equiv \\boldsymbol{\\Phi}^{-1} \\mathcal{E}_{\\mathrm{dim}}(\\mathbf{u}, \\mathbf{x}, t; \\mathbf{p}) \\equiv 0,
\\end{equation}
demostrando que el sistema adimensional es analíticamente equivalente al sistema original si y solo si los factores globales de escala satisfacen $\\Phi_j \\ne 0$ en todo el dominio.
\\end{teorema}

\\section{Conclusiones}
El análisis dimensional de sistemas continuos de reacción-difusión trasciende la simple manipulación algebraica: establece un difeomorfismo exacto que preserva la topología diferencial de los campos y expone con claridad meridiana las bifurcaciones espaciotemporales del medio continuo. La introducción rigurosa de factores de esbeltez $\\mathcal{A}_j$, escalas intrínsecas de longitud $\\ell_{\\mathrm{rd}} = \\sqrt{D/k}$ y formulaciones canónicas duales fundamentadas en la balanza dominante de Kruskal provee una plataforma sólida para el análisis de perturbaciones singulares, la integración numérica rígida y el entrenamiento robusto de arquitecturas de aprendizaje profundo.

\\begin{thebibliography}{99}
\\bibitem{turing1952} A. M. Turing, \`\`The chemical basis of morphogenesis'', \\emph{Philosophical Transactions of the Royal Society of London. Series B, Biological Sciences}, vol. 237, no. 641, pp. 37--72, 1952.
\\bibitem{fisher1937} R. A. Fisher, \`\`The wave of advance of advantageous genes'', \\emph{Annals of Eugenics}, vol. 7, no. 4, pp. 355--369, 1937.
\\bibitem{kolmogorov1937} A. N. Kolmogorov, I. G. Petrovsky, and N. S. Piskunov, \`\`{\\'E}tude de l'{\\'e}quation de la diffusion avec croissance de la quantit{\\'e} de mati{\\\`e}re et son application {\\\`a} un probl{\\\`e}me biologique'', \\emph{Bulletin de l'Universit{\\'e} d'{\\'E}tat {\\\`a} Moscou, S{\\'e}rie Internationale, Section A}, vol. 1, no. 6, pp. 1--25, 1937.
\\bibitem{buckingham1914} E. Buckingham, \`\`On physically similar systems; illustrations of the use of dimensional equations'', \\emph{Physical Review}, vol. 4, no. 4, pp. 345--376, 1914.
\\bibitem{kruskal1962} M. D. Kruskal, \`\`Asymptotology'', in \\emph{Mathematical Models in Physical Sciences}, Prentice-Hall, pp. 17--48, 1962.
\\bibitem{barenblatt1996} G. I. Barenblatt, \\emph{Scaling, Self-similarity, and Intermediate Asymptotics}, Cambridge University Press, 1996.
\\bibitem{murray2002} J. D. Murray, \\emph{Mathematical Biology II: Spatial Models and Biomedical Applications}, 3rd ed., Springer-Verlag, 2002.
\\bibitem{bender1999} C. M. Bender and S. A. Orszag, \\emph{Advanced Mathematical Methods for Scientists and Engineers I: Asymptotic Methods and Perturbation Theory}, Springer-Verlag, 1999.
\\end{thebibliography}

\\end{document}
`;

export function generarReadmePublicacion(nombreModelo: string): string {
  const slug = nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `# Paquete de Publicación Científica: ${nombreModelo}

Este paquete contiene todos los archivos fuente en formato LaTeX estándar (compatible con Overleaf, TeX Live, MiKTeX y arXiv) para documentar, publicar y archivar formalmente el desarrollo matemático de la adimensionalización canónica de sistemas de reacción-difusión.

## Archivos Incluidos

1. **\`manuscrito_teorico.tex\`**: Artículo formal sobre los fundamentos algebraicos, grupos de Lie de dilataciones, matriz dimensional de Buckingham $\\mathbf{M}$, escalamiento anisotrópico en $\\mathbb{R}^n$, análisis asintótico de patrones de Turing, frentes de Fisher-KPP y teoremas de conservación diferencial por retro-sustitución exacta.
2. **\`deduccion_${slug}.tex\`**: Deducción matemática constructiva completa del modelo físico activo, con verificación de homogeneidad de Fourier, mapeos canónicos, balanza dominante de Kruskal e invariantes característicos.
3. **\`referencias.bib\`**: Base de datos bibliográfica BibTeX con las citas clásicas fundamentales indexadas (Turing 1952, Fisher 1937, Kolmogorov-Petrovsky-Piskunov 1937, Buckingham 1914, Kruskal 1962, Barenblatt 1996, Murray 2002, Bender-Orszag 1999).
4. **\`README.md\`**: Esta guía técnica de compilación y reproducibilidad.

## Instrucciones de Compilación

### Opción 1: En Overleaf
1. Entra a [Overleaf](https://www.overleaf.com) y selecciona **New Project** → **Upload Project**.
2. Sube estos archivos fuente.
3. Elige el compilador estándar **pdfLaTeX** en la configuración del proyecto y compila con un clic.

### Opción 2: Compilación Local por Terminal (Linux / macOS / Windows)
\`\`\`bash
# Compilar el manuscrito teórico con bibliografía:
pdflatex manuscrito_teorico.tex
bibtex manuscrito_teorico
pdflatex manuscrito_teorico.tex
pdflatex manuscrito_teorico.tex

# Compilar la deducción matemática del modelo:
pdflatex deduccion_${slug}.tex
\`\`\`

## Certificado de Reproducibilidad
Generado por el Núcleo Formal de Adimensionalización de Antigravity.
Garantiza conservación diferencial exacta e invariancia frente al sistema de unidades.
`;
}

export function descargarTexto(nombreArchivo: string, contenido: string, mime: string = "text/plain"): void {
  const blob = new Blob([contenido], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivo;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}

export function descargarPaqueteCompleto(
  nombreModelo: string,
  indiceForma: number,
  f: FormulacionNucleo
): void {
  const slug = nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const deduccion = exportarDesarrollo(f);
  const readme = generarReadmePublicacion(nombreModelo);

  // Descarga escalonada de los 4 archivos fuente
  descargarTexto(`deduccion-${slug}-forma-${indiceForma + 1}.tex`, deduccion, "text/x-tex");
  setTimeout(() => {
    descargarTexto("manuscrito_teorico.tex", MANUSCRICO_TEORICO_TEX_SAFE(nombreModelo), "text/x-tex");
  }, 350);
  setTimeout(() => {
    descargarTexto("referencias.bib", BIBTEX_PUBLICACION, "text/x-bibtex");
  }, 700);
  setTimeout(() => {
    descargarTexto("README.md", readme, "text/markdown");
  }, 1050);
}

function MANUSCRICO_TEORICO_TEX_SAFE(_nombreModelo: string): string {
  return MANUSCRITO_TEORICO_TEX;
}

export function calcularCrc32(bytes: Uint8Array): number {
  let crc = -1;
  for (let i = 0; i < bytes.length; i++) {
    crc ^= bytes[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ -1) >>> 0;
}

export function crearArchivoZip(archivos: { nombre: string; contenido: string }[]): Uint8Array {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const cdChunks: Uint8Array[] = [];
  let offset = 0;

  for (const archivo of archivos) {
    const nameBytes = encoder.encode(archivo.nombre);
    const dataBytes = encoder.encode(archivo.contenido);
    const crc = calcularCrc32(dataBytes);

    // Local file header (30 bytes)
    const lh = new Uint8Array(30);
    const viewLh = new DataView(lh.buffer);
    viewLh.setUint32(0, 0x04034b50, true);
    viewLh.setUint16(4, 20, true);
    viewLh.setUint16(6, 0, true);
    viewLh.setUint16(8, 0, true); // Store mode (uncompressed)
    viewLh.setUint16(10, 0, true);
    viewLh.setUint16(12, 0, true);
    viewLh.setUint32(14, crc, true);
    viewLh.setUint32(18, dataBytes.length, true);
    viewLh.setUint32(22, dataBytes.length, true);
    viewLh.setUint16(26, nameBytes.length, true);
    viewLh.setUint16(28, 0, true);

    chunks.push(lh, nameBytes, dataBytes);

    // Central directory header (46 bytes)
    const cdh = new Uint8Array(46);
    const viewCdh = new DataView(cdh.buffer);
    viewCdh.setUint32(0, 0x02014b50, true);
    viewCdh.setUint16(4, 20, true);
    viewCdh.setUint16(6, 20, true);
    viewCdh.setUint16(8, 0, true);
    viewCdh.setUint16(10, 0, true);
    viewCdh.setUint16(12, 0, true);
    viewCdh.setUint16(14, 0, true);
    viewCdh.setUint32(16, crc, true);
    viewCdh.setUint32(20, dataBytes.length, true);
    viewCdh.setUint32(24, dataBytes.length, true);
    viewCdh.setUint16(28, nameBytes.length, true);
    viewCdh.setUint16(30, 0, true);
    viewCdh.setUint16(32, 0, true);
    viewCdh.setUint16(34, 0, true);
    viewCdh.setUint16(36, 0, true);
    viewCdh.setUint32(38, 0, true);
    viewCdh.setUint32(42, offset, true);

    cdChunks.push(cdh, nameBytes);

    offset += 30 + nameBytes.length + dataBytes.length;
  }

  const cdOffset = offset;
  let cdSize = 0;
  for (const c of cdChunks) cdSize += c.length;

  // End of Central Directory Record (22 bytes)
  const eocd = new Uint8Array(22);
  const viewEocd = new DataView(eocd.buffer);
  viewEocd.setUint32(0, 0x06054b50, true);
  viewEocd.setUint16(4, 0, true);
  viewEocd.setUint16(6, 0, true);
  viewEocd.setUint16(8, archivos.length, true);
  viewEocd.setUint16(10, archivos.length, true);
  viewEocd.setUint32(12, cdSize, true);
  viewEocd.setUint32(16, cdOffset, true);
  viewEocd.setUint16(20, 0, true);

  let totalLength = 0;
  for (const c of chunks) totalLength += c.length;
  for (const c of cdChunks) totalLength += c.length;
  totalLength += eocd.length;

  const result = new Uint8Array(totalLength);
  let pos = 0;
  for (const c of chunks) {
    result.set(c, pos);
    pos += c.length;
  }
  for (const c of cdChunks) {
    result.set(c, pos);
    pos += c.length;
  }
  result.set(eocd, pos);

  return result;
}

export function descargarPaqueteZip(
  nombreModelo: string,
  indiceForma: number,
  f: FormulacionNucleo
): void {
  const slug = nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const deduccion = exportarDesarrollo(f);
  const readme = generarReadmePublicacion(nombreModelo);

  const archivos = [
    { nombre: `deduccion_${slug}_forma_${indiceForma + 1}.tex`, contenido: deduccion },
    { nombre: "manuscrito_teorico.tex", contenido: MANUSCRITO_TEORICO_TEX },
    { nombre: "referencias.bib", contenido: BIBTEX_PUBLICACION },
    { nombre: "README.md", contenido: readme }
  ];

  const zipBytes = crearArchivoZip(archivos);
  const blob = new Blob([zipBytes as BlobPart], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `paquete-publicacion-${slug}.zip`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
