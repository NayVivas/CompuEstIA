"""Comando principal del proyecto.

La implementación vive dentro del paquete ``computos`` para mantener limpia la
raíz. Se conserva este archivo para seguir ejecutando ``python app.py``.
"""

from computos.flujos.principal import main


if __name__ == "__main__":
    raise SystemExit(main())
