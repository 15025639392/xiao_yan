# Tauri Wrapper For `apps/desktop`

This directory is a Tauri shell that packages the existing Vite/React frontend as a native app.

## Prereqs

- Install Rust toolchain (`rustc`, `cargo`)
- Install platform build deps required by Tauri (varies by OS)

## Dev

```bash
cd apps/desktop
npm install
npm run tauri:dev
```

## Build

```bash
cd apps/desktop
npm run tauri:build
```

## Icons

Tauri reads icon assets from `apps/desktop/src-tauri/icons`. The high-resolution base is `icon.png`; we regenerate platform-specific files (ICNS, ICO, PNG, Android, iOS, etc.) with `npx tauri icon src-tauri/icons/icon.png`. Keep `bundle.icon` in `src-tauri/tauri.conf.json` pointing at the generated `icons/icon.png`, `icons/icon.ico`, and `icons/icon.icns` so each platform picks up the right source. Rerun the CLI whenever the base artwork changes.

## Getting Absolute Folder Paths (Recommended Pattern)

- Let the user pick a directory using a native dialog (frontend).
- Pass the chosen absolute path into the backend once, as the "allowed directory".
- Restrict all file IO to that allowed directory in the Tauri backend (avoid giving the webview unrestricted filesystem access).

### Backend Commands (Added)

- `fs_set_allowed_directory(dir: string) -> { allowed_dir: string | null }`
- `fs_get_allowed_directory() -> { allowed_dir: string | null }`
- `fs_clear_allowed_directory() -> { allowed_dir: string | null }`
- `fs_read_text_file(relPath: string) -> string`
- `fs_write_text_file(relPath: string, content: string) -> void`
- `fs_list_dir(relPath: string) -> string[]`

All file paths are sandboxed to the allowed directory and reject absolute paths or `..` traversal.
