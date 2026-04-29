from __future__ import annotations

from app.creative_writing.models import NovelProject, utc_now


def update_project_habit_state(
    project: NovelProject,
    *,
    attachment_reason: str | None = None,
    last_pause: str | None = None,
    next_intention: str | None = None,
    cadence_note: str | None = None,
) -> NovelProject:
    updates: dict[str, str] = {}
    if attachment_reason is not None:
        updates["attachment_reason"] = attachment_reason.strip()
    if last_pause is not None:
        updates["last_pause"] = last_pause.strip()
    if next_intention is not None:
        updates["next_intention"] = next_intention.strip()
    if cadence_note is not None:
        updates["cadence_note"] = cadence_note.strip()
    habit_state = project.habit_state.model_copy(update={**updates, "updated_at": utc_now()})
    return project.model_copy(update={"habit_state": habit_state, "updated_at": utc_now()})
