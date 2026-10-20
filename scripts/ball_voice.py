import sys, numpy as np, soundfile as sf
from kokoro import KPipeline
text = "Hello. I am a tennis ball. Please do not chew me."
voices = sys.argv[1].split(',')
out = sys.argv[2]
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 0.9
kp = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
for v in voices:
    ch = [np.asarray(a) for _, _, a in kp(text, voice=v, speed=speed)]
    a = np.concatenate(ch)
    sf.write(f"{out}/ball_{v}.wav", a, 24000)
    print(v, len(a) / 24000)
