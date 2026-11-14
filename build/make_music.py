# Gold Hunter - eigene Hintergrundmusik (Chiptune, a-Moll, 132 BPM, 16 Takte, nahtlos wiederholbar)
#   Melodie (Rechteck), Bass (Dreieck), Arpeggio (leise) und Rhythmus (Rauschen) -> Resources\Sounds\music.wav
# Aufruf: python make_music.py
import math
import os
import random
import struct
import wave

RATE = 22050
BPM = 132
BEAT = 60.0 / BPM
STEP = BEAT / 4                       # Sechzehntel
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Resources', 'Sounds', 'music.wav')
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def freq(note):
    """'A4' -> Hz"""
    name, octv = note[:-1], int(note[-1])
    return 440 * 2 ** ((NAMES.index(name) - 9) / 12 + (octv - 4))


# Akkorde je Takt (4 Schlaege): Grundton fuer Bass und Arpeggio
CHORDS = ['A', 'F', 'C', 'G', 'A', 'F', 'G', 'E',
          'D', 'A', 'F', 'C', 'D', 'E', 'A', 'E']
TRIADS = {'A': ['A', 'C', 'E'], 'F': ['F', 'A', 'C'], 'C': ['C', 'E', 'G'], 'G': ['G', 'B', 'D'], 'E': ['E', 'G#', 'B'], 'D': ['D', 'F', 'A']}
# Melodie: (Note oder '-', Laenge in Sechzehnteln) - 16 Takte zu 16 Sechzehnteln
MELODY = [
    ('E5', 2), ('A5', 2), ('C6', 2), ('B5', 2), ('A5', 4), ('E5', 4),
    ('F5', 2), ('A5', 2), ('C6', 4), ('D6', 2), ('C6', 2), ('A5', 4),
    ('G5', 2), ('C6', 2), ('E6', 4), ('D6', 2), ('C6', 2), ('G5', 4),
    ('B5', 2), ('A5', 2), ('G5', 2), ('B5', 2), ('D6', 6), ('-', 2),
    ('E5', 2), ('A5', 2), ('C6', 2), ('E6', 2), ('D6', 2), ('C6', 2), ('B5', 2), ('A5', 2),
    ('F5', 2), ('A5', 2), ('C6', 2), ('F6', 2), ('E6', 4), ('C6', 4),
    ('D6', 2), ('B5', 2), ('G5', 2), ('B5', 2), ('D6', 4), ('G6', 4),
    ('E6', 4), ('D6', 2), ('B5', 2), ('G#5', 6), ('-', 2),
    ('D5', 2), ('F5', 2), ('A5', 4), ('D6', 2), ('C6', 2), ('A5', 4),
    ('C6', 2), ('B5', 2), ('A5', 2), ('E5', 2), ('A5', 6), ('-', 2),
    ('F5', 2), ('A5', 2), ('C6', 2), ('A5', 2), ('F6', 4), ('E6', 4),
    ('E6', 2), ('D6', 2), ('C6', 2), ('B5', 2), ('C6', 4), ('G5', 4),
    ('F5', 2), ('A5', 2), ('D6', 2), ('F6', 2), ('E6', 2), ('D6', 2), ('C6', 2), ('A5', 2),
    ('B5', 4), ('G#5', 4), ('E5', 4), ('B5', 4),
    ('A5', 2), ('C6', 2), ('E6', 2), ('A6', 2), ('G6', 2), ('E6', 2), ('C6', 2), ('B5', 2),
    ('A5', 6), ('-', 2), ('B5', 2), ('C6', 2), ('B5', 2), ('G#5', 2),
]
assert sum(n for _, n in MELODY) == 16 * 16


def square(ph, duty=0.5):
    return 1.0 if ph % 1.0 < duty else -1.0


def tri(ph):
    return 4 * abs(ph % 1.0 - 0.5) - 1


def render():
    total = int(round(16 * 16 * STEP * RATE))
    out = [0.0] * total
    # Melodie
    pos = 0
    for note, n in MELODY:
        length = int(round(n * STEP * RATE))
        if note != '-':
            fr, ph = freq(note), 0.0
            for i in range(length):
                ph += fr / RATE
                vib = 1.0 + 0.004 * math.sin(2 * math.pi * 5.5 * i / RATE) if i > RATE * 0.12 else 1.0
                env = min(1.0, i / 80) * (0.85 ** (i / (RATE * 0.25))) * min(1.0, (length - i) / 300)
                out[pos + i] += 0.16 * square(ph * vib, 0.25) * (0.55 + 0.45 * env)
        pos += length
    # Bass: Achtel auf Grundton und Oktave, Arpeggio in Sechzehnteln (leise)
    bar_len = 16 * STEP
    rnd = random.Random(7)
    for bar, chord in enumerate(CHORDS):
        root = freq(chord + '2')
        triad = [freq(n + '4') for n in TRIADS[chord]]
        for k in range(8):
            start = int(round((bar * bar_len + k * 2 * STEP) * RATE))
            length = int(round(2 * STEP * RATE * 0.9))
            fr = root * (2 if k % 2 else 1)
            ph = 0.0
            for i in range(length):
                ph += fr / RATE
                out[start + i] += 0.20 * tri(ph) * min(1.0, (length - i) / 200)
        for k in range(16):
            start = int(round((bar * bar_len + k * STEP) * RATE))
            length = int(round(STEP * RATE * 0.7))
            fr = triad[k % 3] * (2 if (k // 3) % 2 else 1)
            ph = 0.0
            for i in range(length):
                ph += fr / RATE
                out[start + i] += 0.035 * square(ph, 0.5) * (1 - i / length)
        # Rhythmus: Hi-Hat auf jedem Achtel, Snare auf 2 und 4, Bassdrum auf 1 und 3
        for k in range(8):
            start = int(round((bar * bar_len + k * 2 * STEP) * RATE))
            snare = k in (2, 6)
            kick = k in (0, 4)
            length = int(RATE * (0.12 if snare else 0.03))
            v = 0.0
            for i in range(length):
                if i % 2 == 0:
                    v = rnd.uniform(-1, 1)
                out[start + i] += (0.10 if snare else 0.035) * v * (1 - i / length)
            if kick:
                ph = 0.0
                for i in range(int(RATE * 0.09)):
                    ph += (110 - 70 * i / (RATE * 0.09)) / RATE
                    out[start + i] += 0.30 * math.sin(2 * math.pi * ph) * (1 - i / (RATE * 0.09))
    peak = max(abs(v) for v in out)
    return [v / peak * 0.85 for v in out]


if __name__ == '__main__':
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = render()
    with wave.open(OUT, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h', int(v * 32000)) for v in data))
    print('music.wav %.1f s' % (len(data) / RATE))
