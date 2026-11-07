"""Build the recorded R1 → drum → R2 document for the HTTP verifier.

The first run may spend several minutes authoring the drum. No numerical
reference values or product-library examples are created here.
"""
import json
from pathlib import Path

from demo02_cstr import frozen_model
from flowsheet_inputs import drum4_model, flowsheet_model


def main():
    destination = Path(__file__).resolve().parents[1] / '.tmp' / 'flowsheet-http' / 'source.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(flowsheet_model(frozen_model(), drum4_model())), encoding='utf-8')
    print(f'Wrote {destination}')


if __name__ == '__main__':
    main()
