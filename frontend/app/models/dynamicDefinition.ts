import type { HojaMotor } from '../motor/hojasMotor';
import type { ModeloComun } from '../../motores/modelo/contrato';

export type Inventory = { kind: 'total_mass' } | { kind: 'energy'; coordinate: 'U' | 'H' | 'E' } | { kind: 'component_amount'; componentId: number };
export type Dependent = { kind: 'stream_total' | 'heat_flow'; id: string } | { kind: 'component_flow'; id: string; componentId: number };
export type InventoryOperation = { id: string; volumeId: string; inventory: Inventory; mode: 'dynamic' | 'fixed'; reason: string; dependent?: Dependent };
export type DynamicDefinition = { format: 'rage.dynamic-definition'; version: 1; operations: InventoryOperation[] };
export type DynamicFormulation = {
  format: 'rage.dynamic-formulation'; version: 1; modelId: string; scope: string;
  inventories: { id: string; volumeId: string; inventory: Inventory; name: string; unit: string; mode: 'dynamic' | 'fixed'; operationId: string | null; dependent: Dependent | null; options: (Dependent & { dataId: string })[]; steps: { id: string; title: string; latex: string }[] }[];
  variables: { id: string; volumeId: string; role: 'inventory_state' | 'derived_quantity' | 'dependent_unknown' | 'closure_unknown' | 'external_input' | 'specified_data'; unit: string; source: string }[];
  closures: { volumeId: string; kind: 'equilibrio' | 'supuesto'; packageId: string | null; balanceIds: string[]; note: string }[];
  domains: { id: string; volumeId: string; title: string; latex: string; note: string }[];
  diagnostics: { code: string; volumeId: string; message: string }[];
};

type Obj = Record<string, unknown>;
function object(value: unknown): Obj {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected an inventory definition object.');
  return value as Obj;
}
function exact(value: unknown, required: string[], optional: string[] = []) {
  const data = object(value);
  if (required.some(key => !(key in data)) || Object.keys(data).some(key => !required.includes(key) && !optional.includes(key))) throw new Error('Invalid inventory definition fields.');
  return data;
}
function text(value: unknown): value is string { return typeof value === 'string' && value.trim().length > 0; }
function readInventory(value: unknown) {
  const item = exact(value, ['kind'], ['componentId', 'coordinate']);
  if (!['total_mass', 'energy', 'component_amount'].includes(item.kind as string) || (item.kind === 'component_amount' ? !Number.isInteger(item.componentId) || Number(item.componentId) < 1 : 'componentId' in item)) throw new Error('Invalid inventory identity.');
  if (item.kind === 'energy' ? !['U', 'H', 'E'].includes(item.coordinate as string) : 'coordinate' in item) throw new Error('Invalid energy inventory coordinate.');
}
function readDependent(value: unknown) {
  const item = exact(value, ['kind', 'id'], ['componentId', 'dataId']);
  if (!text(item.id) || !['stream_total', 'heat_flow', 'component_flow'].includes(item.kind as string) || (item.kind === 'component_flow' ? !Number.isInteger(item.componentId) || Number(item.componentId) < 1 : 'componentId' in item)) throw new Error('Invalid dependent flow identity.');
  if ('dataId' in item && !text(item.dataId)) throw new Error('Invalid dependent data reference.');
}
export function readDynamicDefinition(value: unknown, model?: ModeloComun): DynamicDefinition {
  const data = exact(value, ['format', 'version', 'operations']);
  if (data.format !== 'rage.dynamic-definition' || data.version !== 1 || !Array.isArray(data.operations) || data.operations.length > 2000) throw new Error('Unsupported inventory definition.');
  const ids = new Set<string>();
  const effective = new Map<string, Obj>();
  for (const value of data.operations) {
    const op = exact(value, ['id', 'volumeId', 'inventory', 'mode', 'reason'], ['dependent']);
    if (!text(op.id) || op.id.length > 160 || ids.has(op.id) || !text(op.volumeId) || !['dynamic', 'fixed'].includes(op.mode as string) || !text(op.reason) || op.reason.length > 2000) throw new Error('Invalid inventory operation.');
    ids.add(op.id); readInventory(op.inventory);
    if (op.dependent !== undefined) {
      readDependent(op.dependent);
      if (op.mode !== 'fixed' || 'dataId' in object(op.dependent)) throw new Error('Only fixed inventories accept dependent bindings.');
    }
    const inventory = op.inventory as Inventory;
    effective.set(JSON.stringify([op.volumeId, inventory.kind, 'componentId' in inventory ? inventory.componentId : 'coordinate' in inventory ? inventory.coordinate : null]), op);
  }
  for (const op of effective.values()) {
    if (op.mode === 'dynamic') continue;
    if (model) {
      const volume = model.volumenes.find(item => item.id === op.volumeId), inventory = op.inventory as Inventory;
      if (!volume || inventory.kind === 'component_amount' && !volume.componenteIds.includes(inventory.componentId)) throw new Error('Inventory owner or component is missing.');
      if (op.dependent) {
        const binding = op.dependent as Dependent;
        const stream = model.corrientes.find(item => item.id === binding.id), heat = model.intercambios.find(item => item.id === binding.id);
        if (binding.kind === 'heat_flow' ? inventory.kind !== 'energy' || !heat || heat.ley.tipo !== 'impuesto' || ![heat.desde, heat.hasta].includes(volume.id)
          : inventory.kind === 'energy' || !stream || ![stream.desde, stream.hasta].includes(volume.id) || stream.desde === stream.hasta || (inventory.kind === 'component_amount' && !stream.componenteIds.includes(inventory.componentId)) || (binding.kind === 'component_flow' ? stream.materia.modo !== 'por_componente' || !(String(binding.componentId) in stream.materia.caudalIds) || inventory.kind === 'component_amount' && binding.componentId !== inventory.componentId : stream.materia.modo === 'por_componente')) throw new Error('Dependent binding does not match the inventory topology.');
      }
    }
  }
  return value as DynamicDefinition;
}

