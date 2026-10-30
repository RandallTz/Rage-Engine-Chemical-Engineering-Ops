import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "katex/dist/katex.min.css";
import "./globals.css";
import NavBar from "./components/NavBar";
import { ConexionProvider } from "./components/ConexionProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rage · Simulation engine",
  description: "Equation-oriented process simulation with a shared thermodynamic core.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* Dos cosas deliberadas aqui:
          1) Tema oscuro explicito: el CSS base de Next cambia --foreground
             segun prefers-color-scheme, y eso dejaba texto claro sobre
             superficies claras (nodos ilegibles).
          2) ALTURA DEFINIDA (h-screen, no min-h-full). React Flow resuelve
             su tamano con height:100% del contenedor, y un porcentaje no
             resuelve contra una altura MINIMA -- con min-h-full el canvas
             quedaba en cero y no se dibujaba nada ("The parent container
             needs a width and a height"). El scroll de las paginas largas
             lo lleva <main>, no el body. */}
      <body className="flex h-dvh flex-col overflow-hidden bg-zinc-950 text-zinc-100">
        <a href="#workspace" className="skip-link">Skip to workspace</a>
        <ConexionProvider>
          <NavBar />
          <main id="workspace" tabIndex={-1} className="flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</main>
        </ConexionProvider>
      </body>
    </html>
  );
}
