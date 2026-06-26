# variants.yaml — Schema Reference

Single source of truth for all glyph variant mappings in Adinatha Tamil Brahmi.
`gen_features.py` reads this file and regenerates:
- The VS substitution block inside `akhn` in `Adinatha-Tamil-Brahmi-2.ufo/features.fea`
- `variants.js` — sets `window.ATB` for `test_page.html`
- `variants.json` — same data as JSON for Jinavani (Vue)

Run `python gen_features.py` after any change, then `build.bat` to recompile.

---

## Top-level keys

| Key | Description |
|-----|-------------|
| `consonants` | Base consonant glyphs and their selectable variants |
| `independent_vowels` | Independent vowel glyphs (some decompose via ccmp) |
| `signs` | Vowel sign glyphs and their selectable variants |

---

## Entry structure

```yaml
- name: WI              # display name (may be Unicode character for signs: "ā", "i")
  glyph: WI             # glyph name in the UFO — must match features.fea and contents.plist
  unicode: "0x1103A"    # Unicode codepoint as hex string
  variants:
    - glyph: WI.protr.alt    # variant glyph name
      label: protr.          # short label shown in test page column headers
      vs: 1                  # VS number 1–16  (VS1=U+FE00 … VS16=U+FE0F)
      after: "@mid_alt_cons_ae"   # optional — see below
  contextual:           # shaping-internal forms: no VS, no warning
    - WI.stub
    - WI.stub.mid
```

---

## `variants` fields

| Field | Required | Description |
|-------|----------|-------------|
| `glyph` | yes | Exact glyph name in the font |
| `label` | yes | Short display string for the test page |
| `vs` | yes | Variation Selector number (1–16). Gap-safe: TTA uses VS1, VS2, VS4 |
| `after` | no | Whitelist context — see below. VS rule is always unconditional |
| `exclude` | no | Blacklist context — see below. VS rule is always unconditional |

---

## `after` and `exclude` fields

Both fields are **documentary only** — the VS substitution rule is always unconditional.
They are used by the test page to mark cells in the sign variant table.

`after` — **whitelist**: variant is designed for these consonants only; cells for other consonants are left empty.  
`exclude` — **blacklist**: variant works after any consonant *except* these; those cells are left empty.

(Using both on the same variant entry is not recommended — pick one.)

Values for either field:
- `"@classname"` — resolved to glyph names via `@classname = [...]` in features.fea at run time
- `[GLYPH, ...]` — explicit list of base consonant glyph names
- Omitted — no restriction; all cells shown at full opacity

---

## `contextual` list

Glyphs selected automatically by the shaping engine based on positional context
(e.g. `.mid`, `.stub`, `.vert.corner`, `.horiz.long*` forms). They have:
- No VS rule
- No cv feature
- No warning from `gen_features.py`

---

## `compose` field

```yaml
- name: AA
  glyph: AA
  unicode: "0x11006"
  compose: [A, WAA]
  variants:
    - { glyph: AA.1, label: AA.1, vs: 1 }
```

Declares that this glyph is composed of two components: a base letter and a vowel sign.
`gen_features.py` reads this field and automatically:

1. Cross-products every variant of `A` with every variant of `WAA` (excluding default×default)
2. Writes a composite `.glif` for each combination (e.g. `AA.b1`, `AA.s1`, `AA.b1.s1`)
3. Positions the sign component using mark-to-base anchor data from the UFO
4. Registers each composite in `contents.plist`
5. Emits `sub AA VSn by AA.bX.sY;` rules in the akhn block

VS numbering for composites starts after the last explicit `variants:` entry.
Composite glyph names follow the pattern `PARENT.bN.sM` where N = base variant VS, M = sign variant VS (suffix omitted when default).

Adding a new A variant or WAA variant to `variants:` in the yaml automatically
produces new composite glyphs on the next `gen_features.py` run.

No ccmp rule is generated or needed — the default (no VS) renders the parent glyph as-is.

---

## VS numbering convention

Suffix number = VS number where possible:

- `KA.1` → VS1, `KA.2` → VS2, … `KA.5` → VS5
- Gaps are allowed: `TTA` has VS1, VS2, VS4 (no `TTA.3` exists → VS3 is unused)
- `MA` skips VS6 (no `MA.6`): MA.7 → VS7, MA.8 → VS8
- Maximum VS16 (U+FE0F)

---

## Workflow for adding a new variant

1. Draw the new glyph in the UFO editor and name it (e.g. `KA.6`)
2. Add one line under the correct entry in `variants.yaml`:
   ```yaml
   - { glyph: KA.6, label: KA.6, vs: 6 }
   ```
3. Run `python gen_features.py` — updates features.fea and test_page.html
4. Run `build.bat` — recompiles the font
5. Reload the test page and check the Consonant Variants and Sign Variants tabs

For a contextual-only glyph (no VS), add it to `contextual:` instead to suppress warnings.
