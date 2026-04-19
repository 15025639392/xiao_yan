# AI Working Rules For `xiao_yan`

This file defines the default execution rules for any AI agent modifying this repository.

If a user request conflicts with these rules, pause and ask for confirmation only when the conflict is material. Otherwise, follow these rules by default.

## Source Of Truth

- Read [docs/AI 接手开发规范.md](./docs/AI%20%E6%8E%A5%E6%89%8B%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83.md) before making substantial code changes.
- Read [docs/architecture-principles.md](./docs/architecture-principles.md) before changing core architecture, runtime flow, memory, autonomy, safety, or orchestration behavior.
- Preserve the product direction: `xiao_yan` is a digital being first, not a generic automation platform.

## Non-Negotiable Defaults

- Prefer explicit code over hidden magic.
- Prefer small, local, reversible changes over large rewrites.
- Prefer fewer dependencies and shorter call chains.
- Prefer the smallest clear responsibility per module, function, and component.
- Prefer clear module boundaries over clever abstractions.
- Do not treat file growth as a normal implementation strategy.

## File Size Rules

- Backend Python business files should target 300 lines or fewer.
- Backend Python business files over 500 lines should be treated as split candidates.
- Backend Python business files over 800 lines should not receive more logic until a split is considered.
- Frontend pages and container components should target 250 lines or fewer.
- Frontend pages and container components over 400 lines should be treated as split candidates.
- Frontend pages and container components over 600 lines should not receive more logic until a split is considered.
- Functions should usually stay within 40 lines.
- Functions over 60 lines should be reviewed for mixed responsibilities.
- Functions over 100 lines should be split unless they represent a single linear workflow that cannot be simplified further.

## Splitting Rules

- If a module, service, function, or component starts handling more than one clear responsibility, split it.
- Split by responsibility first: protocol, orchestration, storage, transformation, rendering.
- Split by domain second: chat, memory, goals, orchestrator, persona, tools.
- Only move logic into `utils` when it is genuinely generic and not domain behavior in disguise.
- If touching an oversized file, prefer extracting one small layer instead of adding more logic into it.

## Duplication Rules

- When similar logic appears a second time, evaluate extraction.
- Do not introduce abstractions for hypothetical future reuse.
- Extract stable repeated steps, not vague meta-frameworks.
- Do not copy old logic into a new branch and patch it locally unless there is a strong reason.

## Performance Rules

- Avoid repeated HTTP calls, file reads, model calls, or storage reads inside loops.
- Avoid repeated full scans, sorts, serialization, or deserialization of the same data.
- Avoid heavy computation during frontend render.
- Avoid large shared state updates that trigger unrelated rerenders.
- Avoid unbounded polling, logging, history concatenation, or in-memory accumulation on hot paths.
- Reuse results when possible, prefer incremental updates, and limit payload sizes by default.

## Dependency And Architecture Rules

- For `services/core`, keep core runtime dependencies centered on `fastapi`, `pydantic`, and `httpx`.
- Do not promote optional capabilities like `mempalace`, `chromadb`, or `pypdf` into hard runtime requirements.
- Do not add ORM, queue, DI container, or heavy config frameworks without a strong repo-specific justification.
- Keep optional capabilities isolated at the edges with clear downgrade behavior.

## Required Workflow

Before editing:

- Identify the entry point.
- Identify the related models and dependency chain.
- Check whether tests already cover the path.
- Check whether the target file is already oversized.

During editing:

- Stay on the smallest behavior chain that solves the request.
- Check whether the target unit already violates the minimum-responsibility principle before adding more logic.
- Reuse existing patterns unless there is a clear benefit in changing them.
- Do not mix unrelated cleanup into the same change.

Before finishing:

- Run `python3 tools/check_file_budgets.py` when code structure changed or when touching large files.
- For backend verification, prefer the project-managed environment via `uv` instead of assuming system Python dependencies are available.
- Run backend tests with `uv run --project services/core pytest ...` and prefer relevant test subsets before broadening scope.
- Do not claim `fastapi`, `pytest`, or other backend test dependencies are missing until `uv run --project services/core ...` has been tried.
- Ask whether the change increased file size pressure, duplication, or hot-path cost.
- Update docs when dependencies, startup, config, module responsibilities, or downgrade behavior changed.
- State which tests were run; if not run, state why and what risk remains.

## Low-Token Shortcut

For this early-stage project, default to the narrowest useful task shape.

- Prefer one behavior chain per request.
- Prefer an explicit scope in files/modules/routes.
- Prefer reading the target file and related tests before broader docs.
- Prefer relevant test subsets over full-repo validation.
- Prefer 1-2 relevant skills instead of chaining many skills by default.

Recommended request shape:

```text
Goal: <one-sentence goal>
Scope: <files/modules/routes allowed>
Do not: <clear exclusions>
Output: <analyze only / patch code / tests only / plan only>
Verify: <which tests to run or not run>
```

Quick references:

- [docs/daily-shortcuts.md](./docs/daily-shortcuts.md)
- [docs/low-token-collaboration.md](./docs/low-token-collaboration.md)
- [docs/low-token-request-examples.md](./docs/low-token-request-examples.md)

## Review Output Expectations

When reporting a completed code change, include:

- Whether any large file was kept stable, reduced, or made worse.
- Whether duplication was reduced, kept flat, or introduced.
- Whether any performance-sensitive path was changed.
- What tests or checks were run.

## Hard Stops

- Do not silently introduce a new architecture layer.
- Do not silently widen autonomy or execution permissions.
- Do not silently convert optional dependencies into required ones.
- Do not silently turn the product into a tool platform instead of a digital being.
- Do not keep growing a mixed-responsibility file when the change should live in a smaller unit.
- Do not continue inflating already oversized files just because that is the fastest path.
