#!/usr/bin/env python3
"""
gen_features.py — regenerate outputs from variants.yaml.

Usage:  python gen_features.py [--check]
  --check   verify glyphs, report unclassified variant-pattern glyphs, no writes.

Outputs:
  features.fea         — VS substitution block in akhn  (# <<VS_START>> / # <<VS_END>>)
  glyphs/*.glif        — composite glyphs for cross-product variants (compose: entries)
  glyphs/contents.plist — updated with new composite glyph entries
  variants.js          — window.ATB data for test_page.html
  variants.json        — same data as JSON for Jinavani (Vue)
"""

import re, sys, os, json
import xml.etree.ElementTree as ET
import yaml

ROOT       = os.path.dirname(os.path.abspath(__file__))
YAML_PATH  = os.path.join(ROOT, 'variants.yaml')
FEA_PATH   = os.path.join(ROOT, 'Adinatha-Tamil-Brahmi-2.ufo', 'features.fea')
JS_PATH    = os.path.join(ROOT, 'variants.js')
JSON_PATH  = os.path.join(ROOT, 'variants.json')
PLIST_PATH = os.path.join(ROOT, 'Adinatha-Tamil-Brahmi-2.ufo', 'glyphs', 'contents.plist')
GLYPHS_DIR = os.path.join(ROOT, 'Adinatha-Tamil-Brahmi-2.ufo', 'glyphs')

VS_START   = '# <<VS_START>>'
VS_END     = '# <<VS_END>>'
DIST_START = '# <<DIST_START>>'
DIST_END   = '# <<DIST_END>>'

# VS1-VS16: U+FE00-U+FE0F  |  VS17-VS256: U+E0100-U+E01EF
def _vs_char(n):
    """Return the Unicode character for VS n (1-indexed). 0 = no VS (default)."""
    if n == 0:  return ''
    if n <= 16: return chr(0xFE00 + n - 1)
    return chr(0xE0100 + n - 17)

def _vs_codepoint_hex(n):
    if n <= 16: return f'{0xFE00 + n - 1:04X}'
    return f'{0xE0100 + n - 17:05X}'

# Build lookup list (index = VS number, 0 = default)
VS_CHARS = [_vs_char(i) for i in range(257)]  # VS0-VS256

# ── helpers ───────────────────────────────────────────────────────────────────

def parse_fea_classes(fea_text):
    classes = {}
    for m in re.finditer(r'@(\w+)\s*=\s*\[([^\]]+)\]', fea_text, re.DOTALL):
        classes[m.group(1)] = m.group(2).split()
    return classes

def resolve_after(spec, classes):
    """Resolve @classname or explicit list to base glyph names (no variants)."""
    if spec is None:
        return None
    if isinstance(spec, str) and spec.startswith('@'):
        name = spec[1:]
        if name not in classes:
            print(f'WARNING: class {spec} not found in features.fea', file=sys.stderr)
            return []
        raw = classes[name]
    elif isinstance(spec, list):
        raw = list(spec)
    else:
        print(f'WARNING: unrecognised after value: {spec!r}', file=sys.stderr)
        return None
    return list(dict.fromkeys(g for g in raw if '.' not in g))

def patch_blank_class(fea_text, new_vs_glyphs):
    """Insert new VS glyph names into the @blank class definition."""
    if not new_vs_glyphs:
        return fea_text
    def replacer(m):
        existing = set(m.group(1).split())
        to_add = sorted(g for g in new_vs_glyphs if g not in existing)
        if not to_add:
            return m.group(0)
        return '@blank = [' + m.group(1).rstrip() + ' ' + ' '.join(to_add) + '];'
    result, n = re.subn(r'@blank\s*=\s*\[([^\]]+)\];', replacer, fea_text)
    if n == 0:
        print('WARNING: @blank class not found in features.fea', file=sys.stderr)
    return result

def patch_between(text, start_marker, end_marker, new_content):
    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    replacement = start_marker + '\n' + new_content + '\n' + end_marker
    result, n = re.subn(pattern, replacement, text, flags=re.DOTALL)
    if n == 0:
        raise ValueError(f'Markers not found: {start_marker!r} … {end_marker!r}')
    return result

