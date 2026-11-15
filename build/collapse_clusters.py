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


# Innenbereich eines zugeklappten Clusters (so wie bei den von Anfang an kleinen "no error"-Konstanten): ohne das bleibt
# im Diagramm der grosse, leere Rahmen stehen
ICON_PANE = '(3, 3, 13, 19)'
ICON_PARTS = {'39': '(0, 16, 10, 33)', '38': '(10, 0, 27, 16)', '44': '(10, 16, 27, 33)', '28': '(0, 0, 10, 16)'}


def shrink_pane(cl, h, w):
    """Innenbereich (paneHierarchy) und eigene Teile (Rahmen, Inhalt) des Clusters auf das Symbol verkleinern - so speichert
    LabVIEW es beim Zuklappen; ohne das bleibt im Diagramm der grosse, leere Rahmen stehen. h, w = ausgeklappte Groesse."""
    changed = False
    own = {'(0, 0, %d, %d)' % (h, w): '(0, 0, 16, 22)', '(3, 3, %d, %d)' % (h - 3, w - 3): ICON_PANE}
    parts = cl.find('partsList')
    for p in (parts if parts is not None else []):
        b = p.find('bounds')
        if b is not None and b.text in own:
            b.text = own[b.text]
            changed = True
    ph = cl.find('paneHierarchy')
    if ph is not None and ph.findtext('bounds') != ICON_PANE:
        ph.find('bounds').text = ICON_PANE
        fl = ph.find('objFlags')
        if fl is not None:
            fl.text = str(int(fl.text) & ~4)          # wie LabVIEW beim Zuklappen (2494740 -> 2494736)
        pl = ph.find('partsList')
        for p in (pl if pl is not None else []):
            b, pid = p.find('bounds'), p.findtext('partID')
            if b is not None and pid in ICON_PARTS:
                b.text = ICON_PARTS[pid]
        changed = True
    return changed


def box(text):
    return tuple(int(v) for v in re.findall(r'-?\d+', text))


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
            if fl is None or b is None:
                continue
            if int(fl.text) & 0x10000000:          # schon zugeklappt: Innenbereich und Teile nachziehen (Groesse aus savedSize)
                st, sl, sb, sr = box(cl.findtext('savedSize') or '(0, 0, 0, 0)')
                if sb - st > 16 or sr - sl > 22:
                    changed += shrink_pane(cl, sb - st, sr - sl)
                continue
            t, l, bt, r = box(b.text)
            shrink_pane(cl, bt - t, r - l)
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
