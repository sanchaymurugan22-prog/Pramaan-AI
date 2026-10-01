"""Convert AI4Bharat IndicTrans2 (en->indic, distilled 200M) to CTranslate2 8-bit, without PyTorch.

    backend/.venv/bin/python scripts/convert-indictrans2.py models/src/indictrans2-en-indic-dist-200M models/indictrans2-en-indic-ct2

Recent PyTorch has no Intel-Mac wheels, and CTranslate2 has no ready converter for this model, so this
script builds the CTranslate2 model directly from the official weights (model.safetensors, read with numpy).

IndicTrans2 has the same layout as M2M100 (which CTranslate2 supports): a pre-norm Transformer with GELU,
scaled embeddings, sinusoidal positions starting at offset 2, a layer norm after the embeddings, and a final
layer norm. The difference: separate source (English) and target (Indic) vocabularies. The mapping below
follows CTranslate2's own M2M100 converter (ctranslate2/converters/transformers.py, BartLoader).
The tokenizer files (SentencePiece models and dictionaries) are copied next to the model.
"""

import json
import math
import shutil
import sys
from pathlib import Path

import ctranslate2
import numpy as np
from ctranslate2.converters import utils
from ctranslate2.specs import common_spec, transformer_spec
from safetensors.numpy import load_file


def sinusoids(num: int, dim: int, padding_idx: int = 1) -> np.ndarray:
    """IndicTransSinusoidalPositionalEmbedding.get_embedding (tensor2tensor style: sin half, cos half)."""
    half = dim // 2
    scale = math.log(10000) / (half - 1)
    freqs = np.exp(np.arange(half, dtype=np.float32) * -scale)
    angles = np.arange(num, dtype=np.float32)[:, None] * freqs[None, :]
    emb = np.concatenate([np.sin(angles), np.cos(angles)], axis=1).astype(np.float32)
    emb[padding_idx, :] = 0
    return emb


def main(source: Path, target: Path) -> None:
    config = json.loads((source / "config.json").read_text())
    w = load_file(str(source / "model.safetensors"))
    w = {k.removeprefix("model."): v.astype(np.float32) for k, v in w.items()}

    def linear(spec, name):
        spec.weight = w[f"{name}.weight"]
        if f"{name}.bias" in w:
            spec.bias = w[f"{name}.bias"]

    def norm(spec, name):
        spec.gamma = w[f"{name}.weight"]
        spec.beta = w[f"{name}.bias"]

    def attention(spec, name, self_attention):
        q, k, v = (common_spec.LinearSpec() for _ in range(3))
        linear(q, f"{name}.q_proj")
        linear(k, f"{name}.k_proj")
        linear(v, f"{name}.v_proj")
        if self_attention:
            utils.fuse_linear(spec.linear[0], [q, k, v])
        else:
            utils.fuse_linear(spec.linear[0], [q])
            utils.fuse_linear(spec.linear[1], [k, v])
        linear(spec.linear[-1], f"{name}.out_proj")

    assert config["encoder_normalize_before"] and config["decoder_normalize_before"] and config["layernorm_embedding"]
    spec = transformer_spec.TransformerSpec.from_config(
        (config["encoder_layers"], config["decoder_layers"]),
        config["encoder_attention_heads"],
        pre_norm=True,
        activation=common_spec.Activation.GELU,
        layernorm_embedding=True,
    )
    positions = sinusoids(config["max_source_positions"] + 2, config["encoder_embed_dim"])[2:]  # offset 2, as M2M100

    for side in ("encoder", "decoder"):
        s = getattr(spec, side)
        s.scale_embeddings = math.sqrt(config[f"{side}_embed_dim"]) if config["scale_embedding"] else 1.0
        s.position_encodings.encodings = positions
        (s.embeddings[0] if isinstance(s.embeddings, list) else s.embeddings).weight = w[f"{side}.embed_tokens.weight"]
        norm(s.layer_norm, f"{side}.layer_norm")
        norm(s.layernorm_embedding, f"{side}.layernorm_embedding")
        for i, layer in enumerate(s.layer):
            p = f"{side}.layers.{i}"
            attention(layer.self_attention, f"{p}.self_attn", True)
            norm(layer.self_attention.layer_norm, f"{p}.self_attn_layer_norm")
            if side == "decoder":
                attention(layer.attention, f"{p}.encoder_attn", False)
                norm(layer.attention.layer_norm, f"{p}.encoder_attn_layer_norm")
            linear(layer.ffn.linear_0, f"{p}.fc1")
            linear(layer.ffn.linear_1, f"{p}.fc2")
            norm(layer.ffn.layer_norm, f"{p}.final_layer_norm")
    # The output projection is tied to the decoder embeddings (share_decoder_input_output_embed).
    spec.decoder.projection.weight = w.get("lm_head.weight", w["decoder.embed_tokens.weight"])

    def vocab(file):
        ids = json.loads((source / file).read_text(encoding="utf-8"))
        tokens = [t for t, _ in sorted(ids.items(), key=lambda item: item[1])]
        assert [ids[t] for t in tokens] == list(range(len(tokens))), f"{file}: ids are not 0..n-1"
        return tokens

    src_vocab, tgt_vocab = vocab("dict.SRC.json"), vocab("dict.TGT.json")
    assert len(src_vocab) == config["encoder_vocab_size"] and len(tgt_vocab) == config["decoder_vocab_size"]
    spec.register_source_vocabulary(src_vocab)
    spec.register_target_vocabulary(tgt_vocab)
    spec.config.bos_token, spec.config.eos_token, spec.config.unk_token = "<s>", "</s>", "<unk>"
    spec.config.decoder_start_token = tgt_vocab[config["decoder_start_token_id"]]  # "</s>"

    spec.validate()
    spec.optimize(quantization="int8")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    spec.save(str(target))
    for name in ("model.SRC", "model.TGT", "LICENSE"):
        shutil.copy(source / name, target / name)
    (target / "PRAMAAN_SOURCE.txt").write_text(
        "Converted by scripts/convert-indictrans2.py from ai4bharat/indictrans2-en-indic-dist-200M "
        "(MIT licence, AI4Bharat). CTranslate2 int8.\n")
    print(f"Saved {target} ({sum(f.stat().st_size for f in target.iterdir()) / 1e6:.0f} MB).")
    ctranslate2.Translator(str(target), device="cpu")  # loads: the model is complete


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