def _js_str(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"

# ── GLIF helpers ──────────────────────────────────────────────────────────────

def _glif_path(glyph_name, contents):
    fname = contents.get(glyph_name)
    return os.path.join(GLYPHS_DIR, fname) if fname else None

def _read_advance(path):
    root = ET.parse(path).getroot()
    adv = root.find('advance')
    return round(float(adv.get('width', 0))) if adv is not None else 0

def _read_anchors(path):
    root = ET.parse(path).getroot()
    return {a.get('name'): (float(a.get('x', 0)), float(a.get('y', 0)))
            for a in root.findall('anchor') if a.get('name')}

def _sign_offset(base_path, sign_path):
    """(xOffset, yOffset) via mark-to-base anchors, fallback to base advance width."""
    ba = _read_anchors(base_path)
    sa = _read_anchors(sign_path)
    # Convention: base anchor "foo", mark anchor "_foo"
    for name, (bx, by) in ba.items():
        mn = '_' + name
        if mn in sa:
            return round(bx - sa[mn][0]), round(by - sa[mn][1])
    # Fallback: place sign after base
    return _read_advance(base_path), 0

def _safe_filename(glyph_name, existing):
    try:
        from fontTools.ufoLib import userNameToFileName
        return userNameToFileName(glyph_name, existing=existing, suffix='.glif')
    except ImportError:
        stem = re.sub(r'[^a-zA-Z0-9_]', '_', glyph_name)
        fn = stem + '.glif'
        n = 2
        while fn in existing:
            fn = stem + str(n) + '.glif'
            n += 1
        return fn

def _ensure_vs_glyph(vs_num, contents, glyphs_dir, existing_files):
    """Create VS17+ glyph in the UFO if it doesn't already exist."""
    if vs_num <= 16:
        return False  # VS1-VS16 already in font
    glyph_name = f'VS{vs_num}'
    if glyph_name in contents:
        return False
    cp_hex = _vs_codepoint_hex(vs_num)
    glif = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<glyph name="{n}" format="2">\n'
        '  <advance width="0"/>\n'
        '  <unicode hex="{u}"/>\n'
        '</glyph>\n'
    ).format(n=glyph_name, u=cp_hex)
    fname = _safe_filename(glyph_name, existing_files)
    with open(os.path.join(glyphs_dir, fname), 'w', encoding='utf-8') as f:
        f.write(glif)
    contents[glyph_name] = fname
    existing_files.add(fname)
    print(f'  Added glyph: {glyph_name} (U+{cp_hex})')
    return True

def _read_bbox(path):
    """Return (min_x, min_y, max_x, max_y) of all contour points, or None if no contours."""
    root = ET.parse(path).getroot()
    pts = [(float(p.get('x', 0)), float(p.get('y', 0)))
           for p in root.findall('.//point') if p.get('x') is not None]
    if not pts:
        return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)

# Zone thresholds from fontinfo guidelines
_ZONE_MID = 512    # "m" guideline
_ZONE_TOP = 1432   # "tall_cons_var" guideline

def _y_zones(y_min, y_max):
    """Return set of zone names ('bot', 'mid', 'top') the y range covers."""
    z = set()
    if y_min < _ZONE_MID:  z.add('bot')
    if y_max >= _ZONE_MID and y_min < _ZONE_TOP: z.add('mid')
    if y_max >= _ZONE_TOP: z.add('top')
    return z

def _write_composite_glif(path, name, base_g, sign_g, xoff, yoff, width):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<glyph name="{n}" format="2">\n'
            '  <advance width="{w}"/>\n'
            '  <outline>\n'
            '    <component base="{b}"/>\n'
            '    <component base="{s}" xOffset="{x}" yOffset="{y}"/>\n'
            '  </outline>\n'
            '</glyph>\n'.format(n=name, w=width, b=base_g, s=sign_g, x=xoff, y=yoff)
        )

# ── dist auto-generation ─────────────────────────────────────────────────────

