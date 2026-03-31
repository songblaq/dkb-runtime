"""Resolve package version: prefer repo `pyproject.toml` when present, else distribution metadata."""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path


def package_version() -> str:
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    try:
        return pkg_version("dkb-runtime")
    except PackageNotFoundError:
        return "0.2.0"
