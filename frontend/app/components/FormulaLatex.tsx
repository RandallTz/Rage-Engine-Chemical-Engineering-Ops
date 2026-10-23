"use client";
import { useMemo } from "react";
import katex from "katex";

export default function FormulaLatex({ latex, lectura, bloque=false }: { latex:string; lectura:string; bloque?:boolean }) {
  const html=useMemo(()=>{
    try { return katex.renderToString(latex,{displayMode:bloque,throwOnError:true,trust:false,strict:"error",output:"htmlAndMathml"}); }
    catch { return null; }
  },[latex,bloque]);
  return html ? <span className={bloque?"formula-latex formula-latex-block":"formula-latex"} dangerouslySetInnerHTML={{__html:html}}/> : <span role="math" aria-label={lectura}>{lectura}</span>;
}
