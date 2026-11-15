# Gold Hunter - klappt alle Cluster-Konstanten im Blockdiagramm zu (wie "View Cluster As Icon" im Kontextmenue).
#   Das AIXML kennt diese Darstellung nicht, darum nach dem Erzeugen: pylabview entpackt das VI, bei jeder Cluster-Konstante
#   (stdClust direkt unter einer bDConstDCO) werden die Bits 0x10000020 in objFlags gesetzt, die ausgeklappte Groesse kommt nach
#   savedSize, bounds wird das 16 x 22 Symbol (so speichert es LabVIEW selbst, gemessen an Main.vi); dann ohne kompilierten Code
#   wieder zusammengebaut. LabVIEW darf die VIs dabei NICHT geladen haben (Projekt schliessen bzw. LabVIEW neu starten),
#   danach Mass Compile.
# Aufruf: python collapse_clusters.py <VI oder Ordner> ...
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

PYLV = r'C:\Projects\LabVIEWMCP\tools\pylabview\runtime'
STRIP = r'C:\Projects\LabVIEWMCP\scripts\pylv-strip-compiled.py'
ICON_BITS = 0x10000020


def run(args):
    r = subprocess.run([os.path.join(PYLV, 'python.exe'), os.path.join(PYLV, 'app', 'pylabview', 'readRSRC.py')] + args,
                       cwd=os.path.join(PYLV, 'app'), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)


def patch_heap(path):
    txt = open(path, encoding='utf-8').read()
    tree = ET.ElementTree(ET.fromstring(txt))
    changed = 0
    for dco in tree.iter():
        if dco.get('class') != 'bDConstDCO':
            continue
        for cl in dco:
            if cl.get('class') != 'stdClust':
                continue
            fl = cl.find('objFlags')
            b = cl.find('bounds')
            if fl is None or b is None or int(fl.text) & 0x10000000:
                continue
            t, l, bt, r = (int(v) for v in re.findall(r'-?\d+', b.text))
            fl.text = str(int(fl.text) | ICON_BITS)
            ss = cl.find('savedSize')
            if ss is None:
                ss = ET.SubElement(cl, 'savedSize')
            ss.text = '(%d, %d, %d, %d)' % (t, l, bt, r)
            b.text = '(%d, %d, %d, %d)' % (t, l, t + 16, l + 22)
            changed += 1
    if changed:
        head = txt[:txt.index('<', 1)] if txt.startswith('<?xml') else ''
        body = ET.tostring(tree.getroot(), encoding='unicode')
        open(path, 'w', encoding='utf-8').write(head + body)
    return changed


def collapse(vi):
    work = tempfile.mkdtemp(prefix='gh_clust_')
    base = os.path.splitext(os.path.basename(vi))[0]
    try:
        run(['-x', '-i', vi, '-m', os.path.join(work, base + '.xml')])
        heap = os.path.join(work, base + '_BDHb.xml')
        n = patch_heap(heap) if os.path.exists(heap) else 0
        if n:
            subprocess.run([sys.executable, STRIP, work, base], check=True, capture_output=True)
            tmp = os.path.join(work, base + '_new.vi')
            run(['-c', '-m', os.path.join(work, base + '.xml'), '-i', tmp])
            shutil.copyfile(tmp, vi)
        return n
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(paths):
    vis = []
    for p in map(os.path.abspath, paths):
        if os.path.isdir(p):
            vis += [os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs if f.endswith('.vi')]
        else:
            vis.append(p)
    total = 0
    for vi in sorted(vis):
        try:
            n = collapse(vi)
        except Exception as ex:
            print('FEHLER', vi, str(ex).splitlines()[-1][:300])
            continue
        if n:
            print('%3d  %s' % (n, vi))
        total += n
    print('zugeklappt: %d Cluster-Konstanten in %d VIs geprueft' % (total, len(vis)))


if __name__ == '__main__':
    main(sys.argv[1:])