def _sign_info(data, contents):
    """Return list of (glyph_name, mx, sign_min_x, sign_min_y, sign_max_y) for
    left-protruding signs (base + variants). Skips signs with no contours or no _base anchor."""
    result = []
    for s in data.get('signs', []):
        for sg in [s['glyph']] + [v['glyph'] for v in s.get('variants', [])]:
            sp = _glif_path(sg, contents)
            if not sp or not os.path.exists(sp):
                continue
            sa = _read_anchors(sp)
            bb = _read_bbox(sp)
            if bb is None:
                continue
            mx = next((v[0] for k, v in sa.items() if k.startswith('_')), None)
            if mx is None:
                continue
            min_x, min_y, max_x, max_y = bb
            if mx - min_x > 0:   # protrudes left of attachment point
                result.append((sg, mx, min_x, min_y, max_y))
    return result

def _cons_info(data, contents):
    """Return list of (glyph_name, ax, cons_min_x) for consonants + variants."""
    result = []
    for section in ('consonants', 'independent_vowels'):
        for c in data.get(section, []):
            for cg in [c['glyph']] + [v['glyph'] for v in c.get('variants', [])]:
                cp = _glif_path(cg, contents)
                if not cp or not os.path.exists(cp):
                    continue
                ca = _read_anchors(cp)
                ax = next((v[0] for k, v in ca.items() if not k.startswith('_')), None)
                if ax is None:
                    continue
                bb = _read_bbox(cp)
                cons_min_x = bb[0] if bb else 0
                result.append((cg, ax, cons_min_x))
    return result

def gen_dist_auto(data, contents):
    """Generate dist lookup for left-protruding signs.

    Adjustment = max(0, sign_overhang - (cons_anchor_x - cons_bbox_left))
    Only emits rules where the sign actually extends past the consonant's ink left edge.
    Skips (cons, sign) pairs where the sign's y-range is entirely in the top zone
    (y > 1432) and the consonant has no ink there — no real visual collision.
    """
    signs = _sign_info(data, contents)
    cons  = _cons_info(data, contents)

    rules = []
    for sg, mx, s_min_x, s_min_y, s_max_y in signs:
        sign_zones = _y_zones(s_min_y, s_max_y)
        overhang = mx - s_min_x
        for cg, ax, c_min_x in cons:
            # sign left edge relative to consonant origin = ax - mx + s_min_x
            sign_left = ax - mx + s_min_x
            adj = max(0, round(c_min_x - sign_left))
            if adj <= 0:
                continue
            # skip if sign only in top zone (pulli/top mark won't collide with consonant body)
            if sign_zones == {'top'}:
                continue
            rules.append((cg, sg, adj))

    lines = ['# Auto-generated by gen_features.py — edit variants.yaml, not this block', '']
    if rules:
        lines.append('lookup dist_auto {')
        for cg, sg, adj in sorted(rules, key=lambda r: (-r[2], r[0], r[1])):
            lines.append(f"  pos @noblank' {cg} {sg} {adj};")
        lines.append('} dist_auto;')
        lines.append('')
        lines.append('lookup dist_auto;')
        print(f'  dist_auto: {len(rules)} pair rule(s) generated')
    else:
        lines.append('# no left-protruding sign adjustments needed')

    return '\n'.join(lines)

def report_dist(data, contents):
    """Print a human-readable collision report for left-protruding signs."""
    signs = _sign_info(data, contents)
    cons  = _cons_info(data, contents)

    print()
    print('LEFT-PROTRUDING SIGN COLLISION REPORT')
    print('=' * 60)

    for sg, mx, s_min_x, s_min_y, s_max_y in signs:
        overhang = mx - s_min_x
        sign_zones = _y_zones(s_min_y, s_max_y)
        zone_str = '+'.join(sorted(sign_zones))
        print(f'\n  {sg:25s}  overhang={overhang:4.0f}  zones={zone_str}')

        collisions = []
        for cg, ax, c_min_x in cons:
            sign_left = ax - mx + s_min_x
            adj = max(0, round(c_min_x - sign_left))
            if adj > 0:
                skipped = ' [SKIP: top-only zone]' if sign_zones == {'top'} else ''
                collisions.append((cg, adj, skipped))

        if not collisions:
            print(f'    -> no collisions past bbox_left')
        else:
            for cg, adj, note in sorted(collisions, key=lambda r: -r[1]):
                print(f'    -> {cg:20s}  +{adj}{note}')

    print()

