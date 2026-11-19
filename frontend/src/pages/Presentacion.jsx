import { useEffect, useRef, useState } from "react";
import "./Presentacion.css";

const integrantes = [
  "Irene Rendón",
  "Naylu Vivas",
  "Federico Guillardoy",
  "Pablo Vaccotti",
  "Maximiliano Martínez",
  "Alejandro Bachmann",
];


const escenas = [
  {
    numero: "01",
    etiqueta: "EL DESAFÍO",
    titulo: "Toda construcción comienza mucho antes del primer ladrillo.",
    destacado: "Detrás de cada obra hay planos, medidas y decisiones.",
    video: "/presentacion/escena-01.mp4",
    tipo: "intro",
  },
  {
  numero: "02",
  etiqueta: "LA PROPUESTA",
  titulo: "CómputoEstIA",
  destacado: "Una nueva forma de transformar planos en información útil.",
  video: "/presentacion/escena-02.mp4",
  tipo: "marca",
},
  {
    numero: "03",
    etiqueta: "EL PROCESO",
    titulo: "De los planos a la información.",
    destacado: "Cargamos. Organizamos. Revisamos.",
    video: "/presentacion/escena-03.mp4",
    tipo: "proceso",
    modo: "demo",
  },
  {
    numero: "04",
    etiqueta: "VISUALIZACIÓN 3D",
    titulo: "Una forma diferente de ver la estructura.",
    destacado: "Comprender también es poder visualizar.",
    video: "/presentacion/escena-04.mp4",
    tipo: "modelo",
    modo: "demo",
  },
  {
    numero: "05",
    etiqueta: "LOS RESULTADOS",
    titulo: "Información organizada para tomar mejores decisiones.",
    destacado: "Resultados que podemos revisar y verificar.",
    video: "/presentacion/escena-05.mp4",
    tipo: "cierre",
    modo: "demo",
  },
  {
  numero: "06",
  etiqueta: "NUESTRO PROYECTO",
  titulo: "CómputoEstIA",
  destacado: "Una idea que une conocimientos para resolver desafíos reales.",
  descripcion: "Muchas gracias",
  tipo: "equipo",
},
];


