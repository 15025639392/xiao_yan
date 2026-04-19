import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_id: str
    provider_name: str
    api_key: str
    base_url: str
    wire_api: str
    default_model: str


def load_local_env() -> None:
    service_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env.local", service_root / ".env.local"]
    seen_paths: set[Path] = set()

    for path in candidates:
        if path in seen_paths or not path.exists():
            continue

        seen_paths.add(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if not item or item.startswith("#") or "=" not in item:
                continue

            key, value = item.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _is_minimax_like_base_url(base_url: str) -> bool:
    normalized = base_url.lower()
    return "minimaxi.com" in normalized or "minimax.chat" in normalized or "minimax" in normalized


def _is_deepseek_like_base_url(base_url: str) -> bool:
    normalized = base_url.lower()
    return "api.deepseek.com" in normalized or "deepseek.com" in normalized


def _normalize_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")


def _infer_wire_api(base_url: str, configured: str | None) -> str:
    if configured and configured.strip():
        return configured.strip()
    if _is_minimax_like_base_url(base_url) or _is_deepseek_like_base_url(base_url):
        return "chat"
    return "responses"

def _normalize_minimax_model_name(model: str) -> str:
    normalized = model.strip()
    if normalized.lower().startswith("codex-"):
        normalized = normalized[6:].strip()
    return normalized


def get_llm_provider_configs() -> list[LLMProviderConfig]:
    load_local_env()

    providers: list[LLMProviderConfig] = []
    seen_provider_ids: set[str] = set()

    def register_provider(
        *,
        provider_id: str,
        provider_name: str,
        api_key: str,
        base_url: str,
        wire_api: str,
        default_model: str,
    ) -> None:
        normalized_provider_id = _normalize_provider_id(provider_id)
        if not normalized_provider_id or normalized_provider_id in seen_provider_ids:
            return
        normalized_api_key = api_key.strip()
        normalized_base_url = base_url.strip().rstrip("/")
        normalized_default_model = default_model.strip()
        if not normalized_api_key or not normalized_base_url:
            return
        seen_provider_ids.add(normalized_provider_id)
        providers.append(
            LLMProviderConfig(
                provider_id=normalized_provider_id,
                provider_name=provider_name.strip() or normalized_provider_id,
                api_key=normalized_api_key,
                base_url=normalized_base_url,
                wire_api=wire_api.strip() or _infer_wire_api(normalized_base_url, None),
                default_model=normalized_default_model or "gpt-5.4",
            )
        )

    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4"
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_api_key:
        register_provider(
            provider_id="openai",
            provider_name="OpenAI",
            api_key=openai_api_key,
            base_url=openai_base_url or "https://api.openai.com/v1",
            wire_api=_infer_wire_api(openai_base_url or "https://api.openai.com/v1", os.getenv("OPENAI_WIRE_API")),
            default_model=openai_model,
        )

    minimax_api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    minimax_base_url = os.getenv("MINIMAX_BASE_URL", "").strip()
    if not minimax_base_url:
        minimax_base_url = openai_base_url if _is_minimax_like_base_url(openai_base_url) else "https://api.minimaxi.com/v1"
    minimax_wire_api_env = os.getenv("MINIMAX_WIRE_API")
    if minimax_wire_api_env is None and _is_minimax_like_base_url(openai_base_url):
        minimax_wire_api_env = os.getenv("OPENAI_WIRE_API")
    minimax_model = os.getenv("MINIMAX_MODEL", "").strip()
    if not minimax_model and _is_minimax_like_base_url(openai_base_url):
        minimax_model = openai_model
    if not minimax_model:
        minimax_model = "MiniMax-M2.7"
    minimax_model = _normalize_minimax_model_name(minimax_model)
    if minimax_api_key:
        register_provider(
            provider_id="minimaxi",
            provider_name="MiniMax",
            api_key=minimax_api_key,
            base_url=minimax_base_url,
            wire_api=_infer_wire_api(minimax_base_url, minimax_wire_api_env),
            default_model=minimax_model,
        )

    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    deepseek_wire_api = os.getenv("DEEPSEEK_WIRE_API")
    if deepseek_wire_api is None:
        deepseek_wire_api = "chat"
    if deepseek_api_key:
        register_provider(
            provider_id="deepseek",
            provider_name="DeepSeek",
            api_key=deepseek_api_key,
            base_url=deepseek_base_url or "https://api.deepseek.com",
            wire_api=_infer_wire_api(deepseek_base_url or "https://api.deepseek.com", deepseek_wire_api),
            default_model=deepseek_model,
        )

    custom_provider_ids = os.getenv("LLM_PROVIDER_IDS", "")
    for raw_provider_id in custom_provider_ids.split(","):
        provider_id = _normalize_provider_id(raw_provider_id)
        if not provider_id:
            continue
        env_token = provider_id.upper().replace("-", "_")
        provider_api_key = os.getenv(f"LLM_PROVIDER_{env_token}_API_KEY", "").strip()
        provider_base_url = os.getenv(f"LLM_PROVIDER_{env_token}_BASE_URL", "").strip()
        if not provider_api_key or not provider_base_url:
            continue

        register_provider(
            provider_id=provider_id,
            provider_name=os.getenv(f"LLM_PROVIDER_{env_token}_NAME", provider_id),
            api_key=provider_api_key,
            base_url=provider_base_url,
            wire_api=_infer_wire_api(
                provider_base_url,
                os.getenv(f"LLM_PROVIDER_{env_token}_WIRE_API"),
            ),
            default_model=os.getenv(f"LLM_PROVIDER_{env_token}_MODEL", "gpt-5.4"),
        )

    return providers


def get_chat_provider() -> str:
    load_local_env()
    provider_catalog = get_llm_provider_configs()
    if not provider_catalog:
        return "openai"

    configured_provider = _normalize_provider_id(os.getenv("CHAT_PROVIDER", ""))
    if configured_provider and any(provider.provider_id == configured_provider for provider in provider_catalog):
        return configured_provider

    if any(provider.provider_id == "openai" for provider in provider_catalog):
        return "openai"
    return provider_catalog[0].provider_id


def get_service_root() -> Path:
    return Path(__file__).resolve().parents[1]

def get_world_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("WORLD_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "world.json"


def get_state_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("STATE_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "state.json"


def get_persona_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("PERSONA_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()

    return get_service_root() / ".data" / "persona.json"

def get_capability_queue_storage_path() -> Path:
    load_local_env()
    configured = os.getenv("CAPABILITY_QUEUE_STORAGE_PATH")
    if configured:
        return Path(configured).expanduser()
    return get_service_root() / ".data" / "capability_queue.json"


def _read_positive_float_env(name: str, default: float, *, minimum: float) -> float:
    load_local_env()
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _read_positive_int_env(name: str, default: int, *, minimum: int) -> int:
    load_local_env()
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)

def get_chat_context_limit() -> int:
    """获取聊天记忆预算基线（会映射为近期对话预算与长期检索命中数）。"""
    load_local_env()
    configured = os.getenv("CHAT_CONTEXT_LIMIT")
    if configured:
        try:
            value = int(configured)
            return max(1, min(20, value))  # 限制在 1-20 之间
        except ValueError:
            pass
    return 6  # 默认聊天记忆预算基线


def get_chat_knowledge_extraction_enabled() -> bool:
    load_local_env()
    return os.getenv("CHAT_KNOWLEDGE_EXTRACTION_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def get_chat_read_timeout_seconds() -> int:
    """获取上游聊天模型读取超时时间（秒），适用于流式读取与工具链路等待。"""
    load_local_env()
    configured = os.getenv("CHAT_READ_TIMEOUT_SECONDS", "").strip()
    if configured:
        try:
            value = int(configured)
            return max(10, min(600, value))
        except ValueError:
            pass
    return 180


def get_chat_model() -> str:
    """获取聊天默认模型。"""
    load_local_env()
    configured = os.getenv("CHAT_MODEL", "").strip()
    if configured:
        current_provider = get_chat_provider()
        if current_provider == "minimaxi":
            return _normalize_minimax_model_name(configured)
        return configured

    current_provider = get_chat_provider()
    for provider in get_llm_provider_configs():
        if provider.provider_id == current_provider:
            return provider.default_model

    legacy_model = os.getenv("OPENAI_MODEL", "").strip()
    return legacy_model or "gpt-5.4"


def get_mempalace_palace_path() -> str:
    load_local_env()
    service_root = Path(__file__).resolve().parents[1]
    default_path = service_root / ".mempalace" / "palace"
    configured = os.getenv("MEMPALACE_PALACE_PATH", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = service_root / candidate
        candidate = candidate.resolve()
        try:
            legacy_home_default = Path.home().resolve() / ".mempalace" / "palace"
            if candidate == legacy_home_default:
                return str(default_path)
        except Exception:  # noqa: BLE001
            pass
        try:
            candidate.relative_to(service_root)
        except ValueError:
            return str(default_path)
        return str(candidate)
    return str(default_path)


def get_mempalace_results_limit() -> int:
    load_local_env()
    configured = os.getenv("MEMPALACE_RESULTS_LIMIT", "").strip()
    if configured:
        try:
            value = int(configured)
            return max(1, min(10, value))
        except ValueError:
            pass
    return 3


def get_mempalace_wing() -> str:
    load_local_env()
    configured = os.getenv("MEMPALACE_WING", "").strip()
    return configured or "wing_xiaoyan"


def get_mempalace_room() -> str:
    load_local_env()
    configured = os.getenv("MEMPALACE_ROOM", "").strip()
    return configured or "chat_exchange"
