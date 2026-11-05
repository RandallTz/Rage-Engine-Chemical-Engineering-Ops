"""Assessment transport identities survive actual JavaScript JSON round trips."""
import copy
import json
import subprocess

import pytest

from core.compilador.assessment import (
    assess_model, attach_result, read_assessment, result_signature,
)
from core.compilador.compilador import resolver
from core.resultados import leer_resultados
from test_explicit_initialization import fixture


def publication():
    model = fixture([('1', 'kg')])
    return attach_result(assess_model(model), resolver(model))


def test_javascript_roundtrip_keeps_scientific_reader_acceptance():
    result = publication()
    encoded = subprocess.run(
        ['node', '-e', "process.stdin.setEncoding('utf8');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s))));"],
        input=json.dumps(result), text=True, capture_output=True, check=True,
    ).stdout
    restored = json.loads(encoded)
    assert restored['procedencia']['assessment']['resultSignatureVersion'] == 2
    leer_resultados(restored)


def test_legacy_and_explicit_legacy_signatures_remain_readable():
    result = publication()
    evidence = result['procedencia']['assessment']
    evidence.pop('resultSignatureVersion')
    evidence['resultSignature'] = result_signature(result)
    leer_resultados(result)
    evidence['resultSignatureVersion'] = 1
    leer_resultados(result)


@pytest.mark.parametrize('version', [0, 3, None, True, '2', 2.0])
def test_unknown_signature_versions_reject(version):
    result = publication()
    evidence = result['procedencia']['assessment']
    evidence['resultSignatureVersion'] = version
    with pytest.raises(ValueError, match='signature version'):
        read_assessment(evidence, result=result)


def test_signature_version_requires_digest_and_tampering_rejects():
    result = publication()
    evidence = copy.deepcopy(result['procedencia']['assessment'])
    evidence.pop('resultSignature')
    with pytest.raises(ValueError, match='signature version'):
        read_assessment(evidence)
    result['series'][0]['valores'][0] += 0.1
    with pytest.raises(ValueError, match='does not match'):
        read_assessment(result['procedencia']['assessment'], result=result)


def test_numeric_canonicalization_and_type_separation():
    wrap = lambda value: {'procedencia': {}, 'value': value}
    for a, b in [(1, 1.0), (0, -0.0), (1e-7, 0.0000001)]:
        assert result_signature(wrap(a), 2) == result_signature(wrap(b), 2)
    assert result_signature(wrap(1), 2) != result_signature(wrap(True), 2)
    assert result_signature(wrap(1), 2) != result_signature(wrap({'$binary64': '3ff0000000000000'}), 2)
