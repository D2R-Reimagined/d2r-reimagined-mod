"""Encode transparent tier PNGs as D2R inventory sprites (RGBA v31).

The 40-byte header and row-major RGBA layout match SpriteEdit's writer:
https://github.com/eezstreet/D2RModding-SpriteEdit/blob/master/D2RModding-SpriteEdit/MainForm.cs
Art is generated separately; this conversion does not draw tier numbers.
"""
import argparse
from pathlib import Path
import struct

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def encode(image):
    image = image.convert('RGBA')
    width, height = image.size
    pixels = image.tobytes()
    return struct.pack('<4sHH8I', b'SpA1', 31, width, width, height,
                       0, 1, 0, 0, len(pixels), 4) + pixels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True,
                    help='Directory containing transparent map-tier-1.png through map-tier-6.png')
    ap.add_argument('--neutral-matte', action='store_true',
                    help='Convert the generated neutral checker matte to sprite alpha')
    args = ap.parse_args()
    images = []
    for tier in range(1, 7):
        with Image.open(args.source / f'map-tier-{tier}.png') as source:
            image = source.convert('RGBA')
        if args.neutral_matte:
            # Generated art uses warm parchment/ivory and colored bindings;
            # the baked preview matte alone is bright achromatic gray.
            image.putdata([(r, g, b, 0 if min(r, g, b) >= 100 and
                            max(r, g, b) - min(r, g, b) <= 12 else a)
                           for r, g, b, a in image.getdata()])
        if image.getchannel('A').getextrema()[0] != 0:
            raise ValueError(f'Tier {tier} needs genuine transparency; refusing an opaque background')
        images.append(image)
    output = ROOT / 'data/hd/global/ui/items/misc/map'
    output.mkdir(parents=True, exist_ok=True)
    for tier, image in enumerate(images, 1):
        for size, suffix in ((98, ''), (49, '.lowend')):
            converted = image.resize((size, size), Image.Resampling.LANCZOS)
            target = output / f'map_t{tier}{suffix}.sprite'
            target.write_bytes(encode(converted))
            preview = args.source / f'map-tier-{tier}-{size}.png'
            converted.save(preview)
            print(target.relative_to(ROOT))


if __name__ == '__main__':
    main()
