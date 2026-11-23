#!/usr/bin/env python3
"""dev.html helper. The game script inside dev.html is gzip+base64.
  python3 devpack.py unpack   -> writes dev.game.js (readable game code)
  python3 devpack.py pack     -> re-compresses dev.game.js into dev.html (+ new build id)"""
import re, base64, gzip, sys, hashlib
H = open('dev.html', encoding='utf-8').read()
pat = re.compile(r'(<script type="text/plain" id="gamecode" data-z="gzip">)(.*?)(</script>)', re.S)
if sys.argv[1] == 'unpack':
    m = pat.search(H); open('dev.game.js', 'w', encoding='utf-8').write(gzip.decompress(base64.b64decode(m.group(2).strip())).decode('utf-8')); print('unpacked')
else:
    code = open('dev.game.js', encoding='utf-8').read(); m = pat.search(H)
    z = base64.b64encode(gzip.compress(code.encode('utf-8'), 9, mtime=0)).decode()
    out = H[:m.start()] + m.group(1) + z + m.group(3) + H[m.end():]
    bid = hashlib.sha1(out.encode()).hexdigest()[:8]
    out = re.sub(r'<meta name="build" content="[0-9a-f]+">', '<meta name="build" content="' + bid + '">', out, 1)
    open('dev.html', 'w', encoding='utf-8').write(out); print('packed build', bid, len(out))
