import json
import re

injected_file = 'output/injected_tokens.json'
try:
    with open(injected_file, 'r', encoding='utf-8') as f:
        tokens = json.load(f)
except Exception:
    with open('output/clip_tokens.json', 'r', encoding='utf-8') as f:
        tokens = json.load(f)
        
clip0_tokens = []
for t in tokens:
    if str(t.get('clipIndex')) == '0':
        # Apply the exact fixes requested by the user
        word = t['text'].strip().lower()
        
        # 1. get -> ~12.743
        if word == 'get' and abs(t['start'] - 12.47) < 0.1:
            t['end'] = 12.743
            print(f"Fixed 'get' -> {t['end']}")
            
        # 2. you -> 17.217
        elif word == 'you' and abs(t['start'] - 17.13) < 0.1:
            t['end'] = 17.217
            print(f"Fixed 'you' -> {t['end']}")
            
        # 3. of -> 18.296
        elif word == 'of' and abs(t['start'] - 18.21) < 0.1:
            t['end'] = 18.296
            print(f"Fixed 'of' -> {t['end']}")
            
        # 4. bat -> 18.736
        elif word == 'bat' and abs(t['start'] - 18.47) < 0.1:
            t['end'] = 18.736
            print(f"Fixed 'bat' -> {t['end']}")
            
        # 5. i -> 21.677
        elif word == 'i' and abs(t['start'] - 21.55) < 0.1:
            t['end'] = 21.677
            print(f"Fixed 'i' -> {t['end']}")
            
        clip0_tokens.append(t)

# Fix next tokens to avoid overlaps
for i in range(len(clip0_tokens) - 1):
    cur = clip0_tokens[i]
    nxt = clip0_tokens[i+1]
    if cur['end'] > nxt['start'] - 0.002:
        nxt['start'] = round(cur['end'] + 0.002, 4)

js_code = f"""// === CLIP 0 INJECTOR ===
(function() {{
    const newTokens = {json.dumps(clip0_tokens, indent=2)};
    
    // Find target storage key
    let targetKey = null;
    for (let i = 0; i < localStorage.length; i++) {{
        const k = localStorage.key(i);
        if (k && k.startsWith('pulsar_align_clip_')) {{
            targetKey = k;
            break; // We'll just target the first one since it's clip 0
        }}
    }}
    
    // Inject directly into state
    if (window.state && window.state.tokens) {{
        // Filter out existing clip 0 tokens
        state.tokens = state.tokens.filter(t => String(t.clipIndex) !== '0');
        // Add our new tokens
        state.tokens = state.tokens.concat(newTokens);
        
        state.tokens.sort((a, b) => a.start - b.start);
        
        if (!state.tokenStats) state.tokenStats = {{}};
        for (const t of state.tokens) {{
            if (!state.tokenStats[t.id]) {{
                state.tokenStats[t.id] = {{ played: false, selectedCount: 0 }};
            }}
        }}
        
        // Save to storage
        if (targetKey) {{
            localStorage.setItem(targetKey, JSON.stringify({{ tokens: state.tokens }}));
        }}
        
        try {{ if (window.renderAll) window.renderAll(); }} catch(e) {{}}
        console.log('[Clip 0 Injector] Successfully injected ' + newTokens.length + ' tokens!');
    }} else {{
        console.error('window.state not found.');
    }}
}})();
"""

with open('output/clip0_injector.js', 'w', encoding='utf-8') as f:
    f.write(js_code)

print("Generated output/clip0_injector.js")
