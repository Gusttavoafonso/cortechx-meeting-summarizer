from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from app.integrations.base import IntegrationProvider, ProviderNotFoundError

T = TypeVar("T", bound=type[IntegrationProvider])


class ProviderRegistry:
    """Registro centralizado de provedores de integração externa."""

    def __init__(self) -> None:
        self._providers: dict[str, type[IntegrationProvider]] = {}

    def register(self, name: str | None = None) -> Callable[[T], T]:
        """Decorator ou método para registrar uma classe de provedor."""

        def decorator(provider_cls: T) -> T:
            provider_name = (name or getattr(provider_cls, "name", None) or provider_cls.__name__).lower()
            self._providers[provider_name] = provider_cls
            return provider_cls

        return decorator

    def get(self, name: str) -> type[IntegrationProvider]:
        """Obtém a classe do provedor pelo nome registrado."""
        normalized = name.strip().lower()
        provider_cls = self._providers.get(normalized)
        if provider_cls is None:
            raise ProviderNotFoundError(name)
        return provider_cls

    def create(self, name: str, **kwargs: object) -> IntegrationProvider:
        """Instancia um provedor pelo nome registrado."""
        provider_cls = self.get(name)
        return provider_cls(**kwargs)

    def list_available(self) -> list[str]:
        """Retorna os nomes de todos os provedores registrados."""
        return sorted(list(self._providers.keys()))

    def clear(self) -> None:
        """Limpa todos os provedores registrados (útil em testes)."""
        self._providers.clear()


default_registry = ProviderRegistry()
register_provider = default_registry.register
get_provider = default_registry.get
list_providers = default_registry.list_available