# ── composite generation ──────────────────────────────────────────────────────

def _all_composite_names(data):
    """Enumerate glyph names gen_composites would produce, without writing anything."""
    def variants_of(glyph_name):
        for section in ('consonants', 'independent_vowels', 'signs'):
            for e in data.get(section, []):
                if e['glyph'] == glyph_name:
                    result = [(glyph_name, 0)]
                    for v in e.get('variants', []):
                        if v.get('vs'):
                            result.append((v['glyph'], v['vs']))
                    return result
        return [(glyph_name, 0)]

    names = set()
    for section in ('consonants', 'independent_vowels'):
        for entry in data.get(section, []):
            if 'compose' not in entry:
                continue
            base_g, sign_g = entry['compose']
            parent_g = entry['glyph']
            for _, b_vs in variants_of(base_g):
                for _, s_vs in variants_of(sign_g):
                    if b_vs == 0 and s_vs == 0:
                        continue
                    b_suf = '' if b_vs == 0 else f'.b{b_vs}'
                    s_suf = '' if s_vs == 0 else f'.s{s_vs}'
                    names.add(parent_g + b_suf + s_suf)
    return names

def gen_composites(data, plist_path, glyphs_dir):
    """Generate composite glyphs for all entries with compose: [BASE, SIGN].

    Composites are named PARENT.bN.sM where N = base variant VS num,
    M = sign variant VS num (suffix omitted when variant is default).
    VS numbering starts after the last explicit variant in the entry.

    Returns:
      composite_rules  — list of "sub PARENT VSn by COMP;" strings for akhn
      composite_cvs    — {parent_glyph: [{glyph, label, vs}, ...]} for JS/JSON
    """
    import plistlib
    with open(plist_path, 'rb') as f:
        contents = plistlib.load(f)
    existing_files = set(contents.values())
    plist_dirty = False

    def variants_of(glyph_name):
        for section in ('consonants', 'independent_vowels', 'signs'):
            for e in data.get(section, []):
                if e['glyph'] == glyph_name:
                    result = [(glyph_name, 0, 'default')]
                    for v in e.get('variants', []):
                        if v.get('vs'):
                            result.append((v['glyph'], v['vs'], v['label']))
                    return result
        return [(glyph_name, 0, 'default')]

    offset_cache = {}
    def get_offset(b_g, s_g):
        key = (b_g, s_g)
        if key not in offset_cache:
            bp = _glif_path(b_g, contents)
            sp = _glif_path(s_g, contents)
            if bp and sp and os.path.exists(bp) and os.path.exists(sp):
                xoff, yoff = _sign_offset(bp, sp)
                s_adv = _read_advance(sp)
                b_adv = _read_advance(bp)
                width = (xoff + s_adv) if s_adv > 0 else b_adv
            else:
                print(f'  WARNING: GLIF not found for {b_g!r} or {s_g!r}', file=sys.stderr)
                xoff, yoff, width = 0, 0, 500
            offset_cache[key] = (xoff, yoff, width)
        return offset_cache[key]

    composite_rules = []
    composite_cvs   = {}
    new_vs_glyphs   = set()

    for section in ('consonants', 'independent_vowels'):
        for entry in data.get(section, []):
            if 'compose' not in entry:
                continue
            base_g, sign_g = entry['compose']
            parent_g = entry['glyph']

            base_vars = variants_of(base_g)
            sign_vars = variants_of(sign_g)

            # VS numbering starts after the highest explicit variant
            explicit_max = max(
                (v['vs'] for v in entry.get('variants', []) if v.get('vs')),
                default=0
            )
            vs_num = explicit_max + 1
            parent_cvs = []

            for b_glyph, b_vs, b_label in base_vars:
                for s_glyph, s_vs, s_label in sign_vars:
                    if b_vs == 0 and s_vs == 0:
                        continue  # default×default = the parent glyph itself

                    b_suf = '' if b_vs == 0 else f'.b{b_vs}'
                    s_suf = '' if s_vs == 0 else f'.s{s_vs}'
                    comp_name = parent_g + b_suf + s_suf

                    b_lbl = b_label if b_label != 'default' else '—'
                    s_lbl = s_label if s_label != 'default' else '—'
                    label  = f'{b_lbl}+{s_lbl}'

                    if vs_num > 256:
                        print(f'  SKIP {comp_name}: VS{vs_num} exceeds VS256 (max)', file=sys.stderr)
                        vs_num += 1
                        continue

                    if _ensure_vs_glyph(vs_num, contents, glyphs_dir, existing_files):
                        plist_dirty = True
                        new_vs_glyphs.add(f'VS{vs_num}')

                    if comp_name not in contents:
                        xoff, yoff, width = get_offset(b_glyph, s_glyph)
                        fname = _safe_filename(comp_name, existing_files)
                        fpath = os.path.join(glyphs_dir, fname)
                        _write_composite_glif(fpath, comp_name,
                                              b_glyph, s_glyph, xoff, yoff, width)
                        contents[comp_name] = fname
                        existing_files.add(fname)
                        plist_dirty = True
                        print(f'  Composite {comp_name}: {b_glyph} + {s_glyph} @ x={xoff}')
                    else:
                        # Already exists — update offset in case advance changed
                        # (only if GLIF file is present)
                        fpath = os.path.join(glyphs_dir, contents[comp_name])
                        if os.path.exists(fpath):
                            xoff, yoff, width = get_offset(b_glyph, s_glyph)
                            _write_composite_glif(fpath, comp_name,
                                                  b_glyph, s_glyph, xoff, yoff, width)

                    composite_rules.append(f'sub {parent_g} VS{vs_num} by {comp_name};')
                    parent_cvs.append({'glyph': comp_name, 'label': label, 'vs': vs_num})
                    vs_num += 1

            if parent_cvs:
                composite_cvs[parent_g] = parent_cvs

    if plist_dirty:
        with open(plist_path, 'wb') as f:
            plistlib.dump(contents, f)
        print(f'Updated  {os.path.relpath(plist_path)}')

    return composite_rules, composite_cvs, new_vs_glyphs

