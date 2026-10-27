'use client';
import type {LinePlot,TernaryPlot} from './multicomponentDiagrams';
import {formatearNumeroMotor as num} from './formatearNumeroMotor';
import styles from './equilibrioMotor.module.css';

/** Ternary liquid-liquid diagram in plain SVG. Every mark is a published composition placed barycentrically:
 * order[0] bottom-left, order[1] bottom-right, order[2] top. Lines join consecutive certified points of one
 * binodal side; nothing is joined across a branch end, the plait point or a boundary. */
const SIDE=520,MARGIN=48,HEIGHT=SIDE*Math.sqrt(3)/2;
export const TERNARY_GEOMETRY={side:SIDE,margin:MARGIN,height:HEIGHT};
export function ternaryPixel(x:number[]){return {x:MARGIN+SIDE*(x[1]+x[2]/2),y:MARGIN+HEIGHT*(1-x[2])};}
const pt=(x:number[])=>{const p=ternaryPixel(x);return `${p.x.toFixed(3)},${p.y.toFixed(3)}`;};
const COLORS={a:'#3d6580',b:'#9b7048',tie:'#a9b3a0',plait:'#524373',edge:'#536844',triangle:'#8b4550',line:'#18261d'};

export default function TernaryLiquidLiquidChart({plot,names,line}:{plot:TernaryPlot;names:string[];line?:LinePlot}){
  const W=SIDE+2*MARGIN,H=HEIGHT+2*MARGIN+10;
  const grid=[0.2,0.4,0.6,0.8].flatMap(f=>[[[f,1-f,0],[f,0,1-f]],[[1-f,f,0],[0,f,1-f]],[[1-f,0,f],[0,1-f,f]]]);
  return <figure className={styles.chart} style={{height:'auto'}} aria-label="Ternary liquid-liquid diagram">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" width="100%" style={{maxHeight:560}} data-chart="ternary">
      <rect width={W} height={H} fill="#fcfbf8"/>
      {grid.map(([a,b],k)=><line key={k} x1={ternaryPixel(a).x} y1={ternaryPixel(a).y} x2={ternaryPixel(b).x} y2={ternaryPixel(b).y} stroke="#e4e6dc" strokeWidth={0.8}/>)}
      <polygon points={[[1,0,0],[0,1,0],[0,0,1]].map(pt).join(' ')} fill="none" stroke="#8c957f" strokeWidth={1.4}/>
      <text x={MARGIN-6} y={MARGIN+HEIGHT+22} fontSize={13} textAnchor="start">{names[0]}</text>
      <text x={MARGIN+SIDE+6} y={MARGIN+HEIGHT+22} fontSize={13} textAnchor="end">{names[1]}</text>
      <text x={MARGIN+SIDE/2} y={MARGIN-14} fontSize={13} textAnchor="middle">{names[2]}</text>
      {plot.tieLines.map(t=><line key={t.id} data-kind="tie-line" data-id={t.id} x1={ternaryPixel(t.a).x} y1={ternaryPixel(t.a).y} x2={ternaryPixel(t.b).x} y2={ternaryPixel(t.b).y} stroke={COLORS.tie} strokeWidth={0.6}/>)}
      {plot.sides.map(s=><polyline key={`${s.branchId}/${s.phase}`} data-kind="binodal" data-branch={s.branchId} data-phase={s.phase} points={s.points.map(p=>pt(p.x)).join(' ')} fill="none" stroke={s.phase==='liquid-a'?COLORS.a:COLORS.b} strokeWidth={1.8}/>)}
      {plot.edges.map(e=><g key={e.id} data-kind="binary-edge" data-id={e.id}>
        <line x1={ternaryPixel(e.a).x} y1={ternaryPixel(e.a).y} x2={ternaryPixel(e.b).x} y2={ternaryPixel(e.b).y} stroke={COLORS.edge} strokeWidth={1.4} strokeDasharray="4 3"/>
        {[e.a,e.b].map((x,k)=><circle key={k} data-mark="edge-liquid" cx={ternaryPixel(x).x} cy={ternaryPixel(x).y} r={3.5} fill={COLORS.edge}/>)}
      </g>)}
      {plot.triangles.map(t=><polygon key={t.id} data-kind="three-phase" data-id={t.id} points={t.x.map(pt).join(' ')} fill={COLORS.triangle} fillOpacity={0.15} stroke={COLORS.triangle} strokeWidth={1.4}/>)}
      {plot.plaitPoints.map(p=><circle key={p.id} data-kind="plait-point" data-id={p.id} cx={ternaryPixel(p.x).x} cy={ternaryPixel(p.x).y} r={5} fill={COLORS.plait} stroke="#fff" strokeWidth={1.2}/>)}
      {line&&line.start.length===3&&<g data-kind="composition-line">
        <line data-mark="line-ends" x1={ternaryPixel(line.start).x} y1={ternaryPixel(line.start).y} x2={ternaryPixel(line.end).x} y2={ternaryPixel(line.end).y} stroke={COLORS.line} strokeWidth={1} strokeDasharray="2 3"/>
        {line.boundaries.flatMap(b=>[b.before,b.after].map((x,k)=><rect key={`${b.id}/${k}`} data-mark="boundary-feed" data-id={b.id} x={ternaryPixel(x).x-3} y={ternaryPixel(x).y-3} width={6} height={6} fill={COLORS.line}/>))}
      </g>}
    </svg>
    <figcaption className={styles.legend}>
      <span>Mole fractions [mol/mol]</span><span><i style={{background:COLORS.a}}/>Binodal · liquid a</span><span><i style={{background:COLORS.b}}/>Binodal · liquid b</span><span><i style={{background:COLORS.tie}}/>Tie lines ({plot.tieLines.length})</span>
      {plot.plaitPoints.length>0&&<span>● Plait point</span>}{plot.edges.length>0&&<span>- - Binary-edge pair</span>}{plot.triangles.length>0&&<span>▲ L–L–V triangle</span>}{line&&line.start.length===3&&<span>■ Line boundaries</span>}
    </figcaption>
  </figure>;
}

