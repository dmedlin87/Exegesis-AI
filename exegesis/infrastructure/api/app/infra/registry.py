"""Router registration utilities for Theo's API infrastructure adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from fastapi import APIRouter


@dataclass(frozen=True)
class RouterRegistration:
    """Metadata describing a router to mount on the API application."""

    router: APIRouter
    prefix: str | None = None
    tags: Sequence[str] = ()
    requires_security: bool = True


_REGISTRY: List[RouterRegistration] = []


def register_router(registration: RouterRegistration) -> None:
    """Register *registration* with the global router registry."""

    _REGISTRY.append(registration)


def iter_router_registrations() -> Tuple[RouterRegistration, ...]:
    """Return a snapshot of all registered routers."""

    return tuple(_REGISTRY)


def clear_router_registrations() -> None:
    """Remove all routers from the registry."""

    _REGISTRY.clear()


def replace_router_registrations(
    registrations: Iterable[RouterRegistration],
) -> None:
    """Replace the registry contents with *registrations*."""

    clear_router_registrations()
    _REGISTRY.extend(registrations)