# ── feature generation ────────────────────────────────────────────────────────

def gen_vs_rules(data, classes, composite_rules=None):
    lines = ['# Auto-generated by gen_features.py — edit variants.yaml, not this block', '']
    lines.append('# Consonant VS substitutions')
    for c in data.get('consonants', []):
        for v in c.get('variants', []):
            if v.get('vs'):
                lines.append(f"sub {c['glyph']} VS{v['vs']} by {v['glyph']};")
    lines.append('')
    lines.append('# Independent vowel VS substitutions')
    for iv in data.get('independent_vowels', []):
        for v in iv.get('variants', []):
            if v.get('vs'):
                lines.append(f"sub {iv['glyph']} VS{v['vs']} by {v['glyph']};")
    lines.append('')
    lines.append('# Vowel sign VS substitutions')
    for s in data.get('signs', []):
        for v in s.get('variants', []):
            if v.get('vs'):
                lines.append(f"sub {s['glyph']} VS{v['vs']} by {v['glyph']};")
    if composite_rules:
        lines.append('')
        lines.append('# Composite VS substitutions (auto-generated from compose:)')
        lines.extend(composite_rules)
    return '\n'.join(lines)

# ── shared data builders ──────────────────────────────────────────────────────

def _build_cons(data, composite_cvs=None):
    """Return list of consonant/vowel dicts with resolved unicode chars.
    Includes independent_vowels that have explicit variants or compose: entries.
    """
    vs_chars = VS_CHARS
    result = []
    for section in ('consonants', 'independent_vowels'):
        for c in data.get(section, []):
            explicit = [v for v in c.get('variants', []) if v.get('vs')]
            comp     = (composite_cvs or {}).get(c.get('glyph', ''), [])
            if section == 'independent_vowels' and not explicit and not comp:
                continue  # skip vowels with no variants at all

            cvs = [{'l': 'default', 'vs': ''}]
            for v in explicit:
                cvs.append({'l': v['label'], 'vs': vs_chars[v['vs']]})
            for cv in comp:
                if cv['vs'] < len(vs_chars):
                    cvs.append({'l': cv['label'], 'vs': vs_chars[cv['vs']]})

            result.append({
                'n':   c['name'],
                'u':   chr(int(c['unicode'], 16)),
                'syl': c.get('syllable', True),
                'cvs': cvs,
            })
    return result

