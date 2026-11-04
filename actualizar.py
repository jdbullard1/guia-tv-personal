"""Consolida únicamente programación. Nunca lee una lista M3U ni enlaces de vídeo."""
import argparse, collections, copy, datetime as D, gzip, io, json, os, re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
import xml.etree.ElementTree as E

BASE = Path(__file__).resolve().parent
MAX_COMPRESSED = 30_000_000
MAX_XML = 220_000_000
ALLOWED = {'www.open-epg.com', 'iptv-epg.org', 'raw.githubusercontent.com'}

def parse(data, wanted=None):
    if data[:2] == b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
            data = f.read(MAX_XML + 1)
    data = re.sub(br'<!DOCTYPE\s+tv\s+SYSTEM\s+[\"\']xmltv\.dtd[\"\']\s*>', b'', data, flags=re.I)
    if len(data) > MAX_XML or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML rechazado por tamaño o DTD')
    if wanted is None:
        root = E.fromstring(data)
        if root.tag != 'tv':
            raise ValueError('No es XMLTV')
        return root
    parser = E.iterparse(io.BytesIO(data), events=('start', 'end'))
    _, root = next(parser)
    if root.tag != 'tv':
        raise ValueError('No es XMLTV')
    slim = E.Element('tv')
    for event, el in parser:
        if event == 'end' and el.tag in ('channel', 'programme'):
            if el.tag == 'programme' and el.get('channel') in wanted:
                slim.append(copy.deepcopy(el))
            root.remove(el)
            el.clear()
    return slim

def stamp(value):
    try:
        return D.datetime.strptime(value, '%Y%m%d%H%M%S %z')
    except (ValueError, TypeError):
        return None

def build(mapping, roots, now):
    out = E.Element('tv', {'generator-info-name': 'Guia personal'})
    count = 0
    for row in mapping:
        root = roots.get(row['fuente'])
        if root is None:
            continue
        programs, seen = [], set()
        for el in root.findall('programme'):
            if el.get('channel') != row['id_fuente']:
                continue
            start, stop = stamp(el.get('start')), stamp(el.get('stop'))
            if not start or not stop or not start < stop or stop <= now or start > now + D.timedelta(days=7):
                continue
            key = (el.get('start'), el.get('stop'), el.findtext('title'))
            if key in seen:
                continue
            seen.add(key)
            p = E.Element('programme', {'channel': row['id'], 'start': el.get('start'), 'stop': el.get('stop')})
            # No URLs, iconos, enlaces de vídeo ni extensiones del proveedor en la salida.
            for child in el:
                if child.tag in {'title', 'sub-title', 'desc', 'category', 'date', 'episode-num'}:
                    q = E.SubElement(p, child.tag)
                    q.text = child.text
                    for attr in ('lang', 'system'):
                        if child.get(attr):
                            q.set(attr, child.get(attr))
            programs.append(p)
        if programs:
            count += 1
            ch = E.SubElement(out, 'channel', {'id': row['id']})
            E.SubElement(ch, 'display-name').text = row['nombre']
            for p in sorted(programs, key=lambda p: p.get('start')):
                out.append(p)
    return out, count

def lightweight(root, now, hours=48):
    out = E.Element('tv', dict(root.attrib))
    selected, ids = [], set()
    for el in root.findall('programme'):
        start, stop = stamp(el.get('start')), stamp(el.get('stop'))
        if not start or not stop or stop <= now or start > now + D.timedelta(hours=hours):
            continue
        p = E.Element('programme', dict(el.attrib))
        for child in el:
            if child.tag in ('title', 'sub-title'):
                q = E.SubElement(p, child.tag, dict(child.attrib))
                q.text = child.text
        selected.append(p)
        ids.add(p.get('channel'))
    for ch in root.findall('channel'):
        if ch.get('id') in ids:
            out.append(copy.deepcopy(ch))
    out.extend(selected)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, help='Guías ya descargadas; no se hace ninguna petición de red')
    ap.add_argument('--salida', type=Path, default=BASE / 'site')
    args = ap.parse_args()
    mapping = json.loads((BASE / 'mapa.json').read_text())
    if len({x['id'] for x in mapping}) != len(mapping):
        raise ValueError('IDs locales repetidos')
    failed = []
    now = D.datetime.now(D.timezone.utc)
    out = E.Element('tv', {'generator-info-name': 'Guia personal'})
    covered = 0
    for url in sorted({x['fuente'] for x in mapping}):
        u = urlsplit(url)
        if u.scheme != 'https' or u.hostname not in ALLOWED or u.username or u.password or u.query:
            raise ValueError('Fuente no aprobada')
        try:
            if args.cache:
                name = Path(u.path).name
                if name == 'us.xml.gz':
                    name = u.path.split('/')[-2] + '-us.xml.gz'
                data = (args.cache / name).read_bytes()
            else:
                with urlopen(url, timeout=25) as response:
                    data = response.read(MAX_COMPRESSED + 1)
                if len(data) > MAX_COMPRESSED:
                    raise ValueError('Descarga demasiado grande')
            subset = [row for row in mapping if row['fuente'] == url]
            root = parse(data, {row['id_fuente'] for row in subset})
            part, count = build(subset, {url: root}, now)
            out.extend(list(part))
            covered += count
            del root, part, data
        except Exception as exc:
            failed.append({'fuente': url, 'error': type(exc).__name__})
    # No publicar una guía casi vacía por caídas de los proveedores.
    if covered < max(1, len(mapping) * 0.80):
        raise RuntimeError(f'Cobertura insuficiente: {covered}/{len(mapping)}; se conserva lo publicado previamente')
    complete_xml = E.tostring(out, encoding='utf-8', xml_declaration=True)
    light = lightweight(out, now)
    if len(light.findall('channel')) < max(1, len(mapping) * 0.80):
        raise RuntimeError('Cobertura insuficiente en las próximas 48 horas')
    xml = E.tostring(light, encoding='utf-8', xml_declaration=True)
    if len(xml) > 4500000:
        raise RuntimeError('Guia ligera demasiado grande para el cliente Roku; no se publica')
    args.salida.mkdir(parents=True, exist_ok=True)
    for name, data in [('guia.xml', xml), ('guia.xml.gz', gzip.compress(xml, mtime=0)), ('guia-completa.xml', complete_xml), ('guia-completa.xml.gz', gzip.compress(complete_xml, mtime=0))]:
        tmp = args.salida / (name + '.tmp')
        tmp.write_bytes(data)
        os.replace(tmp, args.salida / name)
    status = {'actualizado_utc': now.isoformat(), 'canales': covered, 'canales_48h': len(light.findall('channel')), 'horas_guia_ligera': 48, 'esperados': len(mapping), 'fallos': failed}
    (args.salida / 'estado.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
    (args.salida / '.nojekyll').touch()
    print(json.dumps({'canales': covered, 'fuentes_fallidas': len(failed), 'bytes_xml': len(xml)}))

if __name__ == '__main__':
    main()
