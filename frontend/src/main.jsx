import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

console.log("[CómputoEstIA][bootstrap] frontend iniciado", {
  url: window.location.href,
  apiUrl: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api",
});

window.addEventListener("error", (event) => {
  console.error("[CómputoEstIA][window.error]", {
    mensaje: event.message,
    archivo: event.filename,
    linea: event.lineno,
    columna: event.colno,
    error: event.error,
  });
});

window.addEventListener("unhandledrejection", (event) => {
  console.error(
    "[CómputoEstIA][unhandledrejection] Promesa rechazada sin manejar",
    event.reason,
  );
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
