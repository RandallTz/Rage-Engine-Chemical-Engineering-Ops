/**
 * Las suites anteriores a las "simulaciones guardables" daban por hecho
 * que los componentes eran una preferencia GLOBAL del navegador. Ya no:
 * viven dentro de la simulacion abierta. Esto siembra una simulacion con
 * los componentes que pida el test, para que cada suite siga probando lo
 * suyo y no el arranque en frio.
 */
export async function prepararSimulacion(pagina, componentes = null) {
  const lista = componentes ?? [
    { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
    { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
  ];
  // Hay que estar en el origen correcto antes de tocar su localStorage.
  await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "domcontentloaded" });
  await pagina.evaluate((comps) => {
    const ahora = new Date().toISOString();
    const sim = {
      id: "sim_test_fija",
      nombre: "Simulación de prueba",
      creada: ahora,
      modificada: ahora,
      componentes: comps,
      modelo: "unifac_raoult",
      flowsheet: { nodes: [], edges: [], dados: {} },
    };
    localStorage.setItem("simulador.simulaciones",
      JSON.stringify({ activa: sim.id, lista: [sim] }));
  }, lista);
}
