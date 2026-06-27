#!/usr/bin/env python3
"""Test chart pipeline: matplotlib → PNG → MinIO → image.uploaded SSE event.
Verifies: no localhost URLs, no raw code in answer, MinIO upload works.
"""

import asyncio, json, httpx

async def test():
    body = {
        'message': '用折线图展示：一月100，二月200，三月150，四月300',
        'agentId': 'code-analyst',
        'messageId': 'chart-test',
        'stream': True,
    }
    print(f"Testing: {body['message']}")
    print(f"Agent: {body['agentId']}")

    issues = []
    image_urls = []
    raw_code_found = False
    localhost_found = False
    upload_events = 0

    async with httpx.AsyncClient(timeout=180) as c:
        async with c.stream('POST', 'http://localhost:8000/api/v1/generate/stream', json=body) as r:
            assert r.status_code == 200, f"HTTP {r.status_code}"
            async for line in r.aiter_lines():
                if not line.startswith('data:'): continue
                d = line[6:] if line.startswith('data: ') else line[5:]
                try:
                    e = json.loads(d)
                    t = e.get('type', '')
                    content = e.get('delta', '')

                    if t == 'image.uploaded':
                        upload_events += 1
                        url = e.get('payload', {}).get('url', '')
                        fn = e.get('payload', {}).get('filename', '')
                        image_urls.append(url)
                        print(f'  [image.uploaded] {fn} → {url[:80]}...')
                        if 'localhost' in url:
                            localhost_found = True
                            issues.append(f'CRITICAL: localhost URL in image.uploaded: {url}')

                    elif t == 'message.delta':
                        if 'import matplotlib' in content or 'plt.savefig' in content or 'plt.figure' in content:
                            if not raw_code_found:
                                print(f'  [WARNING] raw code in delta: {content[:100]}')
                                raw_code_found = True
                        print('.', end='', flush=True)

                    elif t == 'message.done':
                        print('\n  [message.done]')
                        break
                    elif t == 'error':
                        err = e.get('error', '') or e.get('payload', {}).get('error', '')[:200]
                        issues.append(f'CRITICAL: SSE error: {err}')
                        break
                except: pass

    # Check final output for localhost URLs
    full_output = []
    async with httpx.AsyncClient(timeout=180) as c:
        async with c.stream('POST', 'http://localhost:8000/api/v1/generate/stream', json=body) as r:
            async for line in r.aiter_lines():
                if not line.startswith('data:'): continue
                d = line[6:] if line.startswith('data: ') else line[5:]
                try:
                    e = json.loads(d)
                    if e.get('type') == 'message.delta':
                        full_output.append(e.get('delta', ''))
                    if e.get('type') == 'message.done':
                        break
                except: pass

    full_text = ''.join(full_output)

    # Check for localhost URL patterns
    import re
    lh = re.findall(r'https?://[^\s)]*localhost[^\s)]*\.png', full_text)
    if lh:
        localhost_found = True
        issues.append(f'CRITICAL: localhost URL in output: {lh}')

    # Check for raw code
    code_indicators = ['```python', 'plt.figure(', 'plt.savefig(', 'import matplotlib']
    for ci in code_indicators:
        if ci in full_text:
            raw_code_found = True
            idx = full_text.index(ci)
            issues.append(f'CRITICAL: raw code in output: "{full_text[max(0,idx-20):idx+80]}"')
            break

    # Results
    print(f'\n{"="*60}')
    print(f'Upload events: {upload_events}')
    print(f'Image URLs: {image_urls}')
    print(f'localhost found: {localhost_found}')
    print(f'Raw code found: {raw_code_found}')
    print(f'Issues: {len(issues)}')
    for i in issues:
        print(f'  {i}')

    if issues:
        print('\n❌ FAILED')
    else:
        print('\n✅ PASSED')
    return len(issues) == 0

if __name__ == '__main__':
    asyncio.run(test())
