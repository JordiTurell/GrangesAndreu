"""Comprueba e instala las dependencias declaradas en requirements.txt al arrancar."""

from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"

# Nombre de distribución -> se ignoran extras y especificadores de versión.
_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _parse_requirements(path: Path) -> list[tuple[str, str]]:
    """Devuelve pares (nombre_distribución, línea_original)."""
    requirements: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQUIREMENT_NAME.match(line)
        if match:
            requirements.append((match.group(0), line))
    return requirements


def _missing_requirements() -> list[str]:
    missing: list[str] = []
    for name, line in _parse_requirements(REQUIREMENTS_FILE):
        try:
            metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(line)
    return missing


def ensure_dependencies(auto_install: bool = True) -> None:
    """Instala los paquetes de requirements.txt que falten en el entorno actual."""
    if not REQUIREMENTS_FILE.is_file():
        return

    missing = _missing_requirements()
    if not missing:
        return

    if not auto_install:
        raise RuntimeError(
            "Faltan dependencias: " + ", ".join(missing) + ". Ejecuta: pip install -r requirements.txt"
        )

    print(f"[bootstrap] Instalando dependencias faltantes: {', '.join(missing)}", flush=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *missing]
    )

    still_missing = _missing_requirements()
    if still_missing:
        raise RuntimeError("No se pudieron instalar: " + ", ".join(still_missing))

    # Permite que los módulos recién instalados sean visibles en este proceso.
    import importlib
    import site

    site.main()
    importlib.invalidate_caches()
    print("[bootstrap] Dependencias listas.", flush=True)


if __name__ == "__main__":
    ensure_dependencies()
