"""Blacklist · 用户 reject 过的 claim 类型不再生成."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class Blacklist:
    """An on-disk blacklist of claim signatures the user rejected.

    Signature is (classification, key_phrase) — coarse enough to block all
    similar claims, fine enough to not over-block.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._entries = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self._entries = []
        else:
            self._entries = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries, ensure_ascii=False, indent=2))

    def add(self, classification: str, key_phrase: str, reason: str = "") -> None:
        entry = {
            "classification": classification,
            "key_phrase": key_phrase.lower().strip(),
            "reason": reason,
        }
        if entry not in self._entries:
            self._entries.append(entry)
            self._save()

    def is_blocked(self, classification: str, claim_text: str) -> Optional[str]:
        """Return the matching key_phrase if blocked, else None."""
        claim_lc = claim_text.lower()
        for e in self._entries:
            if e["classification"] != classification:
                continue
            if e["key_phrase"] in claim_lc:
                return e["key_phrase"]
        return None

    def all(self) -> list[dict]:
        return list(self._entries)
