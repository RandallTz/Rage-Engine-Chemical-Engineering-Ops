export type Expresion = { tipo: 'numero'; valor: number } | { tipo: 'variable'; nombre: string } | { tipo: 'operacion'; op: string; args: Expresion[] };
const funciones: Record<string, (args: number[]) => number> = {
  sin: a => Math.sin(a[0]), cos: a => Math.cos(a[0]), exp: a => Math.exp(a[0]), log: a => Math.log(a[0]),
  sqrt: a => Math.sqrt(a[0]), abs: a => Math.abs(a[0]), min: a => Math.min(...a), max: a => Math.max(...a), step: a => a[0] >= 0 ? 1 : 0,
};
export function analizarExpresion(texto: string, variables: string[]): Expresion {
  if (!texto.trim()) throw new Error('Falta un valor o expresión.');
  if (texto.length > 500) throw new Error('La expresión es demasiado larga.');
  const tokens: string[] = []; let pos = 0;
  while (pos < texto.length) {
    const match = /^\s*(?:(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|([A-Za-z][A-Za-z0-9_]*)|([+\-*/^(),]))/.exec(texto.slice(pos));
    if (!match) { if (!texto.slice(pos).trim()) break; throw new Error(`Símbolo no permitido en «${texto.slice(pos,pos+12)}».`); }
    tokens.push(match[0].trim()); pos += match[0].length;
  }
  let i = 0, nodos = 0;
  const nodo = (e: Expresion) => { if (++nodos > 200) throw new Error('Demasiadas operaciones.'); return e; };
  const operacion = (op: string, args: Expresion[]) => nodo({tipo:'operacion',op,args});
  function atom(): Expresion {
    const token = tokens[i++];
    if (!token) throw new Error('Expresión incompleta.');
    if (token === '(') { const e=sum(); if(tokens[i++]!==')')throw new Error('Falta cerrar el paréntesis.'); return e; }
    if (/^(\d|\.)/.test(token)) { const valor=Number(token); if(!Number.isFinite(valor))throw new Error('Número no finito.'); return nodo({tipo:'numero',valor}); }
    if (token==='pi'||token==='e') return nodo({tipo:'numero',valor:token==='pi'?Math.PI:Math.E});
    if (Object.hasOwn(funciones,token)) {
      if(tokens[i++]!=='(')throw new Error(`${token} necesita paréntesis.`);
      const args=[sum()]; while(tokens[i]===','){i++;args.push(sum());}
      if(tokens[i++]!==')')throw new Error('Falta cerrar la función.');
      if((!['min','max'].includes(token)&&args.length!==1)||args.length>8)throw new Error('Cantidad de argumentos no admitida.');
      return operacion(token,args);
    }
    if(!variables.includes(token))throw new Error(`Variable no admitida: ${token}. Usa ${variables.join(', ')}.`);
    return nodo({tipo:'variable',nombre:token});
  }
  function power(): Expresion { const e=atom(); if(tokens[i]==='^'){i++;return operacion('^',[e,unary()]);}return e; }
  function unary(): Expresion { if(tokens[i]==='-'||tokens[i]==='+'){const op=tokens[i++];return op==='-'?operacion('neg',[unary()]):unary();}return power(); }
  function product(): Expresion { let e=unary();while(tokens[i]==='*'||tokens[i]==='/'){const op=tokens[i++];e=operacion(op,[e,unary()]);}return e; }
  function sum(): Expresion {let e=product();while(tokens[i]==='+'||tokens[i]==='-'){const op=tokens[i++];e=operacion(op,[e,product()]);}return e;}
  const resultado=sum();if(i!==tokens.length)throw new Error('Operación o paréntesis inesperado.');return resultado;
}
export function evaluarExpresion(e: Expresion, variables: Record<string,number>): number {
  let valor: number;
  if(e.tipo==='numero')valor=e.valor;
  else if(e.tipo==='variable')valor=variables[e.nombre];
  else {
    const a=e.args.map(x=>evaluarExpresion(x,variables));
    valor=e.op==='+'?a[0]+a[1]:e.op==='-'?a[0]-a[1]:e.op==='*'?a[0]*a[1]:e.op==='/'?a[0]/a[1]:e.op==='^'?a[0]**a[1]:e.op==='neg'?-a[0]:funciones[e.op](a);
  }
  if(!Number.isFinite(valor))throw new Error('La expresión produjo un valor no finito.');return valor;
}
export function dependeDe(e:Expresion,nombre:string):boolean {return e.tipo==='variable'?e.nombre===nombre:e.tipo==='operacion'?e.args.some(a=>dependeDe(a,nombre)):false;}
