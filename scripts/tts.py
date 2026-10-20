#!/usr/bin/env python3
"""CPU Chatterbox TTS CLI."""
import argparse, json, os, time
import torch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default=None, help="reference wav for voice cloning")
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("--cfg", type=float, default=0.5)
    ap.add_argument("--voice", default=None, help="preset name in voice/<name>.json, e.g. joey")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()

    if a.voice:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "voice", f"{a.voice}.json")) as f:
            preset = json.load(f)
        a.ref = a.ref or os.path.join(root, preset["ref"])
        a.exaggeration, a.cfg = preset["exaggeration"], preset["cfg"]
        a.seed = preset["seed"] if a.seed is None else a.seed
    if a.seed is not None:
        torch.manual_seed(a.seed)

    # Weights were saved on CUDA; force CPU mapping.
    _orig = torch.load
    torch.load = lambda *args, **kw: _orig(*args, **{**kw, "map_location": torch.device("cpu")})

    import torchaudio as ta
    from chatterbox.tts import ChatterboxTTS
    torch.set_num_threads(os.cpu_count() or 4)
    model = ChatterboxTTS.from_pretrained(device="cpu")

    t0 = time.time()
    wav = model.generate(a.text, audio_prompt_path=a.ref,
                         exaggeration=a.exaggeration, cfg_weight=a.cfg)
    elapsed = time.time() - t0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    ta.save(a.out, wav, model.sr)
    dur = wav.shape[-1] / model.sr
    print(f"elapsed={elapsed:.1f}s audio={dur:.1f}s rtf={elapsed/dur:.2f} -> {a.out}")

if __name__ == "__main__":
    main()
