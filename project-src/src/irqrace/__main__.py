"""Entry point for ``python -m irqrace``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
