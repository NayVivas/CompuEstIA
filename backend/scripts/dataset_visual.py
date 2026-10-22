"""Prepara y revisa anotaciones visuales por proyecto, fuera del motor de cómputo."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import sys
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from computos.ia.dataset_visual import guardar_anotacion, preparar_dataset, validar_dataset
from computos.ia.evaluacion_visual import evaluar_predicciones


RECURSOS = Path(__file__).resolve().parents[1] / "herramientas"
INTERFAZ = RECURSOS / "anotador_visual.html"


def _pares(valores: list[str], opcion: str) -> dict[str, str]:
    resultado = {}
    for valor in valores:
        clave, separador, dato = valor.partition("=")
        if not separador or not clave or not dato or clave in resultado:
            raise ValueError(f"{opcion}: se esperaba ID=valor, sin ID repetido: {valor}")
        resultado[clave] = dato
    return resultado


def crear_servidor(salida: Path, puerto: int = 8765) -> tuple[HTTPServer, str]:
    salida = salida.resolve()
    validar_dataset(salida)
    token = secrets.token_urlsafe(24)

    class Anotador(BaseHTTPRequestHandler):
        def _enviar(self, codigo: int, datos: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def _error(self, codigo: int, mensaje: str) -> None:
            self._enviar(codigo, json.dumps({"error": mensaje}, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _autorizado(self) -> bool:
            # Un encabezado no simple evita que una página web externa escriba mediante formularios.
            return secrets.compare_digest(self.headers.get("X-Anotador-Token", ""), token)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/":
                self._enviar(200, INTERFAZ.read_bytes(), "text/html; charset=utf-8")
                return
            if self.path in {"/anotador_visual.css", "/anotador_visual.js"}:
                tipo = "text/css; charset=utf-8" if self.path.endswith(".css") else "text/javascript; charset=utf-8"
                self._enviar(200, (RECURSOS / self.path[1:]).read_bytes(), tipo)
                return
            if self.path == "/api/manifest" or self.path == "/api/anotaciones":
                if not self._autorizado():
                    self._error(403, "Acceso denegado.")
                    return
                nombre = "manifest.json" if self.path.endswith("manifest") else "anotaciones.json"
                self._enviar(200, (salida / nombre).read_bytes(), "application/json; charset=utf-8")
                return
            if self.path.startswith("/imagenes/"):
                if not self._autorizado():
                    self._error(403, "Acceso denegado.")
                    return
                # Solo se entregan imágenes incluidas expresamente en el manifiesto.
                manifiesto = json.loads((salida / "manifest.json").read_text(encoding="utf-8"))
                permitido = {"/" + pagina["imagen"] for pagina in manifiesto["paginas"]}
                if self.path not in permitido:
                    self._error(404, "Imagen no registrada.")
                    return
                imagen = salida / self.path.lstrip("/")
                self._enviar(200, imagen.read_bytes(), mimetypes.guess_type(imagen.name)[0] or "image/jpeg")
                return
            self._error(404, "Ruta desconocida.")

        def do_POST(self) -> None:
            if self.path != "/api/guardar" or not self._autorizado():
                self._error(403, "Acceso denegado.")
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._error(415, "Se requiere JSON.")
                return
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
                if not 0 < longitud <= 1024 * 1024:
                    raise ValueError("Tamaño de anotación inválido.")
                contenido = json.loads(self.rfile.read(longitud))
                if not isinstance(contenido, dict):
                    raise ValueError("Anotación inválida.")
                anotacion = guardar_anotacion(salida, contenido.get("pagina_id"), contenido.get("anotacion"))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self._error(400, str(error))
                return
            self._enviar(200, json.dumps({"guardado": True, "anotacion": anotacion}).encode(), "application/json; charset=utf-8")

        def log_message(self, formato: str, *argumentos: object) -> None:
            # Evita registrar la clave presente en el URL al abrir la interfaz.
            if self.path.split("?", 1)[0] != "/":
                super().log_message(formato, *argumentos)

    return HTTPServer(("127.0.0.1", puerto), Anotador), token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    preparar = sub.add_parser("preparar", help="Inventariar y renderizar PDF por proyecto")
    preparar.add_argument("--proyecto", action="append", required=True, metavar="ID=RUTA")
    preparar.add_argument("--split", action="append", default=[], metavar="ID=train|validation|test")
    preparar.add_argument("--salida", type=Path, required=True)
    preparar.add_argument("--lado-maximo", type=int, default=1600)
    servir = sub.add_parser("servir", help="Abrir un anotador local de planos")
    servir.add_argument("--salida", type=Path, required=True)
    servir.add_argument("--puerto", type=int, default=8765)
    servir.add_argument("--abrir", action="store_true")
    validar = sub.add_parser("validar", help="Comprobar particiones y anotaciones")
    validar.add_argument("--salida", type=Path, required=True)
    evaluar = sub.add_parser("evaluar", help="Medir un detector visual en proyectos revisados")
    evaluar.add_argument("--salida", type=Path, required=True)
    evaluar.add_argument("--predicciones", type=Path, required=True)
    evaluar.add_argument("--split", choices=["validation", "test"], default="test")
    opciones = parser.parse_args(argv)
    try:
        if opciones.accion == "preparar":
            proyectos = {id_: Path(ruta) for id_, ruta in _pares(opciones.proyecto, "--proyecto").items()}
            splits = _pares(opciones.split, "--split")
            manifiesto = preparar_dataset(proyectos, opciones.salida, splits=splits, lado_maximo=opciones.lado_maximo)
            print(f"Preparados {len(manifiesto['paginas'])} planos/páginas de {len(proyectos)} proyectos.")
        if opciones.accion == "servir":
            servidor, token = crear_servidor(opciones.salida, opciones.puerto)
            url = f"http://127.0.0.1:{servidor.server_port}/?clave={token}"
            print(f"Anotador local: {url}", flush=True)
            print("Cerrá con Ctrl+C. Las anotaciones se guardan en la carpeta de salida.", flush=True)
            if opciones.abrir:
                webbrowser.open(url)
            try:
                servidor.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                servidor.server_close()
            return 0
        if opciones.accion == "evaluar":
            print(json.dumps(evaluar_predicciones(opciones.salida, opciones.predicciones, split=opciones.split), ensure_ascii=False, indent=2))
            return 0
        print(json.dumps(validar_dataset(opciones.salida), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
