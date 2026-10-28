#!/usr/bin/env python3
"""Fetch selected third-party reference originals; never overwrite a different file."""
from pathlib import Path
import argparse, hashlib, io, json, re, tempfile, urllib.parse, urllib.request
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]

def fetch_reference(ref, output):
    rid, fmt = ref['id'], ref['source_format'].lower()
    url = urllib.parse.urlsplit(ref['source_url'])
    if not re.fullmatch(r'R\d{2,3}', rid) or fmt not in {'svg','png','webp','jpg','jpeg'}:
        raise ValueError('Invalid reference identifier or format')
    if url.scheme != 'https' or url.hostname != 'cdn2.flowus.cn':
        raise ValueError('Reference URL must use the recorded FlowUs CDN')
    target = Path(output) / f'{rid}.{fmt}'
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == ref['source_sha256']:
            return target
        raise FileExistsError(f'Refusing to overwrite {target}')
    request = urllib.request.Request(ref['source_url'], headers={'User-Agent':'FlowUs-Geometric-Studio/0.1.5'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000 or hashlib.sha256(data).hexdigest() != ref['source_sha256']:
        raise ValueError(f'{rid}: size limit or SHA-256 mismatch; source may have changed')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as file:
        file.write(data)
    return target

def self_test():
    data = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    ref = {'id':'R03','source_format':'svg','source_url':'https://cdn2.flowus.cn/test.svg','source_sha256':hashlib.sha256(data).hexdigest()}
    with tempfile.TemporaryDirectory() as directory:
        with patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
            target = fetch_reference(ref, directory)
        assert target.read_bytes() == data
        target.write_bytes(b'keep user data')
        try:
            fetch_reference(ref, directory)
        except FileExistsError:
            pass
        else:
            raise AssertionError('An existing modified file must be preserved')
        assert target.read_bytes() == b'keep user data'
    print('Self-test passed: byte identity and overwrite protection')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ids', nargs='*', help='Selected IDs, such as R03 R12')
    parser.add_argument('--output', type=Path, default=ROOT/'references/downloaded')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    catalog = {r['id']:r for r in json.loads((ROOT/'references/reference-index.json').read_text())['curated_references']}
    if not args.ids or any(rid not in catalog for rid in args.ids):
        parser.error('Choose one or more available IDs: '+', '.join(catalog))
    for rid in dict.fromkeys(args.ids):
        print(fetch_reference(catalog[rid], args.output))
if __name__ == '__main__':
    main()
