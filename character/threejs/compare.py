"""Side-by-side: Blender Cycles reference vs three.js still -> compare.png (labelled)."""
import sys
from PIL import Image, ImageDraw, ImageFont
a, b, out = sys.argv[1], sys.argv[2], sys.argv[3]
la = sys.argv[4] if len(sys.argv) > 4 else 'Blender Cycles'
lb = sys.argv[5] if len(sys.argv) > 5 else 'three.js (SwiftShader)'
A = Image.open(a).convert('RGB'); B = Image.open(b).convert('RGB').resize(A.size)
W, H = A.size; gap = 16
im = Image.new('RGB', (W * 2 + gap, H), (255, 255, 255)); im.paste(A, (0, 0)); im.paste(B, (W + gap, 0))
d = ImageDraw.Draw(im)
try:
    f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 44)
except OSError:
    f = ImageFont.load_default()
for x, t in ((0, la), (W + gap, lb)):
    d.rounded_rectangle((x + 30, 30, x + 60 + d.textlength(t, font=f), 100), 20, fill=(0, 0, 0))
    d.text((x + 45, 38), t, font=f, fill=(255, 255, 255))
im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
im.save(out)
