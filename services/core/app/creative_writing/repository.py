from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from app.creative_writing.models import (
    CreativeWritingLibrary,
    NovelChapterSummary,
    NovelFragment,
    NovelProject,
    NovelWritingSession,
    NovelWritingContext,
)
from app.utils.file_utils import read_json_file, read_text_file, write_json_file, write_text_file


class CreativeWritingRepository(Protocol):
    def list_projects(self) -> list[NovelProject]:
        ...

    def get_project(self, project_id: str) -> NovelProject | None:
        ...

    def save_project(self, project: NovelProject) -> NovelProject:
        ...

    def next_fragment_sequence(self, project: NovelProject, chapter_index: int) -> int:
        ...

    def save_fragment(self, project: NovelProject, fragment: NovelFragment) -> NovelFragment:
        ...

    def save_chapter_summary(self, project: NovelProject, summary: NovelChapterSummary) -> NovelChapterSummary:
        ...

    def list_chapter_summaries(self, project: NovelProject) -> list[NovelChapterSummary]:
        ...

    def save_session(self, project: NovelProject, session: NovelWritingSession) -> NovelWritingSession:
        ...

    def get_session(self, session_id: str) -> NovelWritingSession | None:
        ...

    def list_sessions(self, project: NovelProject | None = None) -> list[NovelWritingSession]:
        ...

    def list_fragments(self, project: NovelProject, chapter_index: int | None = None) -> list[NovelFragment]:
        ...

    def build_writing_context(
        self,
        project: NovelProject,
        *,
        max_fragments: int = 3,
        max_excerpt_chars: int = 1600,
    ) -> NovelWritingContext:
        ...

    def fragment_relative_path(self, project: NovelProject, chapter_index: int, sequence: int) -> str:
        ...

    def chapter_summary_relative_path(self, project: NovelProject, chapter_index: int) -> str:
        ...