function Presentacion() {
  const [escenaActiva, setEscenaActiva] = useState(0);
  const [progreso, setProgreso] = useState(0);
  const [pantallaCompleta, setPantallaCompleta] = useState(false);
  const contenedorRef = useRef(null);
  const seccionesRef = useRef([]);

  useEffect(() => {
    const observador = new IntersectionObserver(
      (entradas) => {
        entradas.forEach((entrada) => {
          if (entrada.isIntersecting) {
            const indice = Number(entrada.target.dataset.index);
            setEscenaActiva(indice);

            const video = entrada.target.querySelector("video");
            if (video) {
              video.play().catch(() => {});
            }
          } else {
            const video = entrada.target.querySelector("video");
            if (video) video.pause();
          }
        });
      },
      {
        root: contenedorRef.current,
        threshold: 0.55,
      }
    );

    seccionesRef.current.forEach((seccion) => {
      if (seccion) observador.observe(seccion);
    });

    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    const contenedor = contenedorRef.current;
    if (!contenedor) return;

    const actualizarProgreso = () => {
      const maximo =
        contenedor.scrollHeight - contenedor.clientHeight;

      setProgreso(
        maximo > 0 ? (contenedor.scrollTop / maximo) * 100 : 0
      );

      seccionesRef.current.forEach((seccion) => {
        if (!seccion?.classList.contains("escena-demo")) return;

        const recorrido = seccion.offsetHeight - contenedor.clientHeight;
        const avance = Math.max(
          0,
          Math.min(1, (contenedor.scrollTop - seccion.offsetTop) / (recorrido * 0.6))
        );
        const contenido = seccion.querySelector(".presentacion-contenido");
        const altura = contenido?.scrollHeight || 0;

        seccion.style.setProperty("--demo-intro-alto", `${altura * (1 - avance)}px`);
        seccion.style.setProperty("--demo-texto-opacidad", String(Math.max(0, 1 - avance * 1.6)));
      });
    };

    contenedor.addEventListener("scroll", actualizarProgreso);
    window.addEventListener("resize", actualizarProgreso);
    actualizarProgreso();

    return () => {
      contenedor.removeEventListener("scroll", actualizarProgreso);
      window.removeEventListener("resize", actualizarProgreso);
    };
  }, []);

  useEffect(() => {
    function manejarTeclado(evento) {
      if (
        escenas[escenaActiva]?.modo === "demo" &&
        ["ArrowDown", "ArrowUp", "PageDown", "PageUp"].includes(evento.key)
      ) {
        return;
      }

      if (evento.key === "ArrowDown" || evento.key === "PageDown") {
        evento.preventDefault();
        irAEscena(Math.min(escenaActiva + 1, escenas.length - 1));
      }

      if (evento.key === "ArrowUp" || evento.key === "PageUp") {
        evento.preventDefault();
        irAEscena(Math.max(escenaActiva - 1, 0));
      }

      if (evento.key === "Home") {
        evento.preventDefault();
        irAEscena(0);
      }

      if (evento.key === "End") {
        evento.preventDefault();
        irAEscena(escenas.length - 1);
      }

      if (evento.key === "Escape" && document.fullscreenElement) {
        document.exitFullscreen?.();
      }
    }

    window.addEventListener("keydown", manejarTeclado);
    return () => window.removeEventListener("keydown", manejarTeclado);
  }, [escenaActiva]);

  useEffect(() => {
    function actualizarPantalla() {
      setPantallaCompleta(Boolean(document.fullscreenElement));
    }

    document.addEventListener("fullscreenchange", actualizarPantalla);
    return () =>
      document.removeEventListener("fullscreenchange", actualizarPantalla);
  }, []);

  function irAEscena(indice) {
    seccionesRef.current[indice]?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function alternarPantallaCompleta() {
    if (!document.fullscreenElement) {
      contenedorRef.current?.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }

  function ampliarVideo(indice) {
    seccionesRef.current[indice]?.querySelector("video")?.requestFullscreen?.();
  }

  return (
    <main className="presentacion" ref={contenedorRef}>
      <div className="presentacion-progreso">
        <div
          className="presentacion-progreso-barra"
          style={{ height: `${progreso}%` }}
        />
      </div>

      <header className="presentacion-header">
        <a className="presentacion-logo" href="/">
          <span className="presentacion-logo-icono">C</span>
          <span>CómputoEstIA</span>
        </a>

        <div className="presentacion-controles">
          <span className="presentacion-contador">
            {String(escenaActiva + 1).padStart(2, "0")} /{" "}
            {String(escenas.length).padStart(2, "0")}
          </span>
          <button
            type="button"
            className="presentacion-boton"
            onClick={alternarPantallaCompleta}
            aria-label="Alternar pantalla completa"
          >
            {pantallaCompleta ? "Salir de pantalla completa" : "Pantalla completa"}
          </button>
        </div>
      </header>

      <nav className="presentacion-indicadores" aria-label="Escenas">
        {escenas.map((escena, indice) => (
          <button
            key={escena.numero}
            type="button"
            className={
              escenaActiva === indice
                ? "presentacion-punto activo"
                : "presentacion-punto"
            }
            onClick={() => irAEscena(indice)}
            aria-label={`Ir a escena ${indice + 1}: ${escena.etiqueta}`}
            title={escena.etiqueta}
          >
            <span>{escena.numero}</span>
          </button>
        ))}
      </nav>

      {escenas.map((escena, indice) => {
        const esDemo = escena.modo === "demo";
        return (
          <section
            key={escena.numero}
            data-index={indice}
            ref={(elemento) => {
              seccionesRef.current[indice] = elemento;
            }}
            className={`presentacion-escena escena-${escena.tipo}${esDemo ? " escena-demo" : ""}`}
          >
            <div className="presentacion-fondo" />
            <div className="presentacion-luz" />

            {!esDemo && escena.video && (
              <video
                className="presentacion-video presentacion-video-fondo"
                src={escena.video}
                muted
                loop
                playsInline
                preload="none"
                aria-hidden="true"
              />
            )}

            {!esDemo && <div className="presentacion-velo" />}

            <div className="presentacion-escenario">
              <div className="presentacion-contenido">
                <div className="presentacion-etiqueta">
                  <span />
                  {escena.etiqueta}
                </div>

                {indice === 1 && (
                  <div className="presentacion-marca-grande">
                    <div className="presentacion-simbolo">C</div>
                    <span>CómputoEstIA</span>
                  </div>
                )}

                <p className="presentacion-numero">{escena.numero}</p>

                <h1>{escena.titulo}</h1>

                <h2>{escena.destacado}</h2>

                {escena.descripcion && (
                  <p className="presentacion-descripcion">
                    {escena.descripcion}
                  </p>
                )}

                {escena.tipo === "equipo" && (
                  <div className="presentacion-integrantes">
                    {integrantes.map((nombre) => (
                      <div className="presentacion-integrante" key={nombre}>
                        {nombre}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {esDemo && (
                <div className="presentacion-demostracion">
                  <div className="presentacion-demo-barra">
                    <button
                      type="button"
                      className="presentacion-ampliar"
                      onClick={() => ampliarVideo(indice)}
                    >
                      Ampliar video ↗
                    </button>
                  </div>
                  <video
                    className="presentacion-video presentacion-video-demo"
                    src={escena.video}
                    muted
                    loop
                    playsInline
                    controls
                    preload="metadata"
                    aria-label={escena.etiqueta}
                  />
                </div>
              )}

              <div className="presentacion-pie">
                <span>PROYECTO DE CIENCIA DE DATOS E INTELIGENCIA ARTIFICIAL</span>
                <span>
                  {indice === escenas.length - 1
                    ? "FIN DE LA PRESENTACIÓN"
                    : "SCROLL PARA CONTINUAR ↓"}
                </span>
              </div>
            </div>
          </section>
        );
      })}
    </main>
  );
}

export default Presentacion;