"""
Backend de matplotlib: SIN ventana, salvo que se pida.

Por que existe este modulo. Los metodos graficar_* de core/ terminan en
plt.show(). En un backend interactivo eso abre una ventana y BLOQUEA el
proceso hasta que alguien la cierre. Mientras los graficos solo se
miraban a mano, daba igual; en cuanto esos modulos se importan desde el
servidor web, desde los tests o desde CI, pasa de molesto a inaceptable:

  - aparecen ventanas encima de lo que el usuario este haciendo,
  - cada una bloquea hasta que se cierre, asi que una suite de 11 scripts
    se queda esperando a que alguien atienda,
  - y en un servidor sin pantalla puede fallar directamente.

Con 'Agg' se dibuja a memoria y plt.show() se vuelve una operacion nula.
Las figuras siguen construyendose igual, asi que cualquier savefig()
sigue funcionando y el codigo de graficado no cambia.

Quien SI quiera la ventana interactiva define MPLBACKEND (por ejemplo
MPLBACKEND=TkAgg) y esto no lo pisa: la variable de entorno manda.

Importar este modulo ANTES que matplotlib.pyplot. No depende de
config/settings.py, asi que no arrastra pint al nucleo.
"""

import os

import matplotlib

if not os.environ.get("MPLBACKEND"):
    # force=False: si algo ya creo una figura con otro backend, no se le
    # quita de debajo -- se respeta y se sigue.
    matplotlib.use("Agg", force=False)

#: Para que quien lea un traceback sepa por que no salio ninguna ventana.
BACKEND_ACTIVO = matplotlib.get_backend()