class FileCreativeWritingRepository:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.index_path = storage_dir / "projects.json"

    def list_projects(self) -> list[NovelProject]:
        return self._read_library().projects

    def get_project(self, project_id: str) -> NovelProject | None:
        return next((project for project in self.list_projects() if project.id == project_id), None)

    def save_project(self, project: NovelProject) -> NovelProject:
        library = self._read_library()
        projects = [item for item in library.projects if item.id != project.id]
        projects.append(project)
        projects.sort(key=lambda item: item.updated_at, reverse=True)
        write_json_file(
            self.index_path,
            CreativeWritingLibrary(projects=projects).model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
        project_dir = self.project_dir(project)
        write_json_file(
            project_dir / "project.json",
            project.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
        self._write_project_readme(project)
        return project

    def next_fragment_sequence(self, project: NovelProject, chapter_index: int) -> int:
        fragments_dir = self._chapter_dir(project, chapter_index) / "fragments"
        if not fragments_dir.exists():
            return 1
        return len(list(fragments_dir.glob("fragment-*.md"))) + 1

    def save_fragment(self, project: NovelProject, fragment: NovelFragment) -> NovelFragment:
        chapter_dir = self._chapter_dir(project, fragment.chapter_index)
        fragments_dir = chapter_dir / "fragments"
        content_path = self.storage_dir / fragment.file_path
        metadata_path = fragments_dir / f"fragment-{fragment.sequence:03d}.json"
        write_text_file(content_path, fragment.content, create_parent=True)
        write_json_file(
            metadata_path,
            fragment.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
        if fragment.summary:
            write_text_file(chapter_dir / "latest-summary.md", fragment.summary, create_parent=True)
        return fragment

    def save_chapter_summary(self, project: NovelProject, summary: NovelChapterSummary) -> NovelChapterSummary:
        chapter_dir = self._chapter_dir(project, summary.chapter_index)
        summary_path = self.storage_dir / summary.file_path
        metadata_path = chapter_dir / "chapter-summary.json"
        title = f"# {summary.title}\n\n" if summary.title else ""
        write_text_file(summary_path, f"{title}{summary.summary}", create_parent=True)
        write_json_file(
            metadata_path,
            summary.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
        return summary

    def list_chapter_summaries(self, project: NovelProject) -> list[NovelChapterSummary]:
        chapters_root = self.project_dir(project) / "chapters"
        if not chapters_root.exists():
            return []
        metadata_paths = sorted(chapters_root.glob("chapter-*/chapter-summary.json"))
        summaries = [NovelChapterSummary.model_validate(read_json_file(path)) for path in metadata_paths]
        return sorted(summaries, key=lambda item: item.chapter_index)

    def save_session(self, project: NovelProject, session: NovelWritingSession) -> NovelWritingSession:
        path = self._session_path(project, session.id)
        write_json_file(
            path,
            session.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            create_parent=True,
        )
        return session

    def get_session(self, session_id: str) -> NovelWritingSession | None:
        path = next(iter(self.storage_dir.glob(f"*/sessions/session-{session_id}.json")), None)
        if path is None:
            return None
        return NovelWritingSession.model_validate(read_json_file(path))

    def list_sessions(self, project: NovelProject | None = None) -> list[NovelWritingSession]:
        if project is not None:
            metadata_paths = sorted((self.project_dir(project) / "sessions").glob("session-*.json"))
        else:
            metadata_paths = sorted(self.storage_dir.glob("*/sessions/session-*.json"))
        sessions = [NovelWritingSession.model_validate(read_json_file(path)) for path in metadata_paths]
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def list_fragments(self, project: NovelProject, chapter_index: int | None = None) -> list[NovelFragment]:
        chapters_root = self.project_dir(project) / "chapters"
        if not chapters_root.exists():
            return []
        metadata_paths = sorted(chapters_root.glob("chapter-*/fragments/fragment-*.json"))
        fragments = [NovelFragment.model_validate(read_json_file(path)) for path in metadata_paths]
        if chapter_index is not None:
            fragments = [fragment for fragment in fragments if fragment.chapter_index == chapter_index]
        return sorted(fragments, key=lambda item: (item.chapter_index, item.sequence))

    def build_writing_context(
        self,
        project: NovelProject,
        *,
        max_fragments: int = 3,
        max_excerpt_chars: int = 1600,
    ) -> NovelWritingContext:
        fragments = self.list_fragments(project, chapter_index=project.current_chapter_index)
        recent_fragments = fragments[-max_fragments:]
        summaries = [fragment.summary for fragment in recent_fragments if fragment.summary]
        recent_text = "\n\n".join(self._read_fragment_content(fragment) for fragment in recent_fragments)
        previous_chapters = [
            self._format_chapter_summary(summary)
            for summary in self.list_chapter_summaries(project)
            if summary.chapter_index < project.current_chapter_index
        ][-3:]
        return NovelWritingContext(
            project_id=project.id,
            chapter_index=project.current_chapter_index,
            previous_chapter_summaries=previous_chapters,
            recent_summaries=summaries,
            recent_excerpt=recent_text[-max_excerpt_chars:],
        )

    def project_dir(self, project: NovelProject) -> Path:
        return self.storage_dir / project.folder_name

    def fragment_relative_path(self, project: NovelProject, chapter_index: int, sequence: int) -> str:
        return str(
            Path(project.folder_name)
            / "chapters"
            / f"chapter-{chapter_index:03d}"
            / "fragments"
            / f"fragment-{sequence:03d}.md"
        )

    def chapter_summary_relative_path(self, project: NovelProject, chapter_index: int) -> str:
        return str(Path(project.folder_name) / "chapters" / f"chapter-{chapter_index:03d}" / "chapter-summary.md")

    def _read_library(self) -> CreativeWritingLibrary:
        if not self.index_path.exists():
            return CreativeWritingLibrary()
        return CreativeWritingLibrary.model_validate(read_json_file(self.index_path))

    def _chapter_dir(self, project: NovelProject, chapter_index: int) -> Path:
        return self.project_dir(project) / "chapters" / f"chapter-{chapter_index:03d}"

    def _session_path(self, project: NovelProject, session_id: str) -> Path:
        return self.project_dir(project) / "sessions" / f"session-{session_id}.json"

    def _write_project_readme(self, project: NovelProject) -> None:
        outline = "\n".join(f"- {item}" for item in project.outline) or "- 暂未形成稳定大纲"
        characters = "\n".join(f"- {item.name}：{item.role}" for item in project.characters) or "- 暂未固定角色"
        content = (
            f"# {project.title}\n\n"
            f"## 创作动机\n{project.premise}\n\n"
            f"## 语气\n{project.tone}\n\n"
            f"## 角色\n{characters}\n\n"
            f"## 大纲\n{outline}\n"
        )
        write_text_file(self.project_dir(project) / "README.md", content, create_parent=True)

    def _read_fragment_content(self, fragment: NovelFragment) -> str:
        path = self.storage_dir / fragment.file_path
        if not path.exists():
            return ""
        return read_text_file(path)

    def _format_chapter_summary(self, summary: NovelChapterSummary) -> str:
        title = f"{summary.title}：" if summary.title else ""
        return f"第 {summary.chapter_index} 章：{title}{summary.summary}"


def safe_folder_name(project_id: str, title: str) -> str:
    compact_title = re.sub(r"[\\/:*?\"<>|\s]+", "-", title.strip()).strip("-")
    readable_title = compact_title[:48] or "untitled"
    return f"{project_id}-{readable_title}"
