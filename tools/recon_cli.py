"""Execute source reconnaissance with validated GitHub Actions input.

User input is only read as data from RECON_ONLY and never interpolated
into a shell command. Existing tools.recon behavior is preserved.
"""
from __future__ import annotations

import os
import re
import sys

_SOURCE_IDS = re.compile(r"[a-z0-9][a-z0-9_-]*(?:,[a-z0-9][a-z0-9_-]*)*")


def parse_source_ids(raw: str | None) -> list[str]:
    value = (raw or "").strip()
    if not value:
        return []
    if len(value) > 500 or not _SOURCE_IDS.fullmatch(value):
        raise ValueError("Ids de fuentes inválidos: usa letras minúsculas, dígitos, guiones, guion bajo y comas, sin espacios")
    if len(set(value.split(","))) != len(value.split(",")):
        raise ValueError("Ids de fuentes duplicados")
    return ["--only", value]


def main() -> None:
    try:
        source_ids = parse_source_ids(os.environ.get("RECON_ONLY"))
    except ValueError as exc:
        print(f"Error en RECON_ONLY: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    sys.argv = ["tools.recon", "--write-sources", *source_ids]
    from tools.recon import main as run_recon
    run_recon()


if __name__ == "__main__":
    main()
