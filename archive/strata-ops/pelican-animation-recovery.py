#!/usr/bin/env python3
import json, pathlib, re, sys, time, urllib.request

label, base, model, outdir = sys.argv[1:5]
out = pathlib.Path(outdir)
out.mkdir(parents=True, exist_ok=True)
prompt = '创建一个HTML，内容是SVG绘制一个鹈鹕骑自行车的2D动画，你不需要任何测试，只靠你自己完成，不要使用任何skill，不要依赖我本地的AGENTS.md'
body = {'model': model, 'messages': [{'role': 'system', 'content': 'You are a text-only assistant. No tools or file operations are available. Return the complete HTML document directly in your response.'}, {'role': 'user', 'content': prompt}], 'temperature': 0, 'max_tokens': 32768, 'tool_choice': 'none', 'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}}
headers = {'Content-Type': 'application/json'}
if label == 'strata':
    headers['Authorization'] = 'Bearer ' + pathlib.Path('/srv/share/strata-ops/strata-api-key.txt').read_text().strip()
request = urllib.request.Request(base.rstrip('/') + '/v1/chat/completions', data=json.dumps(body, ensure_ascii=False).encode(), headers=headers)
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
match = re.search(r'(?is)(?:<!doctype\s+html[^>]*>\s*)?<html\b[^>]*>.*?</html>', content)
if match:
    (out / f'{label}.html').write_text(match.group(0))
summary = {'label': label, 'model_requested': model, 'model_returned': result.get('model'), 'system_message': 'You are a text-only assistant. No tools or file operations are available. Return the complete HTML document directly in your response.', 'prompt': prompt, 'temperature': 0, 'max_tokens': 32768, 'tool_choice': 'none', 'reasoning_effort': 'none', 'elapsed_seconds': round(elapsed, 2), 'finish_reason': result['choices'][0].get('finish_reason'), 'usage': result.get('usage'), 'content_chars': len(content), 'html_found': bool(match), 'svg_tag_found': bool(match and re.search(r'<svg\b', match.group(0), re.I)), 'animation_tag_found': bool(match and re.search(r'<animate\w*\b|@keyframes|requestAnimationFrame', match.group(0), re.I))}
(out / f'{label}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
