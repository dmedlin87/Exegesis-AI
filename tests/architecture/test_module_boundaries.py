"""Architecture enforcement for the hexagonal module plan."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_python_files(package: str) -> Iterable[Path]:
    root = REPO_ROOT / package.replace(".", "/")
    for path in root.rglob("*.py"):
        if path.name == "__init__.py":
            yield path
        else:
            yield path


def _gather_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()

    class _Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.skip_stack: list[bool] = []

        def visit_If(self, node: ast.If) -> None:  # noqa: N802 - AST callback
            is_type_checking = False
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                is_type_checking = True
            elif isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                is_type_checking = True

            self.skip_stack.append(is_type_checking)
            if not is_type_checking:
                for child in node.body:
                    self.visit(child)
            # Always visit orelse as the guard does not apply there.
            for child in node.orelse:
                self.visit(child)
            self.skip_stack.pop()

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - AST callback
            if any(self.skip_stack):
                return
            for alias in node.names:
                if alias.name:
                    imports.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if any(self.skip_stack):
                return
            if node.module:
                imports.add(node.module)

        def generic_visit(self, node: ast.AST) -> None:  # noqa: N802
            # Propagate skip flag through nested scopes.
            if any(self.skip_stack):
                for child in ast.iter_child_nodes(node):
                    self.visit(child)
            else:
                super().generic_visit(node)

    _Collector().visit(tree)
    return imports


def _normalize_module_name(module: str) -> str:
    if module == "theo":
        return "exegesis"
    if module.startswith("theo."):
        return f"exegesis{module[4:]}"
    return module


def test_domain_isolation() -> None:
    forbidden_prefixes = (
        "exegesis.adapters",
        "exegesis.infrastructure",
        "fastapi",
        "sqlalchemy",
        "celery",
    )
    for path in _iter_python_files("exegesis.domain"):
        for module in _gather_imports(path):
            normalized = _normalize_module_name(module)
            if not normalized.startswith("exegesis"):
                continue
            assert not normalized.startswith(forbidden_prefixes), (
                f"Domain module {path} imports forbidden dependency '{module}'"
            )


def test_application_depends_only_on_domain_and_platform() -> None:
    allowed_prefixes = (
        "exegesis.application",
        "exegesis.domain",
        "exegesis.adapters",
        # Deprecated shims are allowed to import from exegesis.services for backwards-compat
        "exegesis.services",
    )
    forbidden_prefixes = ("exegesis.infrastructure",)
    for path in _iter_python_files("exegesis.application"):
        if "facades" in path.parts:
            continue
        if "tests" in path.parts:
            continue
        if path.name == "bootstrap.py" and "services" in path.parts:
            continue
        if "services" in path.parts and "cli" in path.parts:
            continue
        for module in _gather_imports(path):
            normalized = _normalize_module_name(module)
            if not normalized.startswith("exegesis"):
                continue
            assert normalized.startswith(allowed_prefixes), (
                f"Application module {path} imports '{module}', which violates layering"
            )
            assert not normalized.startswith(forbidden_prefixes), (
                f"Application module {path} must not depend on {module}"
            )


def test_application_does_not_import_service_database() -> None:
    forbidden_prefix = "exegesis.infrastructure.api.app.db"
    for path in _iter_python_files("exegesis.application"):
        for module in _gather_imports(path):
            normalized = _normalize_module_name(module)
            if not normalized.startswith("exegesis"):
                continue
            assert not normalized.startswith(forbidden_prefix), (
                f"Application module {path} imports forbidden database dependency '{module}'"
            )


def test_application_does_not_import_service_runtimes_or_fastapi() -> None:
    forbidden_service_prefix = "exegesis.infrastructure.api.app"
    forbidden_adapters = (
        "exegesis.infrastructure.api.app.adapters.telemetry",
        "exegesis.infrastructure.api.app.adapters.resilience",
        "exegesis.infrastructure.api.app.adapters.security",
    )
    for path in _iter_python_files("exegesis.application"):
        if "tests" in path.parts:
            continue
        if path.name == "bootstrap.py" and "services" in path.parts:
            continue
        if "services" in path.parts and "cli" in path.parts:
            continue
        for module in _gather_imports(path):
            normalized = _normalize_module_name(module)
            for adapter in forbidden_adapters:
                if normalized == adapter or normalized.startswith(f"{adapter}."):
                    pytest.fail(
                        f"Application module {path} imports forbidden adapter '{module}'"
                    )
            if normalized.startswith(forbidden_service_prefix):
                pytest.fail(
                    f"Application module {path} must not import service-layer runtime module '{module}'"
                )
            if module == "fastapi" or module.startswith("fastapi."):
                pytest.fail(
                    f"Application module {path} imports FastAPI dependency '{module}'"
                )


def test_adapters_do_not_cross_import() -> None:
    forbidden_edges = {
        "exegesis.adapters.interfaces": ("exegesis.adapters.persistence", "exegesis.adapters.search", "exegesis.adapters.ai"),
    }
    for path in _iter_python_files("exegesis.adapters"):
        imports = _gather_imports(path)
        for source_prefix, disallowed_targets in forbidden_edges.items():
            if not path.as_posix().startswith((REPO_ROOT / source_prefix.replace(".", "/")).as_posix()):
                continue
            for module in imports:
                for target in disallowed_targets:
                    assert not module.startswith(target), (
                        f"Interface adapter {path} must not import '{module}'"
                    )


def test_routes_depend_on_application_facades() -> None:
    required_prefix = "exegesis.application.facades"
    for path in _iter_python_files("exegesis.infrastructure.api.app.routes"):
        imports = _gather_imports(path)
        assert any(
            _normalize_module_name(module).startswith(required_prefix)
            for module in imports
        ), f"Route module {path} must import {required_prefix} helpers"


def test_workers_use_application_bootstrap() -> None:
    workers_path = REPO_ROOT / "exegesis/infrastructure/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        imports = _gather_imports(path)
        normalized_imports = {_normalize_module_name(module) for module in imports}
        assert "exegesis.application.services.bootstrap" in normalized_imports, (
            f"Worker module {path} must resolve adapters via exegesis.application.services.bootstrap"
        )


def test_cli_commands_use_application_bootstrap() -> None:
    cli_root = REPO_ROOT / "exegesis/application/services/cli"
    for path in cli_root.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        imports = _gather_imports(path)
        normalized_imports = {_normalize_module_name(module) for module in imports}
        assert "exegesis.application.services.bootstrap" in normalized_imports, (
            f"CLI module {path} must resolve adapters via exegesis.application.services.bootstrap"
        )


def test_platform_package_removed() -> None:
    legacy_paths = (
        REPO_ROOT / "theo/platform",
        REPO_ROOT / "exegesis/platform",
    )
    for platform_path in legacy_paths:
        assert not platform_path.exists(), "Legacy 'exegesis.platform' package should be removed."

    violating_modules: list[tuple[Path, str]] = []
    for package in ("exegesis", "tests", "theo"):
        for path in _iter_python_files(package):
            for module in _gather_imports(path):
                normalized = _normalize_module_name(module)
                if normalized == "exegesis.platform" or normalized.startswith("exegesis.platform."):
                    violating_modules.append((path, module))

    assert not violating_modules, (
        "Modules import removed package 'exegesis.platform': "
        + ", ".join(f"{path}:{module}" for path, module in violating_modules)
    )


def test_async_workers_do_not_depend_on_domain_layer() -> None:
    workers_path = REPO_ROOT / "exegesis/infrastructure/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for module in _gather_imports(path):
            normalized = _normalize_module_name(module)
            assert not normalized.startswith("exegesis.domain"), (
                f"Async worker module {path} must not import domain layer module '{module}'"
            )


def test_api_adapters_live_under_infra_namespace() -> None:
    legacy_services_path = REPO_ROOT / "exegesis/infrastructure/api/app/services"
    assert not legacy_services_path.exists(), (
        "Legacy API services package reintroduced; adapters must live in 'infra'."
    )

    infra_path = REPO_ROOT / "exegesis/infrastructure/api/app/infra"
    assert infra_path.exists(), "API infrastructure adapters must live under 'infra'."
    adapter_modules = list(infra_path.rglob("*.py"))
    assert adapter_modules, "Infrastructure namespace should contain adapter modules."
