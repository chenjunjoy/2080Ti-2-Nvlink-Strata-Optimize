#!/usr/bin/env python3
import json, pathlib, re, sys, time, urllib.request, xml.etree.ElementTree as ET

label, base, model, outdir = sys.argv[1:5]
out = pathlib.Path(outdir)
out.mkdir(parents=True, exist_ok=True)
prompt = 'Generate an SVG of a pelican riding a bicycle'
body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0, 'max_tokens': 32768, 'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}}
headers = {'Content-Type': 'application/json'}
if label == 'strata':
    key = pathlib.Path('/srv/share/strata-ops/strata-api-key.txt').read_text().strip()
    headers['Authorization'] = 'Bearer ' + key
request = urllib.request.Request(base.rstrip('/') + '/v1/chat/completions', data=json.dumps(body).encode(), headers=headers)
start = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=1200) as response:
        result = json.load(response)
except Exception as exc:
    (out / f'{label}-error.txt').write_text(str(exc) + '\n')
    raise
elapsed = time.monotonic() - start
(out / f'{label}-response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
content = result['choices'][0]['message'].get('content') or ''
(out / f'{label}-content.md').write_text(content)
match = re.search(r'<svg\b[^>]*>.*?</svg>', content, re.I | re.S)
valid = False
if match:
    svg = match.group(0)
    (out / f'{label}.svg').write_text(svg)
    try:
        ET.fromstring(svg)
        valid = True
    except ET.ParseError:
        pass
summary = {'label': label, 'model_requested': model, 'model_returned': result.get('model'), 'prompt': prompt, 'temperature': 0, 'max_tokens': 32768, 'reasoning_effort': 'none', 'elapsed_seconds': round(elapsed, 2), 'finish_reason': result['choices'][0].get('finish_reason'), 'usage': result.get('usage'), 'content_chars': len(content), 'svg_found': bool(match), 'svg_xml_valid': valid}
(out / f'{label}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
