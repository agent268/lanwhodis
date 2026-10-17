import sys
from pathlib import Path
sp = Path(sys.argv[1])
h = (sp / "design_language.html").read_text(encoding="utf-8")
i = h.index("</style>") + len("</style>")
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="color-scheme" content="light dark">\n')
out = head + h[:i].replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "") + "\n<style>html,body{margin:0}body{background:var(--bg)}</style>\n</head>\n<body>" + h[i:] + "\n</body>\n</html>\n"
(sp / "deckwork-design-language.html").write_text(out, encoding="utf-8")
print(len(out) // 1024, "KiB")
