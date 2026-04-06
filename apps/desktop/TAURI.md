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

The current mascot is an INTP-style “小紫人” (a cute purple-haired girl). Tauri reads icon assets from `apps/desktop/src-tauri/icons`, where the high-resolution base is `icon.png` (the mascot illustration). Regenerate every platform-specific file (ICNS, ICO, PNG, Android, iOS, etc.) by running `npx tauri icon src-tauri/icons/icon.png`, then keep `bundle.icon` in `src-tauri/tauri.conf.json` pointed at `icons/icon.png`, `icons/icon.ico`, and `icons/icon.icns`. Rerun the CLI whenever you update the mascot art so all targets stay in sync.

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
