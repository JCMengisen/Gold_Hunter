# Gold Hunter - schreibt alle Sprites als rohe Pixel fuer das Zeichnen ohne Picture to Pixmap ("Blit"):
#   Resources\Sprites\sprites.bin        je Sprite: h*w*3 Bytes RGB, dann h*w*3 Bytes Maske (255 = sichtbar, 0 = durchsichtig)
#   Resources\Sprites\sprites_blit.txt   je Sprite eine Zeile "Breite;Hoehe;Offset" (Offset in sprites.bin), Reihenfolge = sprites.txt
# Aufruf: python make_blit.py   (nach make_assets.py)
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SPR = os.path.join(HERE, '..', 'Resources', 'Sprites')


def main():
    names = [l.strip() for l in open(os.path.join(SPR, 'sprites.txt')) if l.strip()]
    blob, rows = bytearray(), []
    for name in names:
        im = Image.open(os.path.join(SPR, name + '.png')).convert('RGBA')
        w, h = im.size
        px = im.tobytes()                      # RGBA
        rgb, mask = bytearray(w * h * 3), bytearray(w * h * 3)
        for i in range(w * h):
            r, g, b, a = px[4 * i:4 * i + 4]
            rgb[3 * i:3 * i + 3] = bytes((r, g, b))
            if a >= 128:
                mask[3 * i:3 * i + 3] = b'\xff\xff\xff'
        rows.append('%d;%d;%d' % (w, h, len(blob)))
        blob += rgb + mask
    open(os.path.join(SPR, 'sprites.bin'), 'wb').write(bytes(blob))
    with open(os.path.join(SPR, 'sprites_blit.txt'), 'w', newline='\r\n') as f:
        f.write('\n'.join(rows) + '\n')
    print('%d sprites, %d bytes' % (len(names), len(blob)))


if __name__ == '__main__':
    main()
