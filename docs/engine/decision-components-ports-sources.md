# Volumes, boundaries, connections and equipment

Date: 12 October 2026. Addressed to: Astra's next review and the later implementation coordinated with Claude. (This decision belongs to the lab's bench editor; it is kept with the engine documents because its component/port/source abstraction is the one the Engine follows.)

**Executable assignment for Claude:** [docs/history/frontend/assignment-claude-topology-boundaries-and-sources.md](../history/frontend/assignment-claude-topology-boundaries-and-sources.md). This document keeps the architectural context; the backend scope to be run is in that separate assignment.

## State and scope

**Implemented in this revision:** creating a volume or reactor creates only that piece. It creates no feed, outlet or connections. This applies to the initial button, the palette, dragging and creating a copy of a volume. The three-slot reservations that came with that behaviour were removed. Saved benches and explicit templates keep their elements.

**Editor update:** insertion through a contextual action and connecting volumes without deleting boundaries were also delivered. Evidence and limits in [INTEGRACION_INSERCION_MESA.md](../../frontend/INTEGRACION_INSERCION_MESA.md). The rest of this document keeps the proposed architectural decisions. The engine was not modified and no new physical combinations were enabled. Starting reference: §26 of `docs/ENTREGA_LABORATORIO_CODEX.md`, revision 14.

Goal: to be able to build the model the user intends, see its exchanges and complete its data, without forcing them to think about the serializer's internal structure or filling the canvas with details.

## 1. Central decision

The common unit is a **mathematical component with variables, equations and ports**. A control volume is one class of component; not every component needs to store matter or energy.

| Role | What it represents | Example | What must not be invented |
|---|---|---|---|
| Domain with storage | A region whose state evolves through balances | The tank's water; a wall with heat capacity | Capacity, perfect mixing, geometry or undeclared properties |
| Boundary | Interaction with a part of the surroundings that is not modelled internally | Feed; discharge; known heat | A fictitious volume or the source's dynamics |
| Connection or exchange relation | Transport between components; it can include a constitutive law | A shared stream; thermal contact with a conductance | Storage of its own in an ideal line |
| Equipment | A specialized component, or a grouping of components with external ports | Pump; heater; heat exchanger | That its icon silently determines all its physics |

A wall without storage can be algebraic. A pipe can be an ideal connection, a loss element or several discretized volumes: they are different models of that pipe. Grouping an existing model as equipment only changes its presentation; adding storage or losses changes its equations and requires new data.

Do not require three executed balances of every symbol: a thermal wall does not need a fictitious species balance; a heat boundary does not need its own inventory. Matter, energy and momentum are conserved in the corresponding domains, with explicit reductions and approximations. The engine must declare which families it really formulates and solves.

## 2. Heating a tank: choosing how much is modelled

### A. The power the water receives is known

Declare an external contribution `Q(t)` to the tank, for example 1000 W. The tank's equation includes `+Q`. How the heater produces that power, or what temperature it has, is not calculated.

Recommended UI: select the tank → Energy → Add external heat. A compact thermal marker next to the edge indicates the contribution; selecting it allows editing it. It must be possible to show it as a separate symbol if the user wants to organize it that way.

**The marker, the panel field and the separate symbol are views of the same object with a single identifier.** Do not create at the same time an independent local specification and another connected source that would add the heat twice. Changing the view does not modify the model or its count.

First implementation: reuse the current `calor` piece and its connection through a visual projection; do not create a second contract for sources. Values are assigned in Experimentar; the diagram defines that this interaction exists and gives access to its variables.

### B. The temperature of the hot surroundings is known

Declare a thermal boundary `T_ext` and a relation, for example `Q = G(T_ext - T_tank)`. Here Q is calculated. It is not the same as fixing the tank's T or also imposing an independent Q.

Before offering this option, check that a backend combination exists that assembles it. Do not reinterpret the current "T imposed on the volume" as an external temperature. A new thermal boundary needs its own contract, references and validation.

### C. The cooling of the hot circuit is to be calculated

Model the hot fluid as another domain with an energy balance and connect it thermally to the tank's water. The exchange appears with opposite signs in both balances and cancels in the global balance. The streams of the two circuits do not mix.

The wall is added when its thermal resistance or storage matters. Do not always require three fluid volumes: the tank's water and the coil's fluid are two material domains; the wall is a solid domain if it is represented explicitly. A resistance without storage does not need an initial temperature of its own.

