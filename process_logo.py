from PIL import Image
from pathlib import Path
import math

p = Path('logo.png')
if not p.exists():
    raise SystemExit('logo.png not found')

im = Image.open(p).convert('RGBA')
w, h = im.size

# sample corner pixels (small area) to estimate background color
def sample_corner(img, x, y, size=3):
    rs = gs = bs = 0
    n = 0
    for i in range(size):
        for j in range(size):
            xx = min(max(x + i, 0), img.width - 1)
            yy = min(max(y + j, 0), img.height - 1)
            r, g, b, a = img.getpixel((xx, yy))
            rs += r; gs += g; bs += b; n += 1
    return (rs // n, gs // n, bs // n)

corners = [sample_corner(im, 0, 0), sample_corner(im, w - 3, 0), sample_corner(im, 0, h - 3), sample_corner(im, w - 3, h - 3)]
# average corner color
bg = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))

# distance function
def dist(c1, c2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

# threshold - tuned for dark backgrounds; increase if needed
threshold = 80.0

out = Image.new('RGBA', (w, h))
for y in range(h):
    for x in range(w):
        r, g, b, a = im.getpixel((x, y))
        if dist((r, g, b), bg) < threshold:
            out.putpixel((x, y), (r, g, b, 0))
        else:
            out.putpixel((x, y), (r, g, b, a))

out_path = Path('logo_transparent.png')
out.save(out_path)
print('Saved', out_path)