export function readDynamicFormulation(value: unknown): DynamicFormulation {
  const data = exact(value, ['format', 'version', 'modelId', 'scope', 'inventories', 'variables', 'closures', 'domains', 'diagnostics']);
  if (data.format !== 'rage.dynamic-formulation' || data.version !== 1 || !text(data.modelId) || !text(data.scope)) throw new Error('Invalid dynamic formulation header.');
  for (const field of ['inventories', 'variables', 'closures', 'domains', 'diagnostics']) if (!Array.isArray(data[field])) throw new Error('Invalid dynamic formulation collection.');
  const ids = new Set<string>();
  for (const value of data.inventories as unknown[]) {
    const item = exact(value, ['id', 'volumeId', 'inventory', 'name', 'unit', 'mode', 'operationId', 'dependent', 'options', 'steps']);
    for (const key of ['id', 'volumeId', 'name', 'unit']) if (!text(item[key])) throw new Error('Invalid inventory metadata.');
    if (ids.has(item.id as string)) throw new Error('Duplicate inventory.'); ids.add(item.id as string);
    readInventory(item.inventory);
    if (!['dynamic', 'fixed'].includes(item.mode as string) || item.operationId !== null && !text(item.operationId) || !Array.isArray(item.options) || !Array.isArray(item.steps)) throw new Error('Invalid inventory state.');
    if (item.dependent !== null) readDependent(item.dependent);
    item.options.forEach(option => { readDependent(option); if (!text(object(option).dataId)) throw new Error('Dependent options need a data reference.'); });
    for (const row of item.steps) { const step = exact(row, ['id', 'title', 'latex']); if (!Object.values(step).every(text)) throw new Error('Invalid dynamic balance equation.'); }
  }
  for (const row of data.variables as unknown[]) {
    const variable = exact(row, ['id', 'volumeId', 'role', 'unit', 'source']);
    if (!Object.values(variable).every(text) || !['inventory_state', 'derived_quantity', 'dependent_unknown', 'closure_unknown', 'external_input', 'specified_data'].includes(variable.role as string)) throw new Error('Invalid physical variable role.');
  }
  for (const row of data.closures as unknown[]) {
    const closure = exact(row, ['volumeId', 'kind', 'packageId', 'balanceIds', 'note']);
    if (!text(closure.volumeId) || !['equilibrio', 'supuesto'].includes(closure.kind as string) || closure.packageId !== null && !text(closure.packageId) || !text(closure.note) || !Array.isArray(closure.balanceIds) || closure.balanceIds.some(id => !ids.has(id))) throw new Error('Invalid closure references.');
  }
  for (const row of data.domains as unknown[]) if (!Object.values(exact(row, ['id', 'volumeId', 'title', 'latex', 'note'])).every(text)) throw new Error('Invalid inventory domain.');
  for (const row of data.diagnostics as unknown[]) if (!Object.values(exact(row, ['code', 'volumeId', 'message'])).every(text)) throw new Error('Invalid inventory diagnostic.');
  return value as DynamicFormulation;
}

export function definitionOf(model: HojaMotor) {
  return (model.redTermodinamica?.solicitud.derivacion as Record<string, unknown> | undefined)?.dynamicDefinition as DynamicDefinition | undefined ?? model.dynamicDefinition;
}
export function withDefinition(model: HojaMotor, value: DynamicDefinition): HojaMotor {
  readDynamicDefinition(value);
  return { ...model, ...(model.redTermodinamica ? { redTermodinamica: { ...model.redTermodinamica, solicitud: { ...model.redTermodinamica.solicitud, derivacion: { ...(model.redTermodinamica.solicitud.derivacion as Record<string, unknown> | undefined), dynamicDefinition: value } } } } : { dynamicDefinition: value }), resultado: undefined, resultadoRef: undefined };
}
export function ensureInventoryExecution(model: HojaMotor) {
  const definition = definitionOf(model);
  if (!definition) return;
  readDynamicDefinition(definition);
  const effective = new Map(definition.operations.map(op => [JSON.stringify([op.volumeId, op.inventory.kind, 'componentId' in op.inventory ? op.inventory.componentId : 'coordinate' in op.inventory ? op.inventory.coordinate : null]), op]));
  if ([...effective.values()].some(op => op.mode === 'fixed')) throw new Error('Permanent inventory constraints are defined in Model, but constrained dynamic execution is not connected. Review Model before running.');
}
