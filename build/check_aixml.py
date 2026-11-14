# Gold Hunter - prueft AIXML-Quellen auf Netze, die eine Diagrammgrenze ohne Tunnel kreuzen (das lehnt der Composer ab).
# Aufruf: python check_aixml.py [Datei.xml ...]   ohne Argument: alle *.xml im build-Ordner
import glob
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def nets(attr):
    out = []
    for part in (attr or '').split(','):
        if ':' in part:
            net = part.split(':', 1)[1]
            if net and '.' in net:
                out.append(net)
    return out


def check(path):
    root = ET.parse(path).getroot()
    parent = {}
    kind = {}

    def walk(el, par):
        for ch in el:
            uid = ch.get('uid')
            if uid:
                parent[uid] = par
                kind[uid] = (ch.tag, ch.get('_name', ''), ch.get('_id', ''))
            walk(ch, uid if uid else par)
    walk(root, 'root')

    def diag_of(uid):
        return parent.get(uid, 'root')

    producer = {}       # net -> diagram, in dem das Netz lebt
    consumers = []      # (net, diagram, uid)

    def structure_parent(uid):
        p = parent.get(uid, 'root')
        return p

    for el in root.iter():
        uid = el.get('uid')
        if not uid:
            continue
        tag, name, tid = kind[uid]
        par = parent[uid]
        ptag = kind.get(par, ('root',))[0]
        pname = kind.get(par, ('', ''))[1] if par in kind else ''
        outs, ins = nets(el.get('outputs')), nets(el.get('inputs'))
        if tag == 'Tunnel':
            is_in = tid.startswith('In')
            in_frame = ptag == 'CaseFrame'
            if in_frame:                       # Tunnel einer Case-Seite: lebt in der Seite
                for n in outs:
                    producer[n] = par
                for n in ins:
                    consumers.append((n, par, uid))
            elif pname in ('For Loop', 'While Loop'):
                if is_in:
                    for n in ins:
                        consumers.append((n, structure_parent(par), uid))
                    for n in outs:
                        producer[n] = par
                else:
                    for n in ins:
                        consumers.append((n, par, uid))
                    for n in outs:
                        producer[n] = structure_parent(par)
            else:                              # Tunnel einer Case-Struktur (aussen)
                for n in ins:
                    consumers.append((n, structure_parent(par), uid))
                for n in outs:
                    producer[n] = structure_parent(par)
        elif tag in ('Left', 'Right'):
            loop = parent[par]
            if tag == 'Left':
                for n in ins:
                    consumers.append((n, structure_parent(loop), uid))
                for n in outs:
                    producer[n] = loop
            else:
                for n in ins:
                    consumers.append((n, loop, uid))
                for n in outs:
                    producer[n] = structure_parent(loop)
        elif tag == 'Condition':
            for n in ins:
                consumers.append((n, par, uid))
        elif tag == 'Structure':
            sel = el.get('selectin')
            if sel:
                consumers.append((sel, par, uid))
            loop_i = el.get('count')
            if loop_i and loop_i.endswith('i.v'):
                producer[loop_i] = uid
        else:
            for n in outs:
                producer[n] = par
            for n in ins:
                consumers.append((n, par, uid))
    problems = []
    for n, dg, uid in consumers:
        if n not in producer:
            problems.append(f'{n}: no producer (used by {uid} {kind.get(uid)})')
        elif producer[n] != dg:
            problems.append(f'{n}: made in {producer[n]} {kind.get(producer[n], "")}, used in {dg} by {uid} {kind.get(uid)}')
    return problems


if __name__ == '__main__':
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, '*.xml')))
    bad = 0
    for f in files:
        p = check(f)
        if p:
            bad += 1
            print('==', os.path.basename(f))
            for line in p[:8]:
                print('  ', line)
    print('checked', len(files), 'files,', bad, 'with problems')
