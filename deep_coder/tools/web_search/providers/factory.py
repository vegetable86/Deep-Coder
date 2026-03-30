from deep_coder.tools.web_search.providers.base import SearchProvider
from deep_coder.tools.web_search.providers.brave import BraveSearchProvider
from deep_coder.tools.web_search.providers.google import GoogleSearchProvider
from deep_coder.tools.web_search.providers.serper import SerperProvider


def build_provider(config) -> SearchProvider | None:
    settings = getattr(config, "web_search_settings", None)
    if not settings:
        return None

    provider_name = settings.get("provider")
    if not provider_name:
        raise ValueError("web_search provider is required")

    if provider_name not in {"google", "serper", "brave"}:
        raise ValueError(f"unknown web_search provider: {provider_name}")

    provider_settings = settings.get(provider_name)
    if not isinstance(provider_settings, dict):
        raise ValueError(
            f"web_search provider settings missing for '{provider_name}'"
        )

    if provider_name == "google":
        return GoogleSearchProvider(
            api_key=_require_field(provider_settings, provider_name, "api_key"),
            cx=_require_field(provider_settings, provider_name, "cx"),
        )
    if provider_name == "serper":
        return SerperProvider(
            api_key=_require_field(provider_settings, provider_name, "api_key"),
        )
    if provider_name == "brave":
        return BraveSearchProvider(
            api_key=_require_field(provider_settings, provider_name, "api_key"),
        )


def _require_field(settings: dict, provider_name: str, field_name: str) -> str:
    value = settings.get(field_name)
    if not value:
        raise ValueError(
            f"web_search provider '{provider_name}' requires '{field_name}'"
        )
    return str(value)
