#!/usr/bin/env python3
"""CPU Chatterbox TTS CLI."""
import argparse, os, time
import torch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default=None, help="reference wav for voice cloning")
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("--cfg", type=float, default=0.5)
    a = ap.parse_args()

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
