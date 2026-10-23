# Active equations and mechanical conditions

14 October 2026. Changes only in `/motor`; backend and lab not modified.

## Pressure

`FormulacionEnergia.presionUniforme` means `p(x,t)=P(t)`. It does not turn P into a datum, does not fix its value and does not imply constancy in time.

The new optional field `presionPrescrita` expresses `P(t)=P_ext(t)`. New formulations initialize it to false. Choosing a given external pressure also declares the uniform mechanical reduction. Removing that condition keeps the uniformity and the saved values; the mechanical relation stays pending. A prescribed pressure with the uniformity removed is diagnosed as incompatible with the current reduction.

Old sheets without this field keep the earlier interpretation: uniform pressure with ports or a moving boundary had a given pressure. Reading normalizes each step and its redo history without mutating the sheet or changing its saved signature. An explicit false is never replaced by the old interpretation.

The dynamic preparer uses the explicit condition to build `frontera`. The new field does not extend capabilities or enable routes. In particular, uniform pressure in a rigid domain does not automatically add a prescribed pressure to the UV closure. A pressure condition that was really chosen is kept as an additional constraint.

## Volume

- `V_geom`: the fixed geometry of the integration domain; a datum with a unit.
- `V_ocup`: the volume occupied by the fluid; in the manual constant-density model it is `m/rho_*`.
- `V`: the volume of the integration domain. The existing manual reduction takes `V=V_ocup`; this equality now appears explicitly.

With a fixed domain, the fluid filling it completely and constant density, compatibility requires `dm/dt=0`. It is not a consequence of rigidity alone. No model of free space, level or maximum vessel capacity has been added; the geometric data are not interpreted as thermodynamic properties or as a maximum capacity.

## Final equations

`ecuacionesSistemaEnergia.ts` generates the active relations from the shared formulation. The final view and the solver's provenance consume that list. Stored energy, manual closure, pressure, volume, flow enthalpy/work and boundary work are shown according to the real choices. The integral definitions of active terms go in a single drop-down; those of removed terms do not appear in that list.

`donanteCorrienteEnergia` shares the donor selection between required fields and the final representation. Known constant flows use the external T or the volume's T directly. Flows that can reverse show the condition by sign, without inventing an independent outlet temperature.

Identities and consequences are not additional independent equations. This change does not modify the structural count and does not certify rank, phase state or IAPWS dynamics. The point thermodynamic query stays separate from the manual closure.

## Verification

`verificar_relaciones_energia.mjs` covers migration without modifying data/signature, identical initial values and RHS in old sheets, the difference between uniform and imposed pressure, a pending mechanical condition, geometry/occupied volume, donor selection, reversal, removed terms and the match between representation and provenance. It is part of `test:motor-fundamental`.

Claude's dynamic delivery remains the single contract [docs/history/frontend/contract-claude-assembly-dynamic-engine.md](../history/frontend/contract-claude-assembly-dynamic-engine.md). No second thermodynamic solver has been implemented and its boundary schema has not changed.
