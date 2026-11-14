# Gold Hunter - eigene, synthetisierte Soundeffekte (16 bit, 22050 Hz, mono) -> Resources\Sounds\*.wav
# Aufruf: python make_sounds.py
import math
import os
import random
import struct
import wave

RATE = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Resources', 'Sounds')
os.makedirs(OUT, exist_ok=True)
NOTE = {n: 440 * 2 ** ((i - 9) / 12) for i, n in enumerate(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}


def f(name, octave=4):
    return NOTE[name] * 2 ** (octave - 4)


def tone(f0, f1, dur, vol=0.3, shape='square', duty=0.5):
    n = int(RATE * dur)
    s, ph = [], 0.0
    for i in range(n):
        fr = f0 + (f1 - f0) * i / max(1, n - 1)
        ph += fr / RATE
        p = ph % 1.0
        if shape == 'square':
            v = 1.0 if p < duty else -1.0
        elif shape == 'tri':
            v = 4 * abs(p - 0.5) - 1
        else:
            v = math.sin(2 * math.pi * p)
        env = min(1.0, i / 120) * min(1.0, (n - i) / 400)
        s.append(v * vol * env)
    return s


def noise(dur, vol=0.3, decay=8.0, seed=1):
    rnd = random.Random(seed)
    n = int(RATE * dur)
    out, v = [], 0.0
    for i in range(n):
        if i % 3 == 0:
            v = rnd.uniform(-1, 1)
        out.append(v * vol * math.exp(-decay * i / n))
    return out


def silence(dur):
    return [0.0] * int(RATE * dur)


def notes(seq, shape='square', vol=0.26, gap=0.012, duty=0.5):
    out = []
    for name, octv, dur in seq:
        out += tone(f(name, octv), f(name, octv), dur - gap, vol, shape, duty) + silence(gap)
    return out


def mix(*parts):
    n = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]


def save(name, samples):
    with wave.open(os.path.join(OUT, name + '.wav'), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v)) * 32000)) for v in samples))


SOUNDS = {
    # Sprung: kurzer, steigender Huepfer
    'jump': tone(260, 720, 0.13, 0.22, 'square', 0.25),
    # Muenze: zwei helle Toene
    'coin': notes([('B', 5, 0.05), ('E', 6, 0.12)], vol=0.2, duty=0.25),
    # Goldschatz: kleines Glitzern
    'hoard': notes([('E', 5, 0.05), ('G#', 5, 0.05), ('B', 5, 0.05), ('E', 6, 0.16)], vol=0.2, duty=0.25),
    # Schluessel: metallisches Klingeln
    'key': mix(notes([('A', 5, 0.07), ('E', 6, 0.07), ('A', 6, 0.18)], 'tri', 0.3), noise(0.08, 0.05, 20, 3)),
    # Tuer: tiefes Knarren und Klacken
    'door': tone(140, 70, 0.28, 0.25, 'square', 0.15) + noise(0.06, 0.25, 12, 4),
    # Fackel: Zischen und aufsteigender Ton
    'torch': mix(noise(0.45, 0.18, 3, 5), tone(300, 900, 0.45, 0.12, 'tri')),
    # Neues Leben: froehliche Tonfolge
    'life': notes([('C', 5, 0.08), ('E', 5, 0.08), ('G', 5, 0.08), ('C', 6, 0.08), ('E', 6, 0.08), ('G', 6, 0.22)], vol=0.2, duty=0.25),
    # Tod: fallender Ton
    'death': tone(620, 90, 0.75, 0.25, 'square', 0.5) + silence(0.05),
    # Schatzkammer: Fanfare
    'treasure': notes([('G', 4, 0.12), ('C', 5, 0.12), ('E', 5, 0.12), ('G', 5, 0.24), ('E', 5, 0.12), ('G', 5, 0.5)], vol=0.24, duty=0.33),
    # Level geschafft / neues Level
    'level': notes([('C', 5, 0.1), ('G', 4, 0.1), ('C', 5, 0.1), ('E', 5, 0.1), ('G', 5, 0.1), ('C', 6, 0.35)], vol=0.22, duty=0.33),
    # Spielende: langsam abwaerts
    'gameover': notes([('E', 4, 0.3), ('D#', 4, 0.3), ('D', 4, 0.3), ('C#', 4, 0.9)], 'tri', 0.35),
    # Rutschen an der Stange: kurzes, fallendes Zischen (wird beim Rutschen wiederholt)
    'slide': mix(noise(0.2, 0.12, 2.5, 9), tone(950, 520, 0.2, 0.05, 'tri')),
    # Bereit (nach einem verlorenen Leben)
    'ready': notes([('E', 5, 0.08), ('A', 5, 0.18)], vol=0.18, duty=0.25),
}

if __name__ == '__main__':
    for name, samples in SOUNDS.items():
        save(name, samples)
        print('%-9s %.2f s' % (name, len(samples) / RATE))
