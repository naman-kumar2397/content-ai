"""Assemble dialogue + SFX for joey_origin, derive timings + amplitude envelopes -> timing JSON + mix wav."""
import json, math, numpy as np, soundfile as sf, sys
from scipy.signal import resample_poly
A = 'output/clips/audio/'; SR = 24000; FPS = 24
BALL_VOICE = sys.argv[1] if len(sys.argv) > 1 else 'bm_lewis'

def load(p):
    a, sr = sf.read(p)
    if a.ndim > 1: a = a.mean(1)
    if sr != SR:
        g = math.gcd(sr, SR); a = resample_poly(a, SR // g, sr // g)
    return a.astype(np.float32)

def trim(a, thr=0.012, pad=0.04):
    idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - int(pad * SR)): idx[-1] + int(pad * SR)]

def norm(a, db=-21.0):
    r = np.sqrt(np.mean(a ** 2)); return a * (10 ** (db / 20) / r)

j1 = norm(trim(load(A + 'j1.wav'))); j4 = norm(trim(load(A + 'j4.wav')))
bl = norm(trim(load(A + f'ball_{BALL_VOICE}.wav')))
d = lambda a: len(a) / SR
J1S = 0.35; J1E = J1S + d(j1)
DROP = J1E + 0.25; LAND = DROP + 0.50
BS = LAND + 0.80; BE = BS + d(bl)
J4S = BE + 0.40; J4E = J4S + d(j4)
DUR = J4E + 0.55
N = int(math.ceil(DUR * FPS))
L = int((N / FPS + 0.2) * SR)
def place(a, t):
    tr = np.zeros(L, np.float32); i = int(t * SR); tr[i:i + len(a)] = a; return tr
tj = place(j1, J1S) + place(j4, J4S); tb = place(bl, BS)

def env(tr):
    hop = SR // FPS; e = []
    for f in range(N):
        seg = tr[int(f * hop - hop * 0.5): int(f * hop + hop * 1.5)] if f else tr[:int(hop * 1.5)]
        e.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    e = np.array(e); p = np.percentile(e[e > 0.004], 90) if (e > 0.004).any() else 1
    e = np.clip(e / p, 0, 1.2); e[e < 0.10] = 0
    o = np.zeros_like(e); s = 0
    for i, v in enumerate(e):  # fast attack, slower release
        s = v if v > s else s + (v - s) * 0.45
        o[i] = s
    return np.clip(o, 0, 1).round(4).tolist()

# SFX
t = np.arange(L) / SR
def boing(t0, amp, f0=460, f1=150, dur=0.24):
    o = np.zeros(L, np.float32); n = int(dur * SR); i = int(t0 * SR); tt = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (tt / dur); ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) * np.exp(-tt * 14) * (1 - np.exp(-tt * 900))
    w += 0.4 * np.sin(2 * ph) * np.exp(-tt * 25)
    pop = np.sin(2 * np.pi * 1100 * tt) * np.exp(-tt * 220) * 0.8
    o[i:i + n] = (w + pop) * amp; return o
def ping(t0, fr, amp):
    o = np.zeros(L, np.float32); n = int(0.28 * SR); i = int(t0 * SR); tt = np.arange(n) / SR
    o[i:i + n] = np.sin(2 * np.pi * fr * tt) * np.exp(-tt * 16) * amp; return o
B2 = LAND + 0.586; B3 = B2 + 0.342
sfx = boing(LAND, 0.30) + boing(B2, 0.14, 520, 220, 0.14) + boing(B3, 0.06, 600, 300, 0.1)
sfx += ping(DROP - 0.02, 2093, 0.05) + ping(DROP + 0.07, 2637, 0.05) + ping(DROP + 0.15, 3136, 0.045)
sfx += ping(LAND + 0.03, 3520, 0.04) + ping(LAND + 0.12, 4186, 0.03)
mix = tj + tb + sfx
mix = mix[: int(DUR * SR)]
sf.write(A + 'mix_raw.wav', mix, SR)
json.dump(dict(fps=FPS, nframes=N, duration=round(DUR, 3), ball_voice=BALL_VOICE,
    events=dict(j1=[J1S, J1E], drop_start=DROP, land=LAND, ball=[BS, BE], j4=[J4S, J4E], bounces=[LAND, B2, B3]),
    captions=[dict(text='Hey Claude! Can you make me a tennis ball? A smart one!', t=[J1S - 0.05, J1E + 0.2]),
              dict(text='Claude: On it. \U0001F3BE', t=[DROP, BS - 0.1]),
              dict(text='Hello. I am a tennis ball. Please do not chew me.', t=[BS - 0.05, BE + 0.2]),
              dict(text='...no promises.', t=[J4S - 0.05, DUR])],
    joey_env=env(tj), ball_env=env(tb)), open('output/clips/joey_origin_timing.json', 'w'))
print({k: round(v, 2) if not isinstance(v, list) else [round(x, 2) for x in v] for k, v in
       dict(j1=[J1S, J1E], drop=DROP, land=LAND, ball=[BS, BE], j4=[J4S, J4E], dur=DUR).items()}, N)
