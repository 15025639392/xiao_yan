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
- Reuse existing patterns unless there is a clear benefit in changing them.
- Do not mix unrelated cleanup into the same change.

Before finishing:

- Run `python3 tools/check_file_budgets.py` when code structure changed or when touching large files.
- Ask whether the change increased file size pressure, duplication, or hot-path cost.
- Update docs when dependencies, startup, config, module responsibilities, or downgrade behavior changed.
- State which tests were run; if not run, state why and what risk remains.

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
- Do not continue inflating already oversized files just because that is the fastest path.
