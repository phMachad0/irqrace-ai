"""Per-candidate result cache, keyed by (fingerprint, prompt config, model).

``wiki/Roadmap.md`` W2. The key is exactly those three things and nothing else,
which is why C2's ``fingerprint`` was defined to cover only subject, class,
variable and access locations -- never run id, timing or solver output
(``contracts/README.md``, the sixth decision). Re-running the analyzer produces
new candidate records with new run metadata and the same fingerprints, so the
cache survives it.

The cache earns its keep on the ablation. Five rows over the same fixtures share
no prompt configuration, so the rows themselves never hit -- but *reruns* of a
row do, and consistency measurement runs each candidate n times deliberately.
Hence :meth:`Cache.get` takes an explicit ``sample`` index: repeat runs are
distinct entries rather than cache hits, because collapsing them would silently
turn a consistency measurement into a constant.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path(__file__).resolve().parents[3] / ".llm-cache"


class Cache:
    """A directory of JSON files, one per (candidate, config, model, sample).

    Deliberately not a database. The entries are readable, greppable, and
    individually deletable when one looks wrong, which during prompt
    development is the operation that actually happens.
    """

    def __init__(self, directory: Path | str | None = None, *, enabled: bool = True):
        self.dir = Path(directory) if directory else DEFAULT_DIR
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    def key(
        self,
        fingerprint: str,
        config_hash: str,
        model: str,
        sample: int = 0,
        schema_hash: str = "",
    ) -> str:
        """The cache entry's filename stem.

        ``schema_hash`` covers the **response schema**, and it closes a hole the
        first live run exposed by analogy: ``PromptConfig.hash`` covers the
        prompt assets, so editing a prompt invalidates the cache, but nothing
        covered the verdict schema. Adding a field to the answer changes the
        experiment exactly as much as editing the prompt does, and without this
        the cache would serve answers shaped by the previous schema.

        The model half is a backend spec, and specs legitimately contain
        characters a filename cannot: ``openai:openai/gpt-oss-120b`` has both a
        colon and a slash, and on Windows the slash silently became a
        directory and the colon an invalid argument. So the spec is slugged for
        readability **and** suffixed with a hash of the original, because two
        distinct specs can slug to the same string and a cache collision would
        serve one model's verdict as another's.
        """
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")[:48]
        digest = hashlib.sha256(model.encode("utf-8")).hexdigest()[:8]
        suffix = f".{schema_hash[:8]}" if schema_hash else ""
        return f"{fingerprint[:16]}.{config_hash}.{slug}-{digest}{suffix}.{sample}"

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(
        self,
        fingerprint: str,
        config_hash: str,
        model: str,
        sample: int = 0,
        schema_hash: str = "",
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self._path(
            self.key(fingerprint, config_hash, model, sample, schema_hash)
        )
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    def put(
        self,
        fingerprint: str,
        config_hash: str,
        model: str,
        value: dict[str, Any],
        sample: int = 0,
        schema_hash: str = "",
    ) -> None:
        if not self.enabled:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(
            self.key(fingerprint, config_hash, model, sample, schema_hash)
        )
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def report(self) -> str:
        total = self.hits + self.misses
        rate = self.hits / total if total else 0.0
        return f"cache: {self.hits} hits / {total} lookups ({rate:.0%}) in {self.dir}"
