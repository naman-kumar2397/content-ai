"""Mean sRGB colour of a few regions in two 1080x1920 renders (calibration aid)."""
import sys
import numpy as np
from PIL import Image
R = {'wall_top': (100, 150, 900, 300), 'wall_mid': (700, 1150, 1050, 1300), 'desk_front': (100, 1750, 1000, 1900),
     'joey_chest': (330, 1300, 470, 1420), 'joey_head': (300, 860, 520, 920), 'mouth': (330, 1090, 460, 1130),
     'ball': (870, 1420, 920, 1500), 'ear_L': (140, 950, 190, 1150), 'shadow_desk': (580, 1560, 660, 1620)}
ims = [np.asarray(Image.open(p).convert('RGB')).astype(float) for p in sys.argv[1:3]]
for k, (x0, y0, x1, y1) in R.items():
    a, b = [im[y0:y1, x0:x1].reshape(-1, 3).mean(0).round() for im in ims]
    print(f'{k:12s} blender {a}  three {b}')
