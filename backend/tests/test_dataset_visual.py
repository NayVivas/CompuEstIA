"""Aislamiento entre proyectos y persistencia de evidencia visual revisada."""

from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

import pymupdf

from computos.ia.dataset_visual import (
    guardar_anotacion, preparar_dataset, validar_anotacion_pagina, validar_dataset,
)
from computos.ia.evaluacion_visual import evaluar_predicciones
from scripts.dataset_visual import crear_servidor


class DatasetVisualTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.salida = self.raiz / "dataset"
        self.proyectos = {}
        for nombre, paginas in [("vivienda", 1), ("edificio", 2), ("mercado", 1)]:
            pdf = self.raiz / f"{nombre}.pdf"
            with pymupdf.open() as documento:
                for numero in range(paginas):
                    pagina = documento.new_page(width=320, height=220)
                    pagina.draw_rect((35, 40, 180, 165), color=(0, 0, 0))
                    pagina.insert_text((40, 25), f"{nombre} planta {numero + 1}")
                documento.save(pdf)
            self.proyectos[nombre] = pdf
        self.splits = {"vivienda": "train", "edificio": "validation", "mercado": "test"}

    def preparar(self):
        return preparar_dataset(self.proyectos, self.salida, splits=self.splits, lado_maximo=800)

    def test_paginas_multipagina_y_splits_por_proyecto(self):
        manifiesto = self.preparar()
        self.assertEqual(len(manifiesto["paginas"]), 4)
        self.assertEqual([p["pagina"] for p in manifiesto["paginas"] if p["proyecto_id"] == "edificio"], [1, 2])
        self.assertEqual({p["split"] for p in manifiesto["paginas"] if p["proyecto_id"] == "edificio"}, {"validation"})
        for pagina in manifiesto["paginas"]:
            self.assertTrue((self.salida / pagina["imagen"]).is_file())
        resumen = validar_dataset(self.salida)
        self.assertEqual(resumen["revisadas"], 0)
        self.assertFalse(resumen["cobertura_minima"])

    def test_no_puede_copiar_el_mismo_pdf_a_otro_proyecto(self):
        copia = self.raiz / "copia.pdf"
        shutil.copyfile(self.proyectos["vivienda"], copia)
        with self.assertRaisesRegex(ValueError, "mismo PDF"):
            preparar_dataset({"original": self.proyectos["vivienda"], "otro": copia}, self.salida,
                             splits={"original": "train", "otro": "test"})

    def test_revisa_elemento_y_preserva_anotaciones_al_preparar_otra_vez(self):
        manifiesto = self.preparar()
        pagina = manifiesto["paginas"][0]
        anotacion = {
            "sha256_pdf": pagina["sha256_pdf"], "estado": "revisada", "revisor": "Ing. Pérez",
            "elementos": [{"id": "f1", "familia": "fundacion_aislada", "geometria": "poligono",
                           "puntos": [[.1, .2], [.5, .2], [.5, .7], [.1, .7]],
                           "referencia": "F1", "nota": "contorno"}],
        }
        guardar_anotacion(self.salida, pagina["id"], anotacion)
        self.preparar()
        resumen = validar_dataset(self.salida)
        self.assertEqual(resumen["revisadas"], 1)
        self.assertEqual(resumen["elementos_confirmados_por_familia"], {"fundacion_aislada": 1})
        self.assertFalse(resumen["cobertura_minima"])
        with self.assertRaisesRegex(ValueError, "ausentes"):
            preparar_dataset({"edificio": self.proyectos["edificio"]}, self.salida,
                             splits={"edificio": "validation"})
        self.assertEqual(validar_dataset(self.salida)["revisadas"], 1)

    def test_rechaza_geometrias_y_coordenadas_no_verificables(self):
        pagina = self.preparar()["paginas"][0]
        base = {"sha256_pdf": pagina["sha256_pdf"], "estado": "revisada", "revisor": "Ing. Pérez",
                "elementos": [{"id": "c1", "familia": "columna", "geometria": "poligono",
                                "puntos": [[.1, .1], [.6, .1], [.6, .6]], "referencia": "C1"}]}
        self.assertEqual(len(validar_anotacion_pagina(pagina, base)["elementos"]), 1)
        base["elementos"][0]["geometria"] = "polilinea"
        with self.assertRaisesRegex(ValueError, "geometría inválida"):
            validar_anotacion_pagina(pagina, base)
        base["elementos"][0]["geometria"] = "poligono"
        base["elementos"][0]["puntos"] = [[.1, .1], [1.1, .1], [.6, .6]]
        with self.assertRaisesRegex(ValueError, "normalizados"):
            validar_anotacion_pagina(pagina, base)

    def test_servidor_local_solo_guarda_paginas_validas(self):
        pagina = self.preparar()["paginas"][0]
        servidor, token = crear_servidor(self.salida, puerto=0)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(lambda: (servidor.shutdown(), servidor.server_close(), hilo.join(timeout=3)))
        base = f"http://127.0.0.1:{servidor.server_port}"
        with self.assertRaises(HTTPError) as error:
            urlopen(base + "/api/manifest")
        self.assertEqual(error.exception.code, 403)
        solicitud = Request(base + "/api/manifest", headers={"X-Anotador-Token": token})
        with urlopen(solicitud) as respuesta:
            self.assertEqual(len(json.load(respuesta)["paginas"]), 4)
        imagen = Request(base + "/" + pagina["imagen"], headers={"X-Anotador-Token": token})
        with urlopen(imagen) as respuesta:
            self.assertTrue(respuesta.read(2) == b"\xff\xd8")
            self.assertIn("blob:", respuesta.headers["Content-Security-Policy"])
        with urlopen(base + "/anotador_visual.js") as respuesta:
            self.assertIn(b"async function iniciar()", respuesta.read())
        carga = {"pagina_id": pagina["id"], "anotacion": {
            "sha256_pdf": pagina["sha256_pdf"], "estado": "revisada",
            "revisor": "Ingeniera Ruiz", "elementos": []}}
        solicitud = Request(base + "/api/guardar", data=json.dumps(carga).encode(), method="POST",
                            headers={"X-Anotador-Token": token, "Content-Type": "application/json"})
        with urlopen(solicitud) as respuesta:
            self.assertTrue(json.load(respuesta)["guardado"])
        self.assertEqual(validar_dataset(self.salida)["revisadas"], 1)
        with self.assertRaises(HTTPError) as error:
            urlopen(base + "/imagenes/../manifest.json", timeout=3)
        self.assertEqual(error.exception.code, 403)

    def test_evaluacion_en_proyectos_revisados_cuenta_omisiones_y_falsos_positivos(self):
        self.splits["edificio"] = "test"
        self.splits["mercado"] = "test"
        paginas = self.preparar()["paginas"]
        poligono = [[.1, .1], [.4, .1], [.4, .4], [.1, .4]]
        linea = [[.1, .5], [.8, .5]]
        def elemento(id_, familia, geometria, puntos):
            return {"id": id_, "familia": familia, "geometria": geometria,
                    "puntos": puntos, "referencia": "", "nota": ""}
        verdad = {
            paginas[1]["id"]: [elemento("f1", "fundacion_aislada", "poligono", poligono),
                                elemento("v1", "viga_riostra", "polilinea", linea)],
            paginas[2]["id"]: [],
            paginas[3]["id"]: [elemento("p1", "pedestal", "poligono", poligono)],
        }
        for pagina in paginas[1:]:
            guardar_anotacion(self.salida, pagina["id"], {"sha256_pdf": pagina["sha256_pdf"],
                "estado": "revisada", "revisor": "Ing. Pérez", "elementos": verdad[pagina["id"]]})
        predicciones = {"version": 1, "predicciones": {
            paginas[1]["id"]: [elemento("a", "fundacion_aislada", "poligono", poligono),
                                elemento("b", "viga_riostra", "polilinea", linea)],
            paginas[2]["id"]: [elemento("c", "columna", "poligono", poligono)]}}
        ruta = self.raiz / "predicciones.json"
        ruta.write_text(json.dumps(predicciones), encoding="utf-8")
        resultado = evaluar_predicciones(self.salida, ruta)
        self.assertEqual(resultado["global"]["aciertos"], 2)
        self.assertEqual(resultado["global"]["falsos_positivos"], 1)
        self.assertEqual(resultado["global"]["omisiones"], 1)
        self.assertEqual(resultado["por_familia"]["viga_riostra"]["recall"], 1.0)
        predicciones["predicciones"][paginas[0]["id"]] = []
        ruta.write_text(json.dumps(predicciones), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fuera de la partición"):
            evaluar_predicciones(self.salida, ruta)

    def test_no_evalua_paginas_que_no_han_sido_revisadas(self):
        self.preparar()
        ruta = self.raiz / "predicciones.json"
        ruta.write_text('{"version": 1, "predicciones": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sin revisar"):
            evaluar_predicciones(self.salida, ruta)


if __name__ == "__main__":
    unittest.main()
