import json
from PIL import Image, ImageDraw, ImageFont
T = json.load(open('output/clips/joey_origin_timing.json'))
FB = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 70)
EMO = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
W, H = 1080, 1920; MAXW = 800; PAD = 44; LH = 92
def emoji_img(ch, px):
    f = ImageFont.truetype(EMO, 109); im = Image.new('RGBA', (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
    return im.crop(im.getbbox()).resize((px, px), Image.LANCZOS)
for i, c in enumerate(T['captions']):
    txt = c['text']; emo = None
    if any(ord(ch) > 0x2000 for ch in txt):
        emo = [ch for ch in txt if ord(ch) > 0x2000][0]; txt = txt.replace(emo, '').rstrip()
    words = txt.split(); lines = []; cur = ''
    for w in words:
        t2 = (cur + ' ' + w).strip()
        if FB.getlength(t2) + (80 if emo and w == words[-1] else 0) <= MAXW: cur = t2
        else: lines.append(cur); cur = w
    lines.append(cur)
    widths = [FB.getlength(l) + (84 if emo and k == len(lines) - 1 else 0) for k, l in enumerate(lines)]
    bw = int(max(widths)) + 2 * PAD; bh = LH * len(lines) + 2 * 30
    x0 = (W - bw) // 2; y0 = 330
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=44, fill=(8, 10, 22, 190))
    for k, l in enumerate(lines):
        w = widths[k]; x = (W - w) / 2; y = y0 + 30 + k * LH
        d.text((x, y + LH / 2), l, font=FB, fill=(255, 255, 255, 255), anchor='lm')
        if emo and k == len(lines) - 1:
            e = emoji_img(emo, 72); im.alpha_composite(e, (int(x + FB.getlength(l) + 12), int(y + LH / 2 - 36)))
    im.save(f'output/clips/audio/cap{i}.png'); print(i, lines, bw, bh)
