import puppeteer from "puppeteer-core";
import { prepararSimulacion } from "./preparar_simulacion.mjs";
const EDGE = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const nav = await puppeteer.launch({ executablePath: EDGE, headless: "new", args: ["--no-sandbox"], defaultViewport: { width: 1200, height: 1400 } });
const p = await nav.newPage();
await prepararSimulacion(p, [{nombre:"isobutylene",MW:56.106},{nombre:"methanol",MW:32.042},{nombre:"mtbe",MW:88.148}]);
await p.goto("http://localhost:3000/termodinamica/reactiva", { waitUntil: "networkidle0" });
await esperar(800);
await p.evaluate(() => {
  const set=(i,v)=>{Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,"value").set.call(i,v);i.dispatchEvent(new Event("input",{bubbles:true}));};
  const ins=[...document.querySelectorAll("input")];
  ["-1","-1","3","1e6","60000","5"].forEach((v,k)=>ins[k]&&set(ins[k],v));
});
await esperar(300);
await p.evaluate(() => [...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="Mapa reactivo")?.click());
for (let i=0;i<150;i++){ const t=await p.evaluate(()=>document.body.innerText); if(!t.includes("Integrando…"))break; await esperar(1000);}
await esperar(600);
const el = await p.$("svg");
await el.screenshot({ path: "_topo_svg.png" });
await nav.close();
console.log("listo");
