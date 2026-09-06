from PIL import Image
from pathlib import Path

src = Path('logo_transparent.png')
if not src.exists():
    raise SystemExit('logo_transparent.png not found')

im = Image.open(src).convert('RGBA')

sizes = [32, 64, 192]
for s in sizes:
    out = im.copy()
    out.thumbnail((s, s), Image.LANCZOS)
    out.save(f'favicon-{s}x{s}.png')
    print('Saved', f'favicon-{s}x{s}.png')
