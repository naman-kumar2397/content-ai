#!/usr/bin/env python3
"""Generate 4 golden-retriever mascot voice candidates (Kokoro + Chatterbox clone)."""
import os, subprocess, time, json
import numpy as np, soundfile as sf, torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output/voices"); VOICE = os.path.join(ROOT, "voice")
RAW = os.path.join(OUT, "_raw")
for d in (OUT, VOICE, RAW): os.makedirs(d, exist_ok=True)
TEXT = ("Wait wait wait... you're telling me this AI can write its own code?! "
        "Okay, that's either amazing or terrifying. Probably both! Let's dig in.")
REF_TEXT = ("Hey buddy! Oh man, I am so happy to see you! Guess what, today we get to build something really cool "
            "together, and I have a feeling it is going to be awesome. Come on, let's go, let's go, let's go!")
A_VOICE, B_VOICE = "am_puck", "am_fenrir"
timings = {}

def sh(*a): subprocess.run(a, check=True, capture_output=True)

def finish(raw, name, semis):
    """pitch shift (duration-preserving), loudnorm -16 LUFS, 44.1k mono wav + mp3"""
    r = 2 ** (semis / 12)
    out = os.path.join(OUT, name + ".wav")
    af = f"rubberband=pitch={r:.6f},loudnorm=I=-16:TP=-1.5:LRA=11"
    sh("ffmpeg", "-y", "-i", raw, "-af", af, "-ar", "44100", "-ac", "1", out)
    sh("ffmpeg", "-y", "-i", out, "-codec:a", "libmp3lame", "-q:a", "2", out[:-4] + ".mp3")
    return out

# ---- Kokoro
from kokoro import KPipeline
kp = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
def kokoro(text, voice, speed):
    t = time.time()
    parts = [a for _, _, a in kp(text, voice=voice, speed=speed)]
    a = np.concatenate([np.asarray(p) for p in parts]); return a, time.time() - t

raws = {}
for tag, v in (("A", A_VOICE), ("B", B_VOICE)):
    a, dt = kokoro(TEXT, v, 1.05); timings[tag] = dt
    p = os.path.join(RAW, f"{tag}.wav"); sf.write(p, a, 24000); raws[tag] = p
    # unshifted reference clip (~10s) at natural speed
    ra, _ = kokoro(REF_TEXT, v, 1.0)
    sf.write(os.path.join(VOICE, f"ref_{tag}.wav"), ra, 24000)
    print(tag, "ref dur", len(ra) / 24000, flush=True)

finals = {"A": finish(raws["A"], f"A_kokoro_{A_VOICE}", 1.5),
          "B": finish(raws["B"], f"B_kokoro_{B_VOICE}", 1.5)}

# ---- Chatterbox
_orig = torch.load
torch.load = lambda *a, **k: _orig(*a, **{**k, "map_location": torch.device("cpu")})
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
torch.set_num_threads(os.cpu_count() or 4)
cb = ChatterboxTTS.from_pretrained(device="cpu")
for tag, exg, cfg, semis in (("C", 0.75, 0.4, 1.5), ("D", 0.85, 0.35, 2.0)):
    t = time.time()
    wav = cb.generate(TEXT, audio_prompt_path=os.path.join(VOICE, f"ref_{'A' if tag=='C' else 'B'}.wav"),
                      exaggeration=exg, cfg_weight=cfg)
    timings[tag] = time.time() - t
    p = os.path.join(RAW, f"{tag}.wav"); ta.save(p, wav, cb.sr)
    finals[tag] = finish(p, f"{tag}_chatterbox_clone_{'A' if tag=='C' else 'B'}", semis)
    print(tag, "done", timings[tag], flush=True)

json.dump({"timings": timings, "finals": finals}, open(os.path.join(RAW, "meta.json"), "w"))
