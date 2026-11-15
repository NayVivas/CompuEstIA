
import { useEffect, useRef, useState } from "react";
import "./Presentacion.css";


const escenas = [
  {
    numero: "01",
    etiqueta: "EL DESAFÍO",
    titulo: "La información está en los planos.",
    destacado: "El desafío es convertirla en conocimiento.",
    video: "/presentacion/escena-01.mp4",
    tipo: "intro",
  },
  {
    numero: "02",
    etiqueta: "LA PROPUESTA",
    titulo: "CómputoEstIA",
    destacado: "Ingeniería civil + Ciencia de datos + Inteligencia artificial.",
    video: "/presentacion/escena-02.mp4",
    tipo: "marca",
  },
  {
    numero: "03",
    etiqueta: "EL PROCESO Y LA REVISIÓN",
    titulo: "De múltiples documentos a información organizada.",
    destacado: "La tecnología asiste. El profesional decide.",
    video: "/presentacion/escena-03.mp4",
    tipo: "proceso",
  },
  {
    numero: "04",
    etiqueta: "VISUALIZACIÓN Y RESULTADOS",
    titulo: "Del modelo 3D al cómputo métrico.",
    destacado: "Información técnica para tomar decisiones.",
    video: "/presentacion/escena-04.mp4",
    tipo: "modelo",
  },
  {
    numero: "05",
    etiqueta: "EL FUTURO",
    titulo: "Transformamos planos en información.",
    destacado: "Y la información en mejores herramientas para la ingeniería.",
    video: "/presentacion/escena-05.mp4",
    tipo: "cierre",
  },
  {
  numero: "06",
  etiqueta: "AGRADECIMIENTO",
  titulo: "¡Muchas gracias!",
  destacado: "CómputoEstIA",
  descripcion:
    "De los planos a la información. De la información a mejores decisiones.",
  video: "/presentacion/escena-06.mp4",
  tipo: "cierre",
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
    };

    contenedor.addEventListener("scroll", actualizarProgreso);
    actualizarProgreso();

    return () =>
      contenedor.removeEventListener("scroll", actualizarProgreso);
  }, []);

  useEffect(() => {
    function manejarTeclado(evento) {
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
            {String(escenaActiva + 1).padStart(2, "0")} / 06
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

      {escenas.map((escena, indice) => (
        <section
          key={escena.numero}
          data-index={indice}
          ref={(elemento) => {
            seccionesRef.current[indice] = elemento;
          }}
          className={`presentacion-escena escena-${escena.tipo}`}
        >
          <div className="presentacion-fondo" />
          <div className="presentacion-luz" />

          <video
            className="presentacion-video"
            src={escena.video}
            muted
            loop
            playsInline
            preload="none"
            aria-hidden="true"
          />

          <div className="presentacion-velo" />

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

            <p className="presentacion-descripcion">
              {escena.descripcion}
            </p>

            {indice === 0 && (
              <div className="presentacion-palabras">
                <span>PLANOS</span>
                <span>DATOS</span>
                <span>CÓMPUTOS</span>
              </div>
            )}

            {indice === 2 && (
              <div className="presentacion-pasos">
                {["Lectura", "Clasificación", "Extracción", "Asociación"].map(
                  (paso, i) => (
                    <div key={paso}>
                      <span>0{i + 1}</span>
                      <strong>{paso}</strong>
                    </div>
                  )
                )}
              </div>
            )}

            {indice === 3 && (
              <div className="presentacion-elementos">
                <span>Fundaciones</span>
                <span>Pedestales</span>
                <span>Vigas de riostra</span>
                <span>Columnas</span>
              </div>
            )}

            {indice === 5 && (
              <div className="presentacion-gracias">
                
              </div>
            )}
          </div>

          <div className="presentacion-pie">
            <span>PROYECTO DE CIENCIA DE DATOS E INTELIGENCIA ARTIFICIAL</span>
            <span>SCROLL PARA CONTINUAR ↓</span>
          </div>
        </section>
      ))}
    </main>
  );
}

export default Presentacion;
