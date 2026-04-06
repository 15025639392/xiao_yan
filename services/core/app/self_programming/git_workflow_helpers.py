from __future__ import annotations


def parse_porcelain_status(status_output: str) -> tuple[list[str], list[str], list[str]]:
    staged: list[str] = []
    modified: list[str] = []
    untracked: list[str] = []

    for line in status_output.splitlines():
        line = line.strip()
        if not line:
            continue
        code = line[:2]
        filename = line[3:].strip()
        if code[0] in ("A", "M", "D", "R", "C"):
            staged.append(filename)
        if code[1] in ("M", "D") or (code[0] == " " and code[1] == "M"):
            modified.append(filename)
        if code == "??":
            untracked.append(filename)

    return staged, modified, untracked


def build_branch_name(prefix: str, job_id: str, target_area: str = "") -> str:
    area_slug = target_area.lower().replace(" ", "-").replace("_", "-")[:30]
    if area_slug:
        return f"{prefix}{area_slug}-{job_id[:12]}"
    return f"{prefix}{job_id[:12]}"


def pick_branch_from_list(branches_output: str) -> str | None:
    cleaned = branches_output.strip()
    if not cleaned:
        return None
    return cleaned.split("\n")[0].strip().lstrip("* ")


def pick_ref_from_log(log_output: str) -> str | None:
    cleaned = log_output.strip()
    if not cleaned:
        return None
    first_line = cleaned.splitlines()[0].strip()
    if not first_line:
        return None
    return first_line.split()[0]


def build_commit_message(
    commit_tag: str,
    job_id: str,
    target_area: str,
    summary: str,
    files: list[str],
    candidate_label: str = "",
) -> str:
    body_parts = [f"Job: {job_id}"]
    if candidate_label:
        body_parts.append(f"Candidate: {candidate_label}")

    body_parts.append("Files:")
    for file_path in files:
        body_parts.append(f"  - {file_path}")

    body = "\n".join(body_parts)
    return f"{commit_tag} {target_area}: {summary}\n\n{body}"


__all__ = [
    "parse_porcelain_status",
    "build_branch_name",
    "pick_branch_from_list",
    "pick_ref_from_log",
    "build_commit_message",
]
