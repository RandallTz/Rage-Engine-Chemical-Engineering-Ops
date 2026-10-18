import type { Coordenadas } from './operadores';

export default function DiagramaCoordenadas({ tipo }: { tipo: Coordenadas }) {
  return <svg viewBox="0 0 72 64" width="64" height="54" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
    {tipo === 'cartesianas' ? <>
      <path d="M15 24 38 13 59 24 59 48 36 59 15 47Z M15 24 36 36 59 24 M36 36V59 M38 13V35" />
      <path d="M15 47H7 M59 48 66 52 M38 13V5" />
      <g fill="currentColor" stroke="none" fontSize="8"><text x="3" y="44">y</text><text x="64" y="60">x</text><text x="42" y="9">z</text></g>
    </> : tipo === 'cilindricas' ? <>
      <ellipse cx="34" cy="35" rx="24" ry="19" /><ellipse cx="34" cy="35" rx="12" ry="9" strokeDasharray="2 3" />
      <path d="M34 35 56 25 M34 35H59 M46 35Q46 29 43 29 M34 35V6" />
      <g fill="currentColor" stroke="none" fontSize="8"><text x="44" y="23">r</text><text x="49" y="33">φ</text><text x="38" y="10">z</text></g>
    </> : <>
      <circle cx="34" cy="34" r="24" /><ellipse cx="34" cy="34" rx="24" ry="8" /><ellipse cx="34" cy="34" rx="9" ry="24" strokeDasharray="2 3" />
      <path d="M34 34 52 18 M34 34V5 M34 21Q41 21 43 25" />
      <g fill="currentColor" stroke="none" fontSize="8"><text x="48" y="27">r</text><text x="38" y="20">θ</text><text x="53" y="44">φ</text></g>
    </>}
  </svg>;
}
