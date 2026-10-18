export type OperacionRed={controller:AbortController};
/** Only the latest request can publish or clear its busy indicator. */
export class ControlOperacionRed{
  private actual:OperacionRed|null=null;
  iniciar(){this.cancelar();const op={controller:new AbortController()};this.actual=op;return op;}
  vigente(op:OperacionRed){return this.actual===op&&!op.controller.signal.aborted;}
  cancelar(){this.actual?.controller.abort();}
  finalizar(op:OperacionRed){if(this.actual!==op)return false;this.actual=null;return true;}
}