The available vapor chamber is the bounded regime documented in §24: do not present it as a general transient two-phase volume.

### Changing the level of detail

Going from imposed Q to a modelled hot circuit is **replacing the boundary hypothesis with another model**, not unfolding a card. Show the replacement, remove the earlier imposition for that same interaction, ask for the new data and validate again. Keep the other independent sources the user added on purpose.

## 3. A pump is not simply a "momentum source"

A pump represents the conversion of mechanical work into fluid energy and a pressure rise, with its losses. It must have fluid ports, a hydraulic relation and a representation of the work; it can include storage if that level of detail is declared.

A reduced description can be algebraic: continuity, a relation between flow and pressure rise, an energy balance and a power or efficiency relation. In the ideal steady incompressible case the hydraulic power is `Δp · volumetric_flow`; do not use that expression as a universal law of every machine. Nor identify pressure with momentum, or shaft work with heat.

An ideal imposed-pressure pump and a pump with its own curve are different closures. Do not impose flow, pressure rise and power simultaneously as independent data without analysing compatibility and degrees of freedom.

**Do not implement a pump in this assignment.** The momentum/hydraulic balance still needs a contract and validation. The current work piece does not turn the engine into a pump simulator. The criterion serves to design the abstraction without promising capabilities that do not exist.

## 4. The connection must keep its physical meaning

- A material stream between two systems is one shared stream: the outlet of one and the inlet of the other. It carries species and energy; do not duplicate the flow as two independent data.
- A thermal interface exchanges heat. It carries no mass and introduces no additional advective enthalpy.
- An external source appears in the global balance; an internal exchange cancels. A reaction transforms species inside the domain and does not thereby become an external stream.
- Ports have a stable semantic identity. Moving the point along the edge or changing the orthogonal routing of the line does not change the equations.
- The arrow defines an orientation. Accepting flow reversal depends on the model and its laws; do not enable it just because the editor allows reversing the drawing.
- Equalizing temperatures through an ideal contact is not the same as connecting two temperatures through a finite conductance. The assembler must distinguish the junction from the exchange law.
- A newly created volume is a draft. Do not conclude automatically that it is closed or that its missing exchanges are zero. When the user chooses a closed system, record that decision explicitly.

## 5. A concrete incident when extending a chain

The automatic substitution of `conectar()` removed the terminal outlets of the first system and the terminal inlets of the second, together with their specifications. **It has been removed:** connecting keeps the existing boundaries. It is a different fix from creating volumes without automatic ends.

Separate two actions:

1. **Connect systems:** add a shared stream without deleting existing boundaries or data. If the result is an unsupported branching, keep the drawing and point out the limitation; do not correct the physics by deleting a branch.
2. **Insert a system into a stream:** an explicit action on the line, or a drag with a preview. For `feed → V1 → outlet`, inserting V2 produces `feed → V1 → V2 → outlet`. It keeps the feed, the outlet and their identified data; it adds an internal stream and a volume with its pending data.

The insertion must be a single reversible operation. Before implementing it, fix a migration table of identities and specifications:

- The external feed keeps its identity and declared conditions.
- The external outlet keeps its identity. Its flow data stay as specifications of the final destination and are revalidated; do not confuse them with a datum that belonged to the old volume.
- Conditions tied to the old connection, to V1's outlet state or to a hydraulic law must not be moved without an explicit correspondence. Mark what needs review.
- V1's data and initial conditions are kept. V2 needs its own; do not copy them to look complete.
- The shared stream has a single identity, which appears in both balances and in the catalog.
- Every edit invalidates the current validation and keeps the earlier result only as history.

Do not solve this problem by forcing the outlet to be deleted and recreated, or by adding a long wizard. A contextual "Insert system" action and a preview are enough.

## 6. Assembly and degrees of freedom

Each component contributes variables, equations, constitutive relations, domain conditions and ports to the same residual `R(t, z, dz/dt, a, p) = 0`. Connections contribute relations and shared terms. This is the target architecture; the current engine accepts a bounded set of combinations and is not yet an arbitrary DAE assembler.

To look for a steady state, cancel the derivatives of the states that are part of that same model and apply compatible steady boundaries. Do not create alternative physical balances for that study. Do not assume uniqueness, stability, or that every transient will converge to a steady solution.

The backend's count remains the authority. Adding a line, a source or storage can change the unknowns and relations needed. The frontend does not obtain degrees of freedom by subtracting visible fields, and does not promise that every drawable combination is solvable.