def _build_vsigns(data, classes):
    """Return list of sign dicts with resolved unicode chars and after/exclude lists."""
    vs_chars = VS_CHARS
    result = []
    for s in data.get('signs', []):
        cvs = [{'l': 'default', 'vs': ''}]
        for v in s.get('variants', []):
            if not v.get('vs'):
                continue
            entry = {'l': v['label'], 'vs': vs_chars[v['vs']]}
            after = resolve_after(v.get('after'), classes)
            if after is not None:
                entry['after'] = after
            exclude = resolve_after(v.get('exclude'), classes)
            if exclude is not None:
                entry['exclude'] = exclude
            cvs.append(entry)
        result.append({'n': s['name'], 'u': chr(int(s['unicode'], 16)), 'cvs': cvs})
    return result

# ── variants.js ───────────────────────────────────────────────────────────────

def _json_to_js(obj):
    if isinstance(obj, bool):
        return 'true' if obj else 'false'
    if obj is None:
        return 'null'
    if isinstance(obj, str):
        return _js_str(obj)
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, list):
        return '[' + ','.join(_json_to_js(i) for i in obj) + ']'
    if isinstance(obj, dict):
        pairs = ','.join(k + ':' + _json_to_js(v) for k, v in obj.items())
        return '{' + pairs + '}'
    raise TypeError(type(obj))

def gen_variants_js(cons, vsigns):
    lines = [
        '// Auto-generated by gen_features.py — edit variants.yaml, not this file',
        '(function () {',
        '  var S = String.fromCodePoint;',
        "  var V = [''," + ','.join(f'S(0x{0xFE00+i:04X})' for i in range(16)) +
        ',' + ','.join(f'S(0x{0xE0100+i:05X})' for i in range(240)) + '];',
        '',
    ]

    def u_ref(char):
        return f'S(0x{ord(char):05X})'

    def vs_ref(char):
        if not char:
            return 'V[0]'
        cp = ord(char)
        idx = (cp - 0xFE00 + 1) if cp <= 0xFE0F else (cp - 0xE0100 + 17)
        return f'V[{idx}]'

    cons_js = []
    for c in cons:
        cvs_parts = []
        for cv in c['cvs']:
            after_part   = ',after:['   + ','.join(_js_str(g) for g in cv['after'])   + ']' if 'after'   in cv else ''
            exclude_part = ',exclude:[' + ','.join(_js_str(g) for g in cv['exclude']) + ']' if 'exclude' in cv else ''
            cvs_parts.append('{l:' + _js_str(cv['l']) + ',vs:' + vs_ref(cv['vs']) + after_part + exclude_part + '}')
        syl = 'false' if c['syl'] is False else 'true'
        cons_js.append(
            '    {n:' + _js_str(c['n']) + ',u:' + u_ref(c['u']) + ',syl:' + syl +
            ',cvs:[' + ','.join(cvs_parts) + ']}'
        )

    signs_js = []
    for s in vsigns:
        cvs_parts = []
        for cv in s['cvs']:
            after_part   = ',after:['   + ','.join(_js_str(g) for g in cv['after'])   + ']' if 'after'   in cv else ''
            exclude_part = ',exclude:[' + ','.join(_js_str(g) for g in cv['exclude']) + ']' if 'exclude' in cv else ''
            cvs_parts.append('{l:' + _js_str(cv['l']) + ',vs:' + vs_ref(cv['vs']) + after_part + exclude_part + '}')
        signs_js.append(
            '    {n:' + _js_str(s['n']) + ',u:' + u_ref(s['u']) +
            ',cvs:[' + ','.join(cvs_parts) + ']}'
        )

    lines.append('  window.ATB = {')
    lines.append('    V: V,')
    lines.append('    cons: [')
    lines.append(',\n'.join(cons_js))
    lines.append('    ],')
    lines.append('    vsigns: [')
    lines.append(',\n'.join(signs_js))
    lines.append('    ]')
    lines.append('  };')
    lines.append('})();')
    return '\n'.join(lines)

