from __future__ import annotations

import json
from pathlib import Path

from app.domain.models import ProjectSnapshot

COMMON_ENTRY_FILES = (
    "src/main.tsx",
    "src/main.ts",
    "src/index.tsx",
    "src/index.ts",
    "src/App.tsx",
    "src/App.ts",
    "src-tauri/src/main.rs",
    "src/main.py",
    "main.py",
    "index.js",
    "index.ts",
    "app.py",
)
COMMON_KEY_DIRS = (
    "src",
    "src-tauri",
    "apps",
    "services",
    "tests",
    "test",
    "scripts",
    "packages",
)


class ProjectContextBuilder:
    def build(self, project_path: str) -> ProjectSnapshot:
        root = Path(project_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("project path must point to an existing directory")

        package_json = self._load_package_json(root)
        package_manager = self._detect_package_manager(root)
        framework = self._detect_framework(root, package_json)
        entry_files = self._detect_entry_files(root)
        key_directories = [candidate for candidate in COMMON_KEY_DIRS if (root / candidate).exists()]
        repository_root = self._detect_repository_root(root)
        test_commands = self._build_test_commands(root, package_json, package_manager)
        build_commands = self._build_build_commands(root, package_json, package_manager)

        return ProjectSnapshot(
            project_path=str(root),
            project_name=root.name,
            repository_root=str(repository_root),
            languages=self._detect_languages(root),
            package_manager=package_manager,
            framework=framework,
            entry_files=entry_files,
            test_commands=self._dedupe(test_commands),
            build_commands=self._dedupe(build_commands),
            key_directories=key_directories,
        )

    def _load_package_json(self, root: Path) -> dict:
        package_json_path = root / "package.json"
        if not package_json_path.exists():
            return {}
        try:
            return json.loads(package_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _detect_repository_root(self, root: Path) -> Path:
        for candidate in [root, *root.parents]:
            if (candidate / ".git").exists():
                return candidate
        return root

    def _detect_package_manager(self, root: Path) -> str | None:
        if (root / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (root / "yarn.lock").exists():
            return "yarn"
        if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
            return "bun"
        if (root / "package-lock.json").exists():
            return "npm"
        if (root / "Cargo.toml").exists() or (root / "src-tauri" / "Cargo.toml").exists():
            return "cargo"
        if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
            return "python"
        return None

    def _detect_framework(self, root: Path, package_json: dict) -> str | None:
        dependencies = {
            **(package_json.get("dependencies") or {}),
            **(package_json.get("devDependencies") or {}),
        }
        if (root / "src-tauri" / "Cargo.toml").exists():
            return "tauri"
        if (root / "next.config.js").exists() or (root / "next.config.ts").exists():
            return "nextjs"
        if "vite" in dependencies or (root / "vite.config.ts").exists() or (root / "vite.config.js").exists():
            return "vite"
        if "react" in dependencies:
            return "react"
        if "vue" in dependencies:
            return "vue"
        return None

    def _detect_entry_files(self, root: Path) -> list[str]:
        entries: list[str] = []
        for candidate in COMMON_ENTRY_FILES:
            if (root / candidate).exists():
                entries.append(candidate)
        return entries

    def _detect_languages(self, root: Path) -> list[str]:
        languages: list[str] = []
        if (root / "package.json").exists():
            if any((root / path).exists() for path in ("tsconfig.json", "src/main.ts", "src/main.tsx", "index.ts")):
                languages.append("typescript")
            else:
                languages.append("javascript")
        if (root / "Cargo.toml").exists() or (root / "src-tauri" / "Cargo.toml").exists():
            languages.append("rust")
        if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
            languages.append("python")
        return self._dedupe(languages)

    def _build_test_commands(self, root: Path, package_json: dict, package_manager: str | None) -> list[str]:
        scripts = package_json.get("scripts") if isinstance(package_json, dict) else {}
        commands: list[str] = []
        if isinstance(scripts, dict) and "test" in scripts:
            commands.append(self._package_script_command(package_manager, "test"))
        if (root / "src-tauri" / "Cargo.toml").exists():
            commands.append("cargo test --manifest-path src-tauri/Cargo.toml")
        elif (root / "Cargo.toml").exists():
            commands.append("cargo test")
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").exists():
            commands.append("python -m pytest")
        return commands

    def _build_build_commands(self, root: Path, package_json: dict, package_manager: str | None) -> list[str]:
        scripts = package_json.get("scripts") if isinstance(package_json, dict) else {}
        commands: list[str] = []
        if isinstance(scripts, dict) and "build" in scripts:
            commands.append(self._package_script_command(package_manager, "build"))
        if (root / "src-tauri" / "Cargo.toml").exists():
            commands.append("cargo check --manifest-path src-tauri/Cargo.toml")
        elif (root / "Cargo.toml").exists():
            commands.append("cargo build")
        if (root / "pyproject.toml").exists():
            commands.append("python -m compileall .")
        return commands

    def _package_script_command(self, package_manager: str | None, script_name: str) -> str:
        manager = package_manager or "npm"
        if manager == "yarn":
            return f"yarn {script_name}"
        if manager == "pnpm":
            return f"pnpm {script_name}"
        if manager == "bun":
            return f"bun run {script_name}"
        return f"npm run {script_name}"

    def _dedupe(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped
