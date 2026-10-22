# CómputoEstIA — frontend

Interfaz React conectada con la API FastAPI del proyecto. Esta versión exige el
contrato de API 6 y el build `2026-10-19-v12.3.2-revision-planta`, y muestra en la pantalla de carga el backend
al que está conectada.

## Ejecutar

Primero debe estar funcionando el backend en http://127.0.0.1:8000.

~~~powershell
npm ci
npm run dev
~~~

Después abra la dirección indicada por Vite, normalmente
http://localhost:5173.

## Conexión

`src/services/api.js` envía uno o varios PDF como `multipart/form-data` a:

~~~text
POST http://127.0.0.1:8000/api/analisis/automatico/
~~~

No hay que seleccionar previamente planta, detalles ni columnas. La pantalla
oculta por defecto las páginas ya clasificadas y muestra solamente los
conflictos que requieren intervención. Las demás páginas pueden inspeccionarse
de forma opcional antes de pasar a las inconsistencias y al cálculo.

Para usar otra URL, copie .env.example como .env y modifique VITE_API_URL.
