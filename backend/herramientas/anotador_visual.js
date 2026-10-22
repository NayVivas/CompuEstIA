"use strict";

const clave = new URLSearchParams(location.search).get("clave") || "";
const $ = (id) => document.getElementById(id);
const svgNS = "http://www.w3.org/2000/svg";
const nombres = {
  fundacion_aislada: "Fundación aislada",
  cimiento_corrido: "Cimiento corrido",
  pedestal: "Pedestal",
  viga_riostra: "Viga de riostra",
  columna: "Columna"
};
let manifest, registros, paginaActual, elementos = [], borrador = [], modificada = false;
let ultimoRevisor = "", imagenURL = null, generacion = 0, aumento = 1;

async function solicitar(ruta, opciones = {}) {
  const respuesta = await fetch(ruta, { ...opciones, headers: {
    "X-Anotador-Token": clave, ...(opciones.headers || {})
  }});
  if (!respuesta.ok) {
    let mensaje = `Error ${respuesta.status}`;
    try { mensaje = (await respuesta.json()).error || mensaje; } catch (_) { /* mensaje HTTP */ }
    throw new Error(mensaje);
  }
  return respuesta;
}

function mensaje(texto, tipo = "") {
  $("mensaje").textContent = texto;
  $("mensaje").className = tipo;
}

function opciones(select, valores) {
  select.replaceChildren();
  valores.forEach(([valor, etiqueta]) => {
    const opcion = document.createElement("option");
    opcion.value = valor;
    opcion.textContent = etiqueta;
    select.append(opcion);
  });
}

function actualizarGeometria() {
  const formas = manifest.geometrias[$("familia").value];
  opciones($("geometria"), formas.map((forma) => [forma, forma === "poligono" ? "Polígono · contorno" : "Polilínea · eje"]));
}

function paginasProyecto() {
  return manifest.paginas.filter((pagina) => pagina.proyecto_id === $("proyecto").value);
}

function actualizarLista() {
  const paginas = paginasProyecto();
  opciones($("pagina"), paginas.map((pagina) => {
    const registro = registros[pagina.id];
    const marca = registro?.estado === "revisada" ? "✓" : "○";
    return [pagina.id, `${marca} ${pagina.documento} · pág. ${pagina.pagina}`];
  }));
  $("progreso").textContent = `${Object.values(registros).filter((a) => a.estado === "revisada").length} / ${manifest.paginas.length} páginas revisadas`;
}

function dibujar() {
  const svg = $("dibujo");
  svg.replaceChildren();
  const agregar = (tag, puntos, color, relleno) => {
    const forma = document.createElementNS(svgNS, tag);
    forma.setAttribute("points", puntos.map(([x, y]) => `${x},${y}`).join(" "));
    forma.setAttribute("fill", relleno);
    forma.setAttribute("stroke", color);
    forma.setAttribute("stroke-width", "3");
    forma.setAttribute("vector-effect", "non-scaling-stroke");
    forma.setAttribute("pointer-events", "none");
    svg.append(forma);
  };
  elementos.forEach((elemento) => {
    agregar(elemento.geometria === "poligono" ? "polygon" : "polyline", elemento.puntos, "#006db3", elemento.geometria === "poligono" ? "#007aca3d" : "none");
  });
  if (borrador.length > 1) agregar("polyline", borrador, "#df6237", "none");
  borrador.forEach(([x, y]) => {
    const punto = document.createElementNS(svgNS, "circle");
    punto.setAttribute("cx", x);
    punto.setAttribute("cy", y);
    punto.setAttribute("r", "0.004");
    punto.setAttribute("fill", "#df6237");
    punto.setAttribute("vector-effect", "non-scaling-stroke");
    punto.setAttribute("pointer-events", "none");
    svg.append(punto);
  });
  $("puntos").textContent = `${borrador.length} punto${borrador.length === 1 ? "" : "s"} marcado${borrador.length === 1 ? "" : "s"}`;
  const lista = $("elementos");
  lista.replaceChildren();
  elementos.forEach((elemento, indice) => {
    const fila = document.createElement("li");
    const descripcion = document.createElement("span");
    descripcion.textContent = `${nombres[elemento.familia]}${elemento.referencia ? ` · ${elemento.referencia}` : ""} · ${elemento.puntos.length} puntos`;
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = "Quitar";
    boton.setAttribute("aria-label", `Quitar elemento ${indice + 1}`);
    boton.addEventListener("click", () => {
      elementos.splice(indice, 1);
      modificada = true;
      dibujar();
    });
    fila.append(descripcion, boton);
    lista.append(fila);
  });
}

