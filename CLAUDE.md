# Adinatha Tamil-Brahmi

Font and transcription tooling for the Adinatha Tamil-Brahmi inscription corpus.

## Structure

- `Adinatha-Tamil-Brahmi-2.ufo/` — UFO font source, compiled to `master_ttf/`
- `variants.js` / `variants.json` — character variant data used by the picker
- `transcribe/index.html` — main personal transcription tool (43-page workflow)
- `transcribe/transcribe.html` — redirects to `index.html?mode=transcribe`
- `transcribe/publish.html` — read-only publication gallery
- `transcribe/brahmi-core.js` — shared rendering functions (renderCrop, renderLineCanvas, ImageDB)
- `build.bat` — legacy Windows build (use WSL Makefile instead)

## Builds

**Always use WSL** for font builds and tooling — not PowerShell.

```bash
# In WSL:
fontmake -u Adinatha-Tamil-Brahmi-2.ufo -o ttf --keep-overlaps
```

Goal: replace `build.bat` with a `Makefile` usable in WSL and on a Linux VPS.

## Related Projects

- **Jinavani** (Tamil-Brahmi mobile editor, 50 daily users): `C:\Users\vinod\Projects\jinavani`
  - Stack: Quasar 0.16 + Vue 2 + Cordova — **do not upgrade** (live users)
  - Planned: BrahmiPicker.vue, Transcribe screen, Game screen, Publish screen, PocketBase backend
