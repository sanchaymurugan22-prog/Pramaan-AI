"""Quantise an ONNX model's weights to 8 bits (unsigned), so it runs on onnxruntime's CPU backend (Stage 8).

    backend/.venv/bin/python scripts/quantize-onnx.py models/src/indicconformer-hi/model.onnx models/stt/indicconformer-hi/model.uint8.onnx

Used for AI4Bharat IndicConformer: its ready-made "int8" file uses signed 8-bit convolution weights, which the
CPU backend cannot run. Unsigned weights (QUInt8) work everywhere; this is what sherpa-onnx uses for its models.
"""

import logging
import sys
from pathlib import Path

from onnxruntime.quantization import QuantType, quantize_dynamic


def main(source: Path, target: Path) -> None:
    logging.getLogger().setLevel(logging.ERROR)  # onnxruntime lists every tensor it leaves unquantised
    target.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(model_input=str(source), model_output=str(target), weight_type=QuantType.QUInt8)
    print(f"Saved {target} ({target.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