/** Phase fractions along the composition line: one marker per published phase of each certified row; boundaries
 * are drawn as their bisection interval. Rows are not joined, because phase identity is not tracked between rows. */
const LW=560,LH=240,LM={l:46,r:16,t:14,b:36};
export function linePixel(l:number,fraction:number){return {x:LM.l+(LW-LM.l-LM.r)*l,y:LM.t+(LH-LM.t-LM.b)*(1-fraction)};}
export function CompositionLineChart({plot}:{plot:LinePlot}){
  return <figure className={styles.chart} style={{height:'auto'}} aria-label="Phase fractions along the composition line">
    <svg viewBox={`0 0 ${LW} ${LH}`} role="img" width="100%" data-chart="composition-line">
      <rect width={LW} height={LH} fill="#fcfbf8"/>
      {[0,0.25,0.5,0.75,1].map(v=><g key={v}>
        <line x1={linePixel(0,v).x} x2={linePixel(1,v).x} y1={linePixel(0,v).y} y2={linePixel(0,v).y} stroke="#e4e6dc"/>
        <text x={LM.l-6} y={linePixel(0,v).y+4} fontSize={10} textAnchor="end">{num(v)}</text>
        <text x={linePixel(v,0).x} y={LH-LM.b+14} fontSize={10} textAnchor="middle">{num(v)}</text>
      </g>)}
      <text x={(LW+LM.l)/2} y={LH-4} fontSize={11} textAnchor="middle">l (0 = start, 1 = end)</text>
      <text transform={`translate(12,${(LH-LM.b+LM.t)/2}) rotate(-90)`} fontSize={11} textAnchor="middle">Phase fraction [mol/mol]</text>
      {plot.boundaries.map(b=><rect key={b.id} data-kind="boundary" data-id={b.id} x={linePixel(b.l[0],1).x-0.75} y={LM.t} width={linePixel(b.l[1],1).x-linePixel(b.l[0],1).x+1.5} height={LH-LM.t-LM.b} fill="#8b4550" fillOpacity={0.35}/>)}
      {plot.rows.flatMap(r=>r.phases.map((p,k)=><circle key={`${r.id}/${k}`} data-kind="row-phase" data-id={r.id} data-phase-index={k} cx={linePixel(r.l,p.fraction).x} cy={linePixel(r.l,p.fraction).y} r={2.2} fill={p.kind==='vapor'?'#9b7048':'#3d6580'}/>))}
    </svg>
    <figcaption className={styles.legend}><span><i style={{background:'#3d6580'}}/>Liquid phase fraction</span><span><i style={{background:'#9b7048'}}/>Vapor phase fraction</span>{plot.boundaries.length>0&&<span>▮ Located phase-set boundary</span>}</figcaption>
  </figure>;
}
