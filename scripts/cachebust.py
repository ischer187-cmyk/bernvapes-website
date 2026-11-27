#!/usr/bin/env python3
"""Stamp local asset URLs with a content hash.

Re-run after an image, video, script, or stylesheet changes. The query
(?v=) is the first 10 hex chars of the file's SHA-256. Nothing is counted
by hand. Safe to run twice.

Dynamic fox frames and fox clips are not literal URLs. Those go through
window.BV() and assets/js/rev.js, which this script rewrites.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_GLOBS = ['*.html', 'assets/css/*.css', 'assets/js/*.js']
SKIP_NAMES = {'rev.js', 'cachebust.py'}
EXT = r'(?:webp|png|jpe?g|gif|svg|ico|mp4|webm|js|css|woff2)'
# A quoted or url()-wrapped local path, with an optional old ?v= stamp.
PAT = re.compile(
    rf'''(?P<q>["'(])(?P<path>(?:(?:assets/|\.\./(?:web|fonts|js|css)/)[^"'()\s?#]+|favicon(?:-32)?|apple-touch-icon)\.{EXT})(?:\?v=[0-9A-Za-z]+)?'''
)


def sha10(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()[:10]


def resolve(path, source):
    if path.startswith('../'):
        return (source.parent / path).resolve()
    return (ROOT / path).resolve()


def sources():
    found = []
    for pattern in TEXT_GLOBS:
        found.extend(ROOT.glob(pattern))
    return [p for p in found if p.is_file() and p.name not in SKIP_NAMES]


def dynamic_files():
    files = []
    for folder in (ROOT / 'assets/web/fox_hd', ROOT / 'assets/web/fox_mobile', ROOT / 'assets/web/fox3'):
        if folder.is_dir():
            files.extend(p for p in folder.iterdir() if p.is_file())
    return files


def main():
    hashes = {}
    for path in dynamic_files():
        rel = path.relative_to(ROOT).as_posix()
        hashes[rel] = sha10(path)

    # Stamp literal URLs. Collect hashes for the files those URLs point at.
    stamped = 0
    missing = []
    for src in sources():
        text = src.read_text(encoding='utf-8')
        def repl(m, src=src):
            nonlocal stamped
            raw = m.group('path')
            target = resolve(raw, src)
            try:
                target.relative_to(ROOT)
            except ValueError:
                return m.group(0)
            if not target.is_file():
                missing.append(f'{src.relative_to(ROOT)} -> {raw}')
                return m.group(0)
            rel = target.relative_to(ROOT).as_posix()
            digest = hashes.get(rel)
            if digest is None:
                digest = sha10(target)
                hashes[rel] = digest
            stamped += 1
            return m.group('q') + raw + '?v=' + digest
        new = PAT.sub(repl, text)
        if new != text:
            src.write_text(new, encoding='utf-8')

    # rev.js is the lookup for URLs built at runtime (fox frames, fox clips).
    # Its own hash is stamped onto the script tag above, so it is not in the map.
    lines = ['window.BV_HASH={']
    for rel in sorted(hashes):
        if not (rel.startswith('assets/web/fox_hd/') or rel.startswith('assets/web/fox_mobile/') or rel.startswith('assets/web/fox3/')):
            continue
        lines.append(f'{rel!r}:{hashes[rel]!r},')
    lines.append('};')
    lines.append(
        'window.BV=function(url){if(!url||/^(https?:|data:|blob:)/i.test(url))return url;'
        'var path=String(url).split("?")[0].split("#")[0];'
        'var h=window.BV_HASH[path];if(!h)return url;'
        'if(/[?&]v=/.test(url))return url;return path+"?v="+h;};'
    )
    rev = ROOT / 'assets/js/rev.js'
    rev.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    rev_hash = sha10(rev)
    # The script tag was stamped before rev.js existed, or with the previous hash.
    for src in sources():
        text = src.read_text(encoding='utf-8')
        new = re.sub(r'assets/js/rev\.js(?:\?v=[0-9A-Za-z]+)?', 'assets/js/rev.js?v=' + rev_hash, text)
        if new != text:
            src.write_text(new, encoding='utf-8')
    print(f'stamped {stamped} urls, {len(hashes)} files, rev.js {rev_hash}')
    if missing:
        print('unresolved', len(missing))
        for row in missing[:20]:
            print(' ', row)


if __name__ == '__main__':
    main()
