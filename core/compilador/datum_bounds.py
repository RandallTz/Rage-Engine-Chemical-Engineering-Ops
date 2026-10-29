"""Conservative finite interval admission for prescribed temporal data.

Intervals enclose the expression on the complete declared horizon, with outward
floating-point rounding. Subdivision reduces dependency overestimation; a finite
budget fails closed rather than treating a sample grid as a range proof.
"""
import math


class BoundsUnavailable(ValueError):
    pass


def _out(lo, hi):
    if not math.isfinite(lo) or not math.isfinite(hi):
        raise BoundsUnavailable('The expression has no finite enclosure.')
    return math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)


def interval(node, time):
    if node[0] == 'num':
        return node[1], node[1]
    if node[0] == 'var':
        if node[1] != 't':
            raise BoundsUnavailable('Only SI time is admitted in prescribed data.')
        return time
    op, children = node[1:]
    args = [interval(child, time) for child in children]
    a, b = args[0]
    if op == 'neg':
        return -b, -a
    if op in ('+', '-', '*', '/'):
        c, d = args[1]
        if op == '+':
            return _out(a+c, b+d)
        if op == '-':
            return _out(a-d, b-c)
        if op == '/':
            if c <= 0 <= d:
                raise BoundsUnavailable('A denominator may reach zero.')
            c, d = _out(1/d, 1/c)
        products = (a*c, a*d, b*c, b*d)
        return _out(min(products), max(products))
    if op == '^':
        c, d = args[1]
        if c != d:
            raise BoundsUnavailable('A variable exponent is not bounded by this admission operation.')
        if c == 0:
            return 1., 1.
        if c < 0 and a <= 0 <= b or not float(c).is_integer() and a < 0:
            raise BoundsUnavailable('The power may leave its real finite domain.')
        values = (a**c, b**c)
        lo, hi = min(values), max(values)
        if c > 0 and float(c).is_integer() and int(c) % 2 == 0 and a <= 0 <= b:
            lo = 0.
        lower, upper = _out(lo, hi)
        return (max(0., lower), upper) if lo == 0 else (lower, upper)
    if op in ('sin', 'cos'):
        if max(abs(a), abs(b)) > 1e12:
            raise BoundsUnavailable('Trigonometric argument is too large for reliable range reduction.')
        if b-a >= 2*math.pi:
            return -1., 1.
        offset = math.pi/2 if op == 'sin' else 0.
        function = math.sin if op == 'sin' else math.cos
        values = [function(a), function(b)]
        start = math.ceil((a-offset)/math.pi)
        stop = math.floor((b-offset)/math.pi)
        values.extend((-1.)**k for k in range(start, stop+1))
        lo, hi = _out(min(values), max(values))
        return max(-1., lo), min(1., hi)
    if op == 'exp':
        lo, hi = _out(math.exp(a), math.exp(b))
        return max(0., lo), hi
    if op == 'log':
        if a <= 0:
            raise BoundsUnavailable('The logarithm may leave its positive domain.')
        return _out(math.log(a), math.log(b))
    if op == 'sqrt':
        if a < 0:
            raise BoundsUnavailable('The square root may leave its nonnegative domain.')
        lo, hi = _out(math.sqrt(a), math.sqrt(b))
        return max(0., lo), hi
    if op == 'abs':
        return (0. if a <= 0 <= b else min(abs(a), abs(b))), max(abs(a), abs(b))
    if op == 'min':
        return min(x[0] for x in args), min(x[1] for x in args)
    if op == 'max':
        return max(x[0] for x in args), max(x[1] for x in args)
    if op == 'step':
        return (0., 0.) if b < 0 else (1., 1.) if a >= 0 else (0., 1.)
    raise BoundsUnavailable('No interval operation for '+op)


def certify(datum, final_time, *, positive=False, nonnegative=False, derivative=False):
    from .compilador import AdmissionError
    pending = [(0., final_time, 0)]
    visits = 0
    while pending:
        left, right, depth = pending.pop()
        middle = left+(right-left)/2
        # A concrete witness distinguishes invalid values from inability to
        # establish an enclosure. Units are checked per role before this call.
        for t in (left, middle, right):
            value = datum.d_dt(t) if derivative else datum(t)
            if positive and value <= 0 or nonnegative and value < 0:
                raise AdmissionError('invalid_physical_value',
                    f'The declared physical range is violated at t={t:g} s.', datum.path,
                    native_code='MOTOR_ENS_FUERA_DE_MAGNITUD')
        try:
            lo, hi = interval(datum.derivada if derivative else datum.arbol, (left, right))
            offset = 0. if derivative else datum.desp
            lo, hi = _out(datum.factor*lo+offset, datum.factor*hi+offset)
            valid = (not positive or lo > 0) and (not nonnegative or lo >= 0)
        except (BoundsUnavailable, ArithmeticError, ValueError) as error:
            valid = False
            reason = str(error)
        else:
            reason = 'The enclosure crosses the declared physical range.'
        if valid:
            continue
        visits += 1
        if depth >= 24 or visits >= 8192 or middle in (left, right):
            raise AdmissionError('unbounded_time_data',
                f'Cannot certify the datum over [{left:g}, {right:g}] s: {reason}', datum.path,
                native_code='MOTOR_ENS_EXPRESION')
        pending.extend([(middle, right, depth+1), (left, middle, depth+1)])
