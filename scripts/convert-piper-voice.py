"""Make a Piper voice usable by sherpa-onnx, 8-bit (Stage 8). Used for Telugu, which sherpa-onnx does not
package yet. Run by scripts/download-models.py; by hand:

    backend/.venv/bin/python scripts/convert-piper-voice.py models/src/piper/te_IN-padmavathi-medium.onnx \
        models/tts/vits-piper-te_IN-padmavathi-medium-int8

The same three steps as sherpa-onnx's own scripts (scripts/piper/add_meta_data.py, dynamic_quantization.py):
  1. tokens.txt from the voice's phoneme table (<voice>.onnx.json)
  2. the facts sherpa-onnx needs written into the model (sample rate, espeak voice, ...)
  3. weights quantised to 8 bits (about 21 MB instead of 63 MB)
The espeak-ng-data folder (pronunciation rules, the same for every voice) is copied by download-models.py.
"""

import json
import sys
import tempfile
from pathlib import Path

import onnx
from onnxruntime.quantization import QuantType, quantize_dynamic

LANGUAGE_NAMES = {"te": "Telugu", "hi": "Hindi", "ml": "Malayalam", "ur": "Urdu", "ta": "Tamil", "bn": "Bengali",
                  "mr": "Marathi", "kn": "Kannada", "gu": "Gujarati", "pa": "Punjabi", "ne": "Nepali"}


def main(model: Path, out: Path) -> None:
    config = json.loads(Path(str(model) + ".json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)

    with (out / "tokens.txt").open("w", encoding="utf-8") as f:
        for symbol, ids in config["phoneme_id_map"].items():
            if symbol == "\n":
                continue
            f.write(f"{symbol} {ids[0] if isinstance(ids, list) else ids}\n")

    sample_rate = config["audio"]["sample_rate"]
    voice = config.get("lang_code") or config["espeak"]["voice"]
    code = model.name.split("_")[0]
    meta = {"model_type": "vits", "comment": "piper", "language": LANGUAGE_NAMES.get(code, code), "voice": voice,
            "version": 1, "has_espeak": 1, "has_g2pw": 0, "n_speakers": config["num_speakers"],
            "sample_rate": 22050 if sample_rate == 22500 else sample_rate}

    graph = onnx.load(str(model))
    del graph.metadata_props[:]
    for key, value in meta.items():
        prop = graph.metadata_props.add()
        prop.key, prop.value = key, str(value)
    with tempfile.TemporaryDirectory() as folder:
        with_meta = Path(folder) / "with-meta.onnx"
        onnx.save(graph, str(with_meta))
        target = out / (model.stem + ".int8.onnx")
        quantize_dynamic(model_input=str(with_meta), model_output=str(target), weight_type=QuantType.QUInt8)
    print(f"Saved {target} ({target.stat().st_size / 1e6:.0f} MB), voice {voice}, {meta['sample_rate']} Hz")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