The Datum/Calculate choice is offered only where the contract says the role of the variable can be changed. A constitutive parameter does not automatically become an identification unknown by leaving it empty.

## 7. Proposed implementation order

### Phase 1: topology editing without data loss

Next priority. Extract pure editor operations for connecting and inserting; keep identities; atomic undo/redo; update references and clean up only elements explicitly removed. Add regressions with non-trivial data at the boundaries. It does not require extending the physics of the chain already supported.

Also review the local limit of eight pieces: it currently counts internal nodes, streams included. Do not raise it blindly; separate the editor's limit, the contract's limit and the capabilities per combination. Do not present the number as a universal limitation of the engine.

### Phase 2: one edit for external contributions

A compact projection of the `calor` piece, linked to its current identifier. Editing from the tank or from the symbol; selection highlights its single term in energy. When energy is switched off or adiabatic is declared, point out the contradiction with the existing source and allow resolving it explicitly; do not hide or delete it.

Sources, lines and equipment must be distinguishable by shape and icon; colour is only support. Detailed information appears on selection. Do not add permanent paragraphs to the canvas or new panels open by default.

### Phase 3: a contract of reusable components and equipment

First inventory what the engine already supports: volumes, wall, chamber, streams and contacts. Define common roles and ports as a layer on top of the existing assembly. The final schema must be agreed with the backend; the conceptual names in this document are not new fields authorized to be sent to endpoints.

Grouping a submodel must keep its equations, parameters, references and results. Opening the equipment shows those same components. Introducing an external thermal boundary or a pump needs independent physics deliveries; do not block the first two phases on them.

## 8. Acceptance criteria

1. Creating a volume, reactor or copy creates no boundaries. Saving/reopening does not add them again.
2. Connecting V1 and V2 does not remove the existing feed or outlet. An unsupported topology keeps what was drawn and explains its block when validating.
3. Inserting V2 before an outlet keeps that outlet's identifier and data, identifies the new pending items and is undone in one step.
4. After completing the data, solve → insert → complete → solve works; a late response from the earlier setup does not replace the new one.
5. Heat from the panel and heat from the symbol edit the same object. Changing only the representation keeps the physical request, the count and `modelo_id`.
6. In a closed tank of constant heat capacity with imposed Q, the independent reference is `T(t)=T0+Q·t/C` within its domain. In a model with variable capacities an appropriate reference is used, not this formula for convenience.
7. Two domains in thermal contact conserve energy; the internal exchange cancels and both temperatures are evaluated at the same instant.
8. External source plus internal interface are each counted once. The equations view identifies their origin and signs.
9. A new representation does not enable unsupported physics. The pump is not offered as executable until its delivery is complete.

## 9. Evidence and references

Checks run for the small change already implemented: `npm test`, `npx tsc --noEmit` and ESLint on the two modified application files. The containers test covers a volume and a reactor without ends; it keeps the checks of the projection of explicit streams. The water walkthrough test was adapted to create its boundaries explicitly.

The additional run of `node verificar_recorrido_agua.mjs` reached the HTTP call but could not connect because of an EACCES of the restricted environment. The automatic review of the run with access to the service failed because of a request limit (429); that test was not run against the engine in this revision. Do not attribute a physical result verified today to it.

Browser review: a new empty bench → add a first volume → add a second volume from the palette. Two volumes appear and no stream or boundary is created automatically. The drag check shares the same creation function and was reviewed in code; no manual test of that gesture is claimed.

Observation of the first review: "Ordenar piezas" (arrange pieces) partly overlapped two isolated volumes. In that evidence they were separated by hand. **Fixed in the insertion delivery:** arranging considers the declared height and the usual separation of the volumes. Historical evidence: `preview-volumenes-sin-fronteras.jpg` (a local screenshot, not kept in git).

Design references consulted, as precedents and not as a requirement to adopt Modelica:

- [Modelica: thermal sources](https://doc.modelica.org/om/Modelica.Thermal.HeatTransfer.Sources.html): distinguishes temperature boundaries from heat-flow boundaries.
- [Modelica: pump with a mechanical connection](https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Fluid.Machines.Pump.html): combines fluid and shaft ports, machine relations and options for mass and energy dynamics.

These references support separating physical functions. The compact UI, the insertion of systems and the incremental plan are proposals specific to this project.
