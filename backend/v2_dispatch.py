"""Server-selected v2 HTTP execution; rejection never selects another solver."""
import os

EXECUTOR_ENV = 'RAGE_V2_ASSEMBLY_EXECUTOR'


def _dispatch(operation, request=None):
    configured = os.environ.get(EXECUTOR_ENV)
    mode = 'common' if configured is None else configured
    if mode not in ('common', 'native'):
        raise RuntimeError(EXECUTOR_ENV+' must be common or native; no fallback was selected.')
    if mode == 'common':
        from backend import v2_compatibility
        run = getattr(v2_compatibility, operation)
    else:
        from backend import motor_ensamblaje_v2
        run = {'capabilities': motor_ensamblaje_v2.capacidades_v2,
               'validate': lambda value: motor_ensamblaje_v2.validar_v2(value)[0],
               'resolve': motor_ensamblaje_v2.resolver_v2}[operation]
    # No catch-and-retry: rejection and exceptions belong to the selected path.
    response = run() if operation == 'capabilities' else run(request)
    return {**response, 'executionProvenance': {
        'version': 1, 'path': 'common-compiler' if mode == 'common' else 'native-v2',
        'selection': 'default' if configured is None else 'server-override'}}


def capabilities():
    return _dispatch('capabilities')


def validate(request):
    return _dispatch('validate', request)


def resolve(request):
    return _dispatch('resolve', request)
