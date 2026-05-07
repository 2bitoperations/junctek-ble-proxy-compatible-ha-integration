# Contributing

## Making a release

Every version bump requires **three steps**. Missing any one of them means the release doesn't land in HACS.

### 1. Bump the version

Edit `custom_components/junctek_ble/manifest.json`:

```json
"version": "1.0.X"
```

### 2. Commit and push

```bash
git add ...
git commit -m "v1.0.X: <short description>"
git push
```

### 3. Create a GitHub Release

```bash
gh release create v1.0.X \
  --title "v1.0.X - <short description>" \
  --notes "<release notes>"
```

This step is required. The release workflow (`.github/workflows/release.yml`) only runs on `release: types: [published]` — it does **not** run on a plain `git push` or `git tag` push. The workflow packages `custom_components/junctek_ble/` into `junctek_ble.zip` and attaches it to the release, which is what HACS downloads.

### What "release notes" should contain

- One-line summary of the change
- Any user-visible behaviour change (sensor values, sign conventions, availability)
- Any configuration requirement change

### Version numbering

Patch version (`1.0.X`) for all changes until a stable 1.x baseline is established. No pre-release or development versions — each pushed release is intended to be functional.