async function mostrar(paginaId) {
  const pagina = manifest.paginas.find((item) => item.id === paginaId);
  if (!pagina) return;
  if (modificada && !confirm("Hay cambios sin guardar en esta página. ¿Continuar?")) {
    $("proyecto").value = paginaActual.proyecto_id;
    $("pagina").value = paginaActual.id;
    return;
  }
  const carga = ++generacion;
  paginaActual = pagina;
  $("proyecto").value = pagina.proyecto_id;
  actualizarLista();
  $("pagina").value = pagina.id;
  $("encabezado").textContent = `${pagina.proyecto_id} · página ${pagina.pagina} · ${pagina.split}`;
  $("origen").textContent = `Archivo: ${pagina.documento}\nPágina: ${pagina.pagina}\nPartición: ${pagina.split}`;
  $("origen").style.whiteSpace = "pre-line";
  const anotacion = registros[pagina.id];
  elementos = structuredClone(anotacion?.elementos || []);
  borrador = [];
  $("revisor").value = anotacion?.revisor || ultimoRevisor;
  $("revisada").checked = anotacion?.estado === "revisada";
  $("referencia").value = "";
  $("nota").value = "";
  modificada = false;
  dibujar();
  mensaje("Cargando imagen…");
  try {
    const respuesta = await solicitar("/" + pagina.imagen);
    const nuevaURL = URL.createObjectURL(await respuesta.blob());
    if (carga !== generacion) { URL.revokeObjectURL(nuevaURL); return; }
    if (imagenURL) URL.revokeObjectURL(imagenURL);
    imagenURL = nuevaURL;
    $("plano").src = imagenURL;
    aumento = 1;
    $("plano").onload = () => {
      if (carga !== generacion) return;
      ajustarZoom();
      mensaje("");
    };
  } catch (error) { mensaje(error.message, "error"); }
}

function ajustarZoom() {
  const imagen = $("plano");
  const ancho = Math.min(imagen.naturalWidth || 1000, $("lienzo").clientWidth - 42);
  $("papel").style.width = Math.round(ancho * aumento) + "px";
}

function cambiarPagina(delta) {
  const paginas = paginasProyecto();
  const indice = paginas.findIndex((item) => item.id === paginaActual.id) + delta;
  if (paginas[indice]) mostrar(paginas[indice].id);
}

function agregarElemento() {
  const geometria = $("geometria").value;
  const minimo = geometria === "poligono" ? 3 : 2;
  if (borrador.length < minimo) {
    mensaje(`Marcá al menos ${minimo} puntos para esta forma.`, "error");
    return;
  }
  elementos.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    familia: $("familia").value,
    geometria,
    puntos: borrador,
    referencia: $("referencia").value.trim(),
    nota: $("nota").value.trim()
  });
  borrador = [];
  $("referencia").value = "";
  $("nota").value = "";
  modificada = true;
  mensaje("Elemento agregado. Guardá la revisión de la página.");
  dibujar();
}

async function guardar() {
  if (borrador.length) { mensaje("Terminá o deshacé los puntos pendientes antes de guardar.", "error"); return; }
  const revisor = $("revisor").value.trim();
  const anotacion = {
    sha256_pdf: paginaActual.sha256_pdf,
    estado: $("revisada").checked ? "revisada" : "pendiente",
    revisor,
    elementos
  };
  $("guardar").disabled = true;
  try {
    const respuesta = await solicitar("/api/guardar", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({pagina_id: paginaActual.id, anotacion})
    });
    registros[paginaActual.id] = (await respuesta.json()).anotacion;
    ultimoRevisor = revisor;
    modificada = false;
    actualizarLista();
    $("pagina").value = paginaActual.id;
    mensaje("Revisión guardada.", "ok");
  } catch (error) { mensaje(error.message, "error"); }
  finally { $("guardar").disabled = false; }
}

async function iniciar() {
  try {
    if (!clave) throw new Error("Abrí la URL completa que muestra la terminal del anotador.");
    manifest = await (await solicitar("/api/manifest")).json();
    registros = (await (await solicitar("/api/anotaciones")).json()).paginas;
    opciones($("familia"), Object.keys(manifest.geometrias).map((key) => [key, nombres[key] || key]));
    actualizarGeometria();
    opciones($("proyecto"), manifest.proyectos.map((proyecto) => [proyecto.id, `${proyecto.id} · ${proyecto.split}`]));
    actualizarLista();
    if (manifest.paginas.length) await mostrar(manifest.paginas[0].id);
    $("proyecto").addEventListener("change", () => {
      const seleccion = paginasProyecto()[0];
      if (seleccion) mostrar(seleccion.id);
    });
    $("pagina").addEventListener("change", () => mostrar($("pagina").value));
    $("familia").addEventListener("change", actualizarGeometria);
    $("anterior").addEventListener("click", () => cambiarPagina(-1));
    $("siguiente").addEventListener("click", () => cambiarPagina(1));
    $("acercar").addEventListener("click", () => { aumento = Math.min(aumento * 1.5, 6); ajustarZoom(); });
    $("alejar").addEventListener("click", () => { aumento = Math.max(aumento / 1.5, 0.5); ajustarZoom(); });
    $("deshacer").addEventListener("click", () => { borrador.pop(); dibujar(); });
    $("terminar").addEventListener("click", agregarElemento);
    $("guardar").addEventListener("click", guardar);
    $("revisor").addEventListener("input", () => { modificada = true; });
    $("revisada").addEventListener("change", () => { modificada = true; });
    $("dibujo").addEventListener("pointerdown", (evento) => {
      const limites = $("dibujo").getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (evento.clientX - limites.left) / limites.width));
      const y = Math.max(0, Math.min(1, (evento.clientY - limites.top) / limites.height));
      borrador.push([x, y]);
      dibujar();
    });
    window.addEventListener("beforeunload", (evento) => { if (modificada) evento.preventDefault(); });
    window.addEventListener("resize", ajustarZoom);
  } catch (error) { $("progreso").textContent = error.message; mensaje(error.message, "error"); }
}

iniciar();
