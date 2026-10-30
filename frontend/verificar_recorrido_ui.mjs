/** Reusable browser regression through the Codex CUA tab API. Run with a connected
 * local frontend and backend. Creates its own named simulation, preserves existing work.
 * await verificarRecorrido(tab); No synthetic physics responses or storage resets. */
export async function verificarRecorrido(tab,{crear=true}={}){
  const comprobar=(c,m)=>{if(!c)throw new Error(m);};
  const estado=()=>tab.getAXState({emit:false});
  if(crear){await tab.playwright.getByRole('link',{name:'Mis simulaciones',exact:true}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Referencia · bomba ideal Datos completos',exact:true}).click();
  await tab.playwright.getByRole('textbox',{name:'Nombre de la nueva simulación',exact:true}).fill('Validación del recorrido');
  await tab.playwright.getByRole('button',{name:'Crear y abrir',exact:true}).click();await estado();}
  await tab.playwright.getByTestId('rf__node-s1').click();await estado();
  await tab.playwright.getByLabel('Unidad de F',{exact:true}).selectOption('kmol/h');await estado();
  comprobar(await tab.playwright.getByRole('textbox',{name:'F Dato introducido',exact:true}).getAttribute('value')==='360','La conversión de mol/s a kmol/h debe preservar el caudal físico');
  await tab.reload();await estado();
  await tab.playwright.getByTestId('rf__node-s1').click();await estado();
  comprobar(await tab.playwright.getByRole('textbox',{name:'F Dato introducido',exact:true}).getAttribute('value')==='360','El dato convertido debe persistir tras recargar');
  await tab.playwright.getByRole('button',{name:'Resolver',exact:true}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Editar',exact:true}).click();await estado();
  await tab.playwright.getByTestId('rf__node-op1').click();await estado();
  await tab.playwright.getByRole('tab',{name:'Resultados',exact:true}).click();await estado();
  await tab.playwright.getByText('Caso de referencia analítico',{exact:true}).click();await estado();
  comprobar(await tab.playwright.getByText('303975 · Coincide',{exact:true}).isVisible(),'La descarga calculada debe corresponder a la bomba de referencia');
  await tab.playwright.getByRole('button',{name:'Editar op1.factor_P',exact:true}).click();await estado();
  comprobar(await tab.playwright.getByRole('tab',{name:'Datos',exact:true}).getAttribute('aria-selected')==='true','Revisar un resultado debe abrir Datos');
  await tab.playwright.getByRole('tab',{name:'Modelo',exact:true}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Consultar sistema completo',exact:false}).click();await estado();
  comprobar(await tab.playwright.locator('dialog[open] .katex').count()>0,'El cuaderno debe renderizar LaTeX');
  await tab.playwright.getByRole('button',{name:'Cerrar consulta de ecuaciones',exact:true}).click();await estado();
  await tab.playwright.getByText('Tabla de corrientes',{exact:false}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Revisar s1.F, Dato introducido',exact:true}).click();await estado();
  comprobar(await tab.playwright.getByRole('textbox',{name:'F Dato introducido',exact:true}).isVisible(),'La tabla debe navegar al dato de la corriente');
  await tab.playwright.getByRole('button',{name:'Reporte',exact:true}).click();await estado();
  comprobar(await tab.playwright.getByRole('heading',{name:'Especificaciones y alcance del cálculo',exact:true}).isVisible(),'El reporte debe incluir trazabilidad');
  await tab.playwright.getByRole('button',{name:'Comparar',exact:true}).click();await estado();
  await tab.playwright.getByLabel('Nombre del escenario',{exact:true}).fill('Base de regresión');
  await tab.playwright.getByRole('button',{name:'Guardar escenario',exact:true}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Editar',exact:true}).click();await estado();
  await tab.playwright.getByTestId('rf__node-op1').click();await estado();
  await tab.playwright.getByRole('textbox',{name:'factor_P Dato introducido',exact:true}).fill('4');await estado();
  await tab.playwright.getByRole('button',{name:'Resolver',exact:true}).click();await estado();
  await tab.playwright.getByRole('button',{name:'Comparar',exact:true}).click();await estado();
  await tab.playwright.locator('.scenario-changes summary').click();await estado();
  comprobar(await tab.playwright.locator('.scenario-changes').getByText('op1.factor_P',{exact:true}).isVisible(),'La comparación debe identificar la especificación modificada');
  await tab.playwright.getByRole('button',{name:'Editar',exact:true}).click();await estado();
  await tab.playwright.getByTestId('rf__node-op1').click();await estado();
  await tab.playwright.getByRole('textbox',{name:'factor_P Dato introducido',exact:true}).fill('3');await estado();
  await tab.playwright.getByRole('button',{name:'Resolver',exact:true}).click();await estado();
  return 'Recorrido verificado: creación, unidades, persistencia, cálculo real, pestañas, LaTeX, tabla, reporte y cambios entre escenarios.';
}