# ── variants.json ─────────────────────────────────────────────────────────────

def gen_variants_json(cons, vsigns):
    return json.dumps({'cons': cons, 'vsigns': vsigns}, ensure_ascii=False, indent=2)

# ── verification ──────────────────────────────────────────────────────────────

def verify(data, plist_path):
    import plistlib
    with open(plist_path, 'rb') as f:
        contents = plistlib.load(f)
    all_glyphs = set(contents.keys())
    errors = 0
    for section in ('consonants', 'signs', 'independent_vowels'):
        for entry in data.get(section, []):
            for v in entry.get('variants', []):
                if v['glyph'] not in all_glyphs:
                    print(f'ERROR: glyph not in font: {v["glyph"]}', file=sys.stderr)
                    errors += 1
    classified = _all_composite_names(data)
    for section in ('consonants', 'signs', 'independent_vowels'):
        for entry in data.get(section, []):
            classified.add(entry['glyph'])
            for v in entry.get('variants', []): classified.add(v['glyph'])
            for g in entry.get('contextual', []): classified.add(g)
    pat = re.compile(r'.+\.(\d+$|protr|alt|stub|mid|inv|top|left|inside|corner|vert|horiz|long|bot)')
    unclassified = sorted(g for g in all_glyphs if pat.match(g) and g not in classified)
    if unclassified:
        print('WARNING: variant-pattern glyphs not in variants.yaml:')
        for g in unclassified:
            print(f'  {g}')
    return errors

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    check_only   = '--check'       in sys.argv
    report_only  = '--report-dist' in sys.argv
    data    = yaml.safe_load(open(YAML_PATH, encoding='utf-8'))
    fea     = open(FEA_PATH, encoding='utf-8').read()
    classes = parse_fea_classes(fea)

    errors = verify(data, PLIST_PATH)
    if errors:
        print(f'{errors} error(s) — fix before regenerating.', file=sys.stderr)
        sys.exit(1)
    if check_only:
        print('Check passed (no writes).')
        return

    if report_only:
        import plistlib as _plr
        with open(PLIST_PATH, 'rb') as _fr:
            _cr = _plr.load(_fr)
        report_dist(data, _cr)
        return

    print('Generating composite glyphs...')
    # Pre-create VS17-VS26 glyphs so they're always available
    import plistlib as _pl
    with open(PLIST_PATH, 'rb') as _f:
        _c = _pl.load(_f)
    _existing = set(_c.values())
    _dirty = False
    for _n in range(17, 27):
        if _ensure_vs_glyph(_n, _c, GLYPHS_DIR, _existing):
            _dirty = True
    if _dirty:
        with open(PLIST_PATH, 'wb') as _f:
            _pl.dump(_c, _f)
        print(f'Updated  {os.path.relpath(PLIST_PATH)}')

    composite_rules, composite_cvs, new_vs_glyphs = gen_composites(data, PLIST_PATH, GLYPHS_DIR)

    fea_new = patch_between(fea, VS_START, VS_END,
                            gen_vs_rules(data, classes, composite_rules))
    vs17plus = {f'VS{n}' for n in range(17, 27)}
    fea_new = patch_blank_class(fea_new, vs17plus)

    print('Generating dist rules...')
    import plistlib as _pl3
    with open(PLIST_PATH, 'rb') as _f3:
        _contents_dist = _pl3.load(_f3)
    fea_new = patch_between(fea_new, DIST_START, DIST_END,
                            gen_dist_auto(data, _contents_dist))

    open(FEA_PATH, 'w', encoding='utf-8').write(fea_new)
    print(f'Updated  {os.path.relpath(FEA_PATH)}')

    cons   = _build_cons(data, composite_cvs)
    vsigns = _build_vsigns(data, classes)

    open(JS_PATH,   'w', encoding='utf-8').write(gen_variants_js(cons, vsigns))
    print(f'Written  {os.path.relpath(JS_PATH)}')

    open(JSON_PATH, 'w', encoding='utf-8').write(gen_variants_json(cons, vsigns))
    print(f'Written  {os.path.relpath(JSON_PATH)}')

    print('Done. Run build.bat to recompile the font.')

if __name__ == '__main__':
    main()
