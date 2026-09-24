import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Sin esto, Turbopack busca hacia arriba un package-lock.json y acaba
  // infiriendo el directorio HOME del usuario como raiz del proyecto
  // (avisa en cada build). La raiz es esta carpeta, no el repo entero:
  // el backend Python es un despliegue aparte.
  turbopack: { root: path.resolve(__dirname) },
  // El indicador flotante de Next en desarrollo se pone justo encima del
  // boton "Resolver" de la esquina inferior izquierda del flowsheet.
  devIndicators: false,
};

export default nextConfig;
