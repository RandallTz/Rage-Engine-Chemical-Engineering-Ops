"""Compile a typed AST recipe once; bind each instance through its identity map.

The key is the complete alpha-normalized AST, including literal values and
operator order. Identity binding separately includes symbol IDs, state indices
and constant values. This is a numerical lowering cache, not a physical proof.
"""
from functools import lru_cache
import json
from types import SimpleNamespace


@lru_cache(maxsize=4096)
def _generic(recipe):
    from .explicito import SistemaExplicito
    ast = json.loads(recipe)
    symbols = set()
    def visit(value):
        if isinstance(value,dict):
            if value.get('tipo') == 'simbolo': symbols.add(value['id'])
            for item in value.values(): visit(item)
        elif isinstance(value,list):
            for item in value: visit(item)
    visit(ast)
    evaluator = SimpleNamespace(tiempo='__time',valores={},
        indice={s:int(s.removeprefix('__slot')) for s in symbols if s!='__time'})
    evaluator._compilar = lambda tree,label: SistemaExplicito._compilar_uncached(evaluator,tree,label)
    return evaluator._compilar(ast,'cached typed AST recipe')


@lru_cache(maxsize=16384)
def _instance(recipe, identity_map):
    generic = _generic(recipe)
    def evaluate(time,state):
        values = [state[value] if kind=='state' else float.fromhex(value) for _,kind,value in identity_map]
        return generic(time,values)
    return evaluate


def compile_ast(evaluator, expression, label):
    slots = {}
    bindings = []
    def canonical(value):
        if isinstance(value,dict):
            if value.get('tipo') == 'simbolo':
                identity = value['id']
                if identity == evaluator.tiempo:
                    return {'tipo':'simbolo','id':'__time'}
                if identity not in slots:
                    slots[identity] = '__slot'+str(len(slots))
                    bindings.append((identity,'state',evaluator.indice[identity]) if identity in evaluator.indice
                                    else (identity,'constant',float(evaluator.valores[identity]).hex()))
                return {**value,'id':slots[identity]}
            return {key:canonical(item) for key,item in value.items()}
        if isinstance(value,list): return [canonical(item) for item in value]
        return value
    # Unsupported operators retain their existing located messages.
    def supported(value):
        if isinstance(value,dict):
            if 'tipo' in value and value['tipo'] not in (
                    'numero','simbolo','suma','producto','cociente','potencia','funcion'):
                return False
            return all(supported(item) for item in value.values())
        return not isinstance(value,list) or all(supported(item) for item in value)
    if not supported(expression):
        return evaluator._compilar_uncached(expression,label)
    recipe = json.dumps(canonical(expression),sort_keys=True,separators=(',',':'),allow_nan=False)
    return _instance(recipe,tuple(bindings))


def evidence():
    return {'version':1,'generic':_generic.cache_info()._asdict(),
            'instances':_instance.cache_info()._asdict(),
            'rule':'complete alpha-normalized typed AST plus exact symbol/index/constant identity map'}


def clear():
    _generic.cache_clear(); _instance.cache_clear()
