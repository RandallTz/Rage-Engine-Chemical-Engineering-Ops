import type { Metadata } from "next";
import Cuaderno from "./Cuaderno";
import "./estilos.css";
import "./estudio.css";

export const metadata: Metadata = { title: "Adimensionalización | Rage" };
export default function Page() { return <Cuaderno />; }
