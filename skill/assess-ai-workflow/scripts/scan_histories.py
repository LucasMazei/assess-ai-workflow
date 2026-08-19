#!/usr/bin/env python3
"""Read-only, best-effort scanner for local AI coding-assistant histories.

The scanner intentionally emits aggregates and short, redacted user-message
samples instead of copying conversations.  It uses only Python's standard
library and opens Cursor's SQLite databases in immutable/read-only mode.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator


SOURCE_NAMES = ("codex", "claude", "cursor", "opencode")
SCHEMA_VERSION = "1.0"
HOME = Path.home()
ASSESSMENT_SALT = os.urandom(32)

TOOL_CATEGORIES = frozenset({
    "browser", "research", "planning", "delegation", "filesystem_read",
    "filesystem_write", "shell", "version_control", "communication",
    "database", "other",
})
MODEL_FAMILIES = frozenset({
    "openai-gpt", "openai-codex", "anthropic-claude", "google-gemini",
    "luna", "meta-llama", "mistral", "deepseek", "other-model",
})
INTENT_LABELS = {
    "research": "Pesquisar ou reunir contexto",
    "planning": "Planejar trabalho ou definir abordagem",
    "implementation": "Implementar ou alterar um artefato",
    "validation": "Testar ou validar um resultado",
    "debugging": "Diagnosticar ou corrigir um problema",
    "review": "Revisar ou avaliar um artefato",
    "handoff": "Resumir, documentar ou transferir contexto",
    "unknown": "Intencao nao inferivel com seguranca",
}
SIGNAL_NAMES = (
    "research", "planning", "implementation", "validation", "browser",
    "handoff", "blocked", "error",
)
CASE_LIMITATIONS = frozenset({
    "Intent is a deterministic coarse paraphrase, not a quoted prompt.",
    "Tool arguments, outputs, code, paths, and names are intentionally omitted.",
    "Signals are heuristic and may be incomplete.",
    "No safe user intent was retained for this session.",
    "Model identifiers are reduced to broad families.",
})

SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", re.I), "[REDACTED_PRIVATE_KEY]"),
    # Vendor-prefixed tokens. Cover BOTH hyphen (OpenAI/Anthropic sk-, Slack xox*-)
    # and underscore (Stripe sk_live_, GitHub github_pat_, npm_) prefix styles.
    (re.compile(r"\b(?:sk|pk|rk|sess|ghp|gho|ghu|ghs|ghr|xox[abprs])-[-A-Za-z0-9_]{12,}\b", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), "[REDACTED_STRIPE_KEY]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\b(?:glpat|gho|npm|dop_v1|shpat|shpss|xapp)[-_][A-Za-z0-9_-]{16,}\b", re.I), "[REDACTED_TOKEN]"),
    (re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"), "[REDACTED_SENDGRID_KEY]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\bya29\.[A-Za-z0-9._-]{20,}\b"), "[REDACTED_GOOGLE_OAUTH]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{25,}\b"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I), "Bearer [REDACTED]"),
    # key = value / key: value assignments. Broadened key list incl. token, auth,
    # authorization, credential, private_key, connection strings, and PT terms
    # (senha, chave). Optional leading ``export``. Value may be quoted.
    (re.compile(r"(?i)\b((?:export\s+)?(?:api[_-]?key|access[_-]?key(?:[_-]?id)?|secret[_-]?access[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|id[_-]?token|client[_-]?secret|client[_-]?token|app[_-]?secret|private[_-]?key|secret[_-]?key|api[_-]?secret|service[_-]?key|conn(?:ection)?[_-]?string|database[_-]?url|dsn|password|passwd|pwd|senha|secret|token|credential|authorization|pat|chave))\b[\"']?\s*[:=]\s*[\"']?[^\s,;\"'`]{6,}"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@"), r"\1[REDACTED]@"),
    # Generic connection strings with embedded credentials (postgres://, mongodb+srv://, redis://, amqp://).
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@"), r"\1[REDACTED]@"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
    # Catch-all for a pasted high-entropy secret with no recognizable prefix or key.
    # Requires length >= 32 AND mixed classes (>=1 upper, >=1 lower, >=1 digit) so it
    # targets tokens/passwords, not prose, git SHAs (hex-only), or short hashes.
    (re.compile(r"(?<![A-Za-z0-9+_=-])(?=[A-Za-z0-9+_=-]{32,}(?![A-Za-z0-9+_=-]))(?=[A-Za-z0-9+_=-]*[A-Z])(?=[A-Za-z0-9+_=-]*[a-z])(?=[A-Za-z0-9+_=-]*\d)[A-Za-z0-9+_=-]{32,}"), "[REDACTED_SECRET]"),
    # Avoid treating date-stamped model names such as ``model-4-5-20251001``
    # as phone numbers while still redacting standalone phone-like sequences.
    (re.compile(r"(?<![A-Za-z0-9-])(?:\+?\d[\d(). -]{7,}\d)(?!\w)"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "[REDACTED_ID]"),
    (re.compile(r"(https?://[^\s?#]+)[?#][^\s]+", re.I), r"\1"),
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Cursor stores epoch milliseconds.
        if value > 10_000_000_000:
            value /= 1000
        try:
            return dt.datetime.fromtimestamp(value, dt.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return parse_time(int(value))
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or dt.timezone.utc).astimezone(dt.timezone.utc)
        except ValueError:
            return None
    return None


def iso(value: dt.datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def redact(text: Any, limit: int = 360) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.replace(str(HOME), "~")
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict) and part.get("type") in {"text", "input_text", "output_text"}:
                bits.append(str(part.get("text", "")))
        return " ".join(bits)
    if isinstance(content, dict):
        return str(content.get("text", ""))
    return ""


def usable_sample(text: str) -> bool:
    low = text.lower()
    return len(text.strip()) >= 12 and not any(marker in low for marker in (
        "<environment_context>", "<in-app-browser-context", "<permissions instructions>",
        "# agents.md instructions", "message type: new_task",
    ))


def model_family(name: Any) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    low = name.lower()
    if "luna" in low:
        return "luna"
    if "codex" in low:
        return "openai-codex"
    if "gpt" in low or "openai" in low or re.search(r"\bo[134]\b", low):
        return "openai-gpt"
    if "claude" in low or "anthropic" in low:
        return "anthropic-claude"
    if "gemini" in low or "google" in low:
        return "google-gemini"
    if "llama" in low or "meta" in low:
        return "meta-llama"
    if "mistral" in low:
        return "mistral"
    if "deepseek" in low:
        return "deepseek"
    return "other-model"


def tool_category(name: Any) -> str:
    low = str(name or "").lower()
    if any(x in low for x in ("browser", "chrome", "computer", "playwright", "screenshot")):
        return "browser"
    if any(x in low for x in ("search", "query", "fetch", "web", "research")):
        return "research"
    if any(x in low for x in ("plan", "goal", "todo")):
        return "planning"
    if any(x in low for x in ("agent", "task", "delegate")):
        return "delegation"
    if any(x in low for x in ("apply_patch", "write", "edit", "create_file")):
        return "filesystem_write"
    if any(x in low for x in ("read", "view", "glob", "find", "list", "grep")):
        return "filesystem_read"
    if any(x in low for x in ("git", "github", "commit", "pull_request")):
        return "version_control"
    if any(x in low for x in ("sql", "database", "supabase", "sqlite")):
        return "database"
    if any(x in low for x in ("message", "mail", "slack", "calendar", "linear")):
        return "communication"
    if any(x in low for x in ("shell", "bash", "terminal", "exec", "command")):
        return "shell"
    return "other"


_SIGNAL_PATTERNS = {
    "research": re.compile(r"\b(search|research|pesquis|investig|look up|context)\w*", re.I),
    "planning": re.compile(r"\b(plan|roadmap|spec|planej|estrat[eé]g|arquitet)\w*", re.I),
    "implementation": re.compile(r"\b(implement|build|create|edit|alter|cria|fa[cç]a|implementar?)\w*", re.I),
    "validation": re.compile(r"\b(test|valid|verify|qa|lint|chec|homolog)\w*", re.I),
    "handoff": re.compile(r"\b(handoff|resum|document|report|relat[oó]rio|entrega)\w*", re.I),
    "blocked": re.compile(r"\b(blocked|bloquead|impedid|sem acesso|permission denied)\b", re.I),
    "error": re.compile(r"\b(error|erro|failed|failure|falhou|exception|bug)\b", re.I),
    "debugging": re.compile(r"\b(debug|diagnos|corrig|fix|bug|erro|error)\w*", re.I),
    "review": re.compile(r"\b(review|audit|revis|avali|critique)\w*", re.I),
}


class CaseBuilder:
    """Accumulate only bounded, non-content metadata for one local session."""

    def __init__(self, source: str, local_id: str, is_subagent: bool = False) -> None:
        self.source = source
        self.local_id = local_id
        self.is_subagent = is_subagent
        self.start: dt.datetime | None = None
        self.end: dt.datetime | None = None
        self.models: set[str] = set()
        self.tools: list[str] = []
        self.tool_counts: collections.Counter[str] = collections.Counter()
        self.messages: collections.Counter[str] = collections.Counter()
        self.signals = {name: False for name in SIGNAL_NAMES}
        self.intent_hits = collections.Counter()
        self.has_safe_intent = False

    def touch(self, when: dt.datetime | None) -> None:
        if when:
            self.start = min(self.start, when) if self.start else when
            self.end = max(self.end, when) if self.end else when

    def add_model(self, model: Any) -> None:
        family = model_family(model)
        if family:
            self.models.add(family)

    def add_message(self, role: str, text: str = "") -> None:
        if role in {"user", "assistant", "system", "developer"}:
            self.messages[role] += 1
        if not text:
            return
        if role == "user" and usable_sample(text):
            self.has_safe_intent = True
        # System/developer instructions mention every workflow concept and would
        # make all signals true. User text establishes intent; assistant text
        # may contribute only closure/validation outcomes.
        allowed_signals = set(_SIGNAL_PATTERNS) if role == "user" else (
            {"validation", "handoff", "blocked", "error"} if role == "assistant" else set()
        )
        for signal, pattern in _SIGNAL_PATTERNS.items():
            if signal not in allowed_signals:
                continue
            if pattern.search(text):
                if signal in self.signals:
                    self.signals[signal] = True
                if role == "user" and signal in INTENT_LABELS:
                    self.intent_hits[signal] += 1

    def add_tool(self, name: Any) -> None:
        category = tool_category(name)
        self.tool_counts[category] += 1
        if not self.tools or self.tools[-1] != category:
            if len(self.tools) < 24:
                self.tools.append(category)
        if category in {"research"}:
            self.signals["research"] = True
        if category == "planning":
            self.signals["planning"] = True
        if category in {"filesystem_write", "shell", "version_control", "database"}:
            self.signals["implementation"] = True
        if category == "browser":
            self.signals["browser"] = True

    def finish(self) -> dict[str, Any]:
        if self.intent_hits:
            intent = max(self.intent_hits, key=lambda key: (self.intent_hits[key], key))
        elif self.signals["error"]:
            intent = "debugging"
        elif self.signals["validation"]:
            intent = "validation"
        elif self.signals["implementation"]:
            intent = "implementation"
        elif self.signals["planning"]:
            intent = "planning"
        elif self.signals["research"]:
            intent = "research"
        else:
            intent = "unknown"
        limits = [
            "Intent is a deterministic coarse paraphrase, not a quoted prompt.",
            "Tool arguments, outputs, code, paths, and names are intentionally omitted.",
            "Model identifiers are reduced to broad families.",
            "Signals are heuristic and may be incomplete.",
        ]
        if not self.has_safe_intent:
            limits.append("No safe user intent was retained for this session.")
        event_locators = [
            {
                "event_id": hmac.new(
                    ASSESSMENT_SALT,
                    f"{self.source}\0{self.local_id}\0{index}\0{category}".encode(),
                    hashlib.sha256,
                ).hexdigest()[:12],
                "ordinal": index,
                "event_type": category,
            }
            for index, category in enumerate(self.tools)
        ]
        return {
            "case_id": hmac.new(
                ASSESSMENT_SALT,
                f"{self.source}\0{self.local_id}".encode(),
                hashlib.sha256,
            ).hexdigest()[:16],
            "source": self.source,
            "period": {"start": self.start.date().isoformat() if self.start else None, "end": self.end.date().isoformat() if self.end else None},
            "session_type": "subagent" if self.is_subagent else "parent",
            "models": sorted(self.models),
            "intent": INTENT_LABELS[intent],
            "tool_sequence": self.tools,
            "event_locators": event_locators,
            "counts": {"messages": dict(sorted(self.messages.items())), "tool_calls": sum(self.tool_counts.values()), "tool_categories": dict(sorted(self.tool_counts.items()))},
            "signals": dict(self.signals),
            "limitations": limits,
        }


class Metrics:
    def __init__(self, source: str, max_samples: int, max_cases_per_month: int = 2) -> None:
        self.source = source
        self.max_samples = max_samples
        self.max_cases_per_month = max_cases_per_month
        self.sessions = 0
        self.messages = collections.Counter()
        self.tool_calls = 0
        self.subagent_sessions = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.files_examined = 0
        self.records_examined = 0
        self.models: collections.Counter[str] = collections.Counter()
        self.model_metrics: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        self.samples: list[dict[str, Any]] = []
        self.workflow_case_buckets: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        self.earliest: dt.datetime | None = None
        self.latest: dt.datetime | None = None
        self.errors: list[str] = []

    def touch(self, when: dt.datetime | None) -> None:
        if when:
            self.earliest = min(self.earliest, when) if self.earliest else when
            self.latest = max(self.latest, when) if self.latest else when

    def model(self, name: Any, field: str = "events", amount: int = 1) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        name = redact(name.strip(), 100)
        # ``models`` is a lightweight distribution of observed model-tagged
        # events; the field-specific breakdown remains in ``model_metrics``.
        self.models[name] += amount
        self.model_metrics[name][field] += amount

    def sample(self, text: str, when: dt.datetime | None, model: str | None = None) -> None:
        if len(self.samples) >= self.max_samples or not usable_sample(text):
            return
        clean = redact(text)
        digest = hmac.new(ASSESSMENT_SALT, text.encode("utf-8", "replace"), hashlib.sha256).hexdigest()[:12]
        safe_model = redact(model, 100) if model else None
        self.samples.append({"source": self.source, "timestamp": iso(when), "model": safe_model, "text": clean, "sample_id": digest})

    def workflow_case(self, case: dict[str, Any]) -> None:
        """Keep at most max_cases_per_month deterministic candidates per calendar month."""
        period = case.get("period") or {}
        bucket = str(period.get("start") or period.get("end") or "unknown")[:7]
        candidates = self.workflow_case_buckets[bucket]
        candidates.append(case)
        candidates.sort(key=lambda item: item["case_id"])
        del candidates[self.max_cases_per_month:]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions,
            "messages": dict(sorted(self.messages.items())),
            "tool_calls": self.tool_calls,
            "subagent_sessions": self.subagent_sessions,
            "tokens": {"input": self.input_tokens, "output": self.output_tokens},
            "models": dict(self.models.most_common()),
            "model_metrics": {k: dict(v) for k, v in sorted(self.model_metrics.items())},
            "time_range": {"earliest": iso(self.earliest), "latest": iso(self.latest)},
        }


def iter_jsonl(path: Path, metrics: Metrics) -> Iterator[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        metrics.records_examined += 1
                        yield value
                except (json.JSONDecodeError, ValueError):
                    continue
    except (OSError, PermissionError) as exc:
        metrics.errors.append(redact(f"Could not read {path}: {exc}"))


def discover_jsonl(roots: Iterable[Path], errors: list[str] | None = None) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix == ".jsonl":
            found.add(root)
        elif root.is_dir():
            try:
                found.update(root.rglob("*.jsonl"))
            except (OSError, PermissionError) as exc:
                if errors is not None:
                    errors.append(redact(f"Could not enumerate {root}: {exc}"))
    return sorted(found)


def file_may_overlap(path: Path, cutoff: dt.datetime | None) -> bool:
    if cutoff is None:
        return True
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc) >= cutoff
    except OSError:
        return True


def scan_codex(cutoff: dt.datetime | None, max_samples: int, max_cases_per_month: int = 2) -> Metrics:
    m = Metrics("codex", max_samples, max_cases_per_month)
    roots = [HOME / ".codex/sessions", HOME / ".codex/archived_sessions"]
    for path in discover_jsonl(roots, m.errors):
        if not file_may_overlap(path, cutoff):
            continue
        session_seen = False
        current_model = None
        is_subagent = False
        case = CaseBuilder("codex", str(path))
        file_input_tokens = 0
        file_output_tokens = 0
        records = iter_jsonl(path, m)
        for rec in records:
            when = parse_time(rec.get("timestamp"))
            if cutoff and when and when < cutoff:
                continue
            typ, payload = rec.get("type"), rec.get("payload") or {}
            if typ == "session_meta":
                source = json.dumps(payload.get("thread_source", ""), ensure_ascii=False).lower()
                is_subagent = "subagent" in source or "agent" in source
                case.is_subagent = is_subagent
            if typ == "turn_context":
                current_model = payload.get("model") or current_model
                m.model(current_model, "turns")
                case.add_model(current_model)
            if typ == "response_item":
                ptype, role = payload.get("type"), payload.get("role")
                if ptype in {"function_call", "custom_tool_call", "computer_call"}:
                    m.tool_calls += 1
                    case.add_tool(payload.get("name") or ("computer" if ptype == "computer_call" else ptype))
                if role in {"user", "assistant", "system", "developer"}:
                    m.messages[role] += 1
                    m.model(current_model, f"{role}_messages")
                    message_text = text_from_content(payload.get("content"))
                    case.add_message(role, message_text)
                    if role == "user":
                        m.sample(message_text, when, current_model)
            if typ == "event_msg":
                event_text = payload.get("message") or payload.get("error") or ""
                if isinstance(event_text, str) and event_text:
                    case.add_message("system", event_text)
            if typ == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                total = info.get("total_token_usage") or {}
                # This is cumulative; retain the greatest value observed per file.
                file_input_tokens = max(file_input_tokens, int(total.get("input_tokens", 0) or 0))
                file_output_tokens = max(file_output_tokens, int(total.get("output_tokens", 0) or 0))
            m.touch(when)
            case.touch(when)
            session_seen = True
        if session_seen:
            m.sessions += 1
            m.files_examined += 1
            m.subagent_sessions += int(is_subagent)
            m.input_tokens += file_input_tokens
            m.output_tokens += file_output_tokens
            m.workflow_case(case.finish())
    return m


def usage_int(usage: dict[str, Any], *names: str) -> int:
    for name in names:
        value = usage.get(name)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


CLAUDE_PROJECTS_ROOT = HOME / ".claude/projects"
OPENCODE_DB = HOME / ".local/share/opencode/opencode.db"


def claude_project_key(path: Path) -> str:
    """Return the top-level project directory name for a Claude session path."""
    try:
        rel = path.relative_to(CLAUDE_PROJECTS_ROOT)
    except ValueError:
        try:
            rel = path.resolve().relative_to(CLAUDE_PROJECTS_ROOT.resolve())
        except (ValueError, OSError):
            return ""
    return rel.parts[0] if rel.parts else ""


def is_background_agent_project(key: str) -> bool:
    """Heuristic: session store written by a background/observer agent, not a person."""
    k = key.lower()
    return "observer" in k or "claude-mem" in k or "claude_mem" in k


def list_claude_projects() -> list[dict[str, Any]]:
    """Enumerate Claude project directories with cheap, read-only metadata for a scope gate."""
    projects: dict[str, dict[str, Any]] = {}
    for path in discover_jsonl([CLAUDE_PROJECTS_ROOT]):
        key = claude_project_key(path)
        if not key:
            continue
        entry = projects.setdefault(key, {"key": key, "sessions": 0, "subagent_files": 0, "_mtime": None})
        entry["sessions"] += 1
        if "/subagents/" in str(path):
            entry["subagent_files"] += 1
        try:
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        except OSError:
            mtime = None
        if mtime and (entry["_mtime"] is None or mtime > entry["_mtime"]):
            entry["_mtime"] = mtime
    result: list[dict[str, Any]] = []
    for entry in projects.values():
        entry["last_modified"] = iso(entry.pop("_mtime"))
        entry["likely_background_agent"] = is_background_agent_project(entry["key"])
        result.append(entry)
    result.sort(key=lambda item: (-item["sessions"], item["key"]))
    return result


def scan_claude(cutoff: dt.datetime | None, max_samples: int,
                include_projects: set[str] | None = None,
                exclude_projects: set[str] | None = None,
                max_cases_per_month: int = 2) -> Metrics:
    m = Metrics("claude", max_samples, max_cases_per_month)
    for path in discover_jsonl([HOME / ".claude/projects"], m.errors):
        if not file_may_overlap(path, cutoff):
            continue
        key = claude_project_key(path)
        if exclude_projects and key in exclude_projects:
            continue
        if include_projects is not None and key not in include_projects:
            continue
        session_seen = False
        is_subagent = "/subagents/" in str(path)
        case = CaseBuilder("claude", str(path), is_subagent)
        for rec in iter_jsonl(path, m):
            when = parse_time(rec.get("timestamp"))
            if cutoff and when and when < cutoff:
                continue
            typ, message = rec.get("type"), rec.get("message") or {}
            if typ in {"user", "assistant"}:
                role = message.get("role") or typ
                m.messages[role] += 1
                model = message.get("model")
                m.model(model, f"{role}_messages")
                case.add_model(model)
                content = message.get("content")
                blocks = content if isinstance(content, list) else []
                m.tool_calls += sum(1 for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use")
                for block in blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        case.add_tool(block.get("name"))
                message_text = text_from_content(content)
                case.add_message(role, message_text)
                if role == "user":
                    m.sample(message_text, when, model)
                usage = message.get("usage") or {}
                m.input_tokens += usage_int(usage, "input_tokens")
                m.output_tokens += usage_int(usage, "output_tokens")
            m.touch(when)
            case.touch(when)
            session_seen = True
        if session_seen:
            m.sessions += 1
            m.files_examined += 1
            m.subagent_sessions += int(is_subagent)
            m.workflow_case(case.finish())
    return m


def sqlite_ro(path: Path, immutable: bool = True) -> sqlite3.Connection:
    # mode=ro forbids writes. Immutable stores are safe to read without their WAL.
    query = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    uri = "file:" + str(path).replace("?", "%3f") + query
    return sqlite3.connect(uri, uri=True)


def cursor_text(bubble: dict[str, Any]) -> str:
    return text_from_content(bubble.get("text") or bubble.get("richText") or "")


def cursor_state_db_candidates() -> list[Path]:
    """Cursor's globalStorage lives under a platform-specific config root."""
    rel = "User/globalStorage/state.vscdb"
    candidates = [
        HOME / "Library/Application Support/Cursor" / rel,  # macOS
        HOME / ".config/Cursor" / rel,  # Linux
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Cursor" / rel)  # Windows
    candidates.append(HOME / "AppData/Roaming/Cursor" / rel)  # Windows fallback
    return candidates


def scan_cursor(cutoff: dt.datetime | None, max_samples: int, max_cases_per_month: int = 2) -> Metrics:
    m = Metrics("cursor", max_samples, max_cases_per_month)
    db = next((p for p in cursor_state_db_candidates() if p.exists()), None)
    if db is None:
        return m
    try:
        con = sqlite_ro(db)
        try:
            headers: dict[str, tuple[dt.datetime | None, dict[str, Any], CaseBuilder]] = {}
            for cid, created, updated, subagent, value in con.execute(
                "SELECT composerId, createdAt, lastUpdatedAt, isSubagent, value FROM composerHeaders"
            ):
                when = parse_time(created or updated)
                if cutoff and when and when < cutoff:
                    continue
                try:
                    head = json.loads(value) if value else {}
                except (json.JSONDecodeError, TypeError):
                    head = {}
                case = CaseBuilder("cursor", str(cid), bool(subagent or head.get("isSubagent")))
                case.touch(when)
                headers[str(cid)] = (when, head, case)
                m.sessions += 1
                m.subagent_sessions += int(bool(subagent or head.get("isSubagent")))
                m.touch(when)
                model = head.get("model") or head.get("modelName")
                m.model(model, "sessions")
                case.add_model(model)
            m.records_examined += len(headers)
            # composerData contains the actual bubbles on current Cursor builds.
            for key, value in con.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"):
                cid = str(key).split(":", 1)[-1]
                if headers and cid not in headers:
                    continue
                try:
                    data = json.loads(value)
                except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                    continue
                when = parse_time(data.get("createdAt")) or (headers.get(cid) or (None, {}, None))[0]
                if cutoff and when and when < cutoff:
                    continue
                model = data.get("model") or data.get("modelName") or data.get("defaultModel")
                case = (headers.get(cid) or (None, {}, None))[2]
                if case:
                    case.touch(when)
                    case.add_model(model)
                for bubble in data.get("conversation") or []:
                    if not isinstance(bubble, dict):
                        continue
                    btype = bubble.get("type")
                    role = "user" if btype in {1, "1", "user", "human"} else "assistant"
                    m.messages[role] += 1
                    m.model(model, f"{role}_messages")
                    message_text = cursor_text(bubble)
                    if case:
                        case.add_message(role, message_text)
                    if role == "user":
                        m.sample(message_text, when, model)
                    caps = bubble.get("capabilitiesRan") or bubble.get("capabilityStatuses") or []
                    m.tool_calls += len(caps) if isinstance(caps, (list, dict)) else 0
                    if case:
                        cap_items = caps.keys() if isinstance(caps, dict) else caps if isinstance(caps, list) else []
                        for cap in cap_items:
                            if isinstance(cap, dict):
                                case.add_tool(cap.get("name") or cap.get("type"))
                            else:
                                case.add_tool(cap)
                m.records_examined += 1
            for _when, _head, case in headers.values():
                m.workflow_case(case.finish())
            m.files_examined = 1
        finally:
            con.close()
    except (sqlite3.Error, OSError, PermissionError) as exc:
        m.errors.append(redact(f"Cursor database unavailable: {exc}"))
    return m


def json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else {}
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def opencode_model_name(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    data = json_object(value)
    model = data.get("id") or data.get("modelID") if data else value
    return model if isinstance(model, str) and model.strip() else None


def scan_opencode(cutoff: dt.datetime | None, max_samples: int, max_cases_per_month: int = 2) -> Metrics:
    """Read retained OpenCode sessions from the local SQLite store without modifying it."""
    m = Metrics("opencode", max_samples, max_cases_per_month)
    if not OPENCODE_DB.exists():
        return m
    try:
        # OpenCode actively uses WAL, so immutable=1 would hide committed recent data.
        con = sqlite_ro(OPENCODE_DB, immutable=False)
        try:
            sessions = con.execute(
                "SELECT id, parent_id, model, tokens_input, tokens_output, time_created, time_updated FROM session"
            )
            for session_id, parent_id, session_model, input_tokens, output_tokens, created, updated in sessions:
                session_model = opencode_model_name(session_model)
                when = parse_time(updated or created)
                if cutoff and when and when < cutoff:
                    continue
                is_subagent = bool(parent_id)
                case = CaseBuilder("opencode", str(session_id), is_subagent)
                case.touch(parse_time(created))
                case.touch(parse_time(updated))
                case.add_model(session_model)
                m.model(session_model, "sessions")
                m.sessions += 1
                m.subagent_sessions += int(is_subagent)
                m.input_tokens += int(input_tokens or 0)
                m.output_tokens += int(output_tokens or 0)
                m.touch(parse_time(created))
                m.touch(parse_time(updated))

                messages: dict[str, tuple[str, dt.datetime | None, str | None]] = {}
                for message_id, message_created, raw_data in con.execute(
                    "SELECT id, time_created, data FROM message WHERE session_id = ? ORDER BY time_created", (session_id,)
                ):
                    data = json_object(raw_data)
                    role = data.get("role")
                    if role not in {"user", "assistant", "system", "developer"}:
                        continue
                    model = data.get("modelID") or session_model
                    messages[str(message_id)] = (role, parse_time(message_created), model if isinstance(model, str) else None)

                text_by_message: dict[str, list[str]] = collections.defaultdict(list)
                for message_id, part_created, raw_data in con.execute(
                    "SELECT p.message_id, p.time_created, p.data FROM part AS p "
                    "JOIN message AS msg ON msg.id = p.message_id WHERE msg.session_id = ? ORDER BY p.time_created",
                    (session_id,),
                ):
                    data = json_object(raw_data)
                    part_type = data.get("type")
                    if part_type == "tool":
                        m.tool_calls += 1
                        case.add_tool(data.get("tool"))
                    elif part_type == "text" and isinstance(data.get("text"), str):
                        text_by_message[str(message_id)].append(data["text"])
                    case.touch(parse_time(part_created))
                    m.records_examined += 1

                for message_id, (role, message_when, model) in messages.items():
                    text = " ".join(text_by_message[message_id])
                    m.messages[role] += 1
                    m.model(model, f"{role}_messages")
                    case.add_model(model)
                    case.add_message(role, text)
                    if role == "user":
                        m.sample(text, message_when, model)
                    case.touch(message_when)
                    m.records_examined += 1
                m.workflow_case(case.finish())
            m.files_examined = 1
        finally:
            con.close()
    except (sqlite3.Error, OSError, PermissionError) as exc:
        m.errors.append(redact(f"OpenCode database unavailable: {exc}"))
    return m


def source_presence() -> dict[str, dict[str, Any]]:
    locations = {
        "codex": [HOME / ".codex/sessions", HOME / ".codex/archived_sessions"],
        "claude": [HOME / ".claude/projects"],
        "cursor": cursor_state_db_candidates(),
        "opencode": [OPENCODE_DB],
    }
    return {
        name: {
            "detected": any(p.exists() for p in paths),
            "locations_checked": [str(p).replace(str(HOME), "~") for p in paths],
        }
        for name, paths in locations.items()
    }


def codex_session_estimate() -> dict[str, Any]:
    """Cheap, read-only session/file count for the Codex source, for the scope gate."""
    files = discover_jsonl([HOME / ".codex/sessions", HOME / ".codex/archived_sessions"])
    latest: dt.datetime | None = None
    for path in files:
        try:
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        except OSError:
            continue
        if latest is None or mtime > latest:
            latest = mtime
    return {"sessions": len(files), "last_modified": iso(latest)}


def opencode_session_estimate() -> dict[str, Any]:
    if not OPENCODE_DB.exists():
        return {"sessions": 0, "last_modified": None}
    try:
        con = sqlite_ro(OPENCODE_DB, immutable=False)
        try:
            sessions, latest = con.execute("SELECT COUNT(*), MAX(time_updated) FROM session").fetchone()
            return {"sessions": int(sessions or 0), "last_modified": iso(parse_time(latest))}
        finally:
            con.close()
    except (sqlite3.Error, OSError, PermissionError):
        return {"sessions": 0, "last_modified": None}


def _models_in_file(path: Path, limit: int = 200) -> set[str]:
    """Read-only, light extraction of distinct model identifiers from one session file.

    Reads at most ``limit`` records and only pulls the model field — no content,
    no redaction, no sampling — so it is far cheaper than a full scan.
    """
    found: set[str] = set()
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for i, line in enumerate(handle):
                if i >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                for cand in (msg.get("model"), rec.get("model"), rec.get("modelName"),
                             (rec.get("payload") or {}).get("model") if isinstance(rec.get("payload"), dict) else None):
                    if isinstance(cand, str) and cand.strip():
                        found.add(cand.strip())
    except OSError:
        pass
    return found


def llm_signals(exclude_background: bool = True) -> dict[str, dict[str, int]]:
    """Which LLMs the person has signals from, per source, as {raw_model: session_count}.

    Read-only and light. For Claude, background-agent project dirs are skipped so the
    tally reflects the person's own usage, not an observer agent's model calls.
    """
    signals: dict[str, dict[str, int]] = {}
    # Claude: per project dir (skip background/observer stores).
    claude: collections.Counter[str] = collections.Counter()
    for path in discover_jsonl([CLAUDE_PROJECTS_ROOT]):
        if exclude_background and is_background_agent_project(claude_project_key(path)):
            continue
        for model in _models_in_file(path):
            claude[model] += 1
    if claude:
        signals["claude"] = dict(claude.most_common())
    # Codex: sessions + archived.
    codex: collections.Counter[str] = collections.Counter()
    for path in discover_jsonl([HOME / ".codex/sessions", HOME / ".codex/archived_sessions"]):
        for model in _models_in_file(path):
            codex[model] += 1
    if codex:
        signals["codex"] = dict(codex.most_common())
    # OpenCode stores the selected model once per session in its local database.
    if OPENCODE_DB.exists():
        try:
            con = sqlite_ro(OPENCODE_DB, immutable=False)
            try:
                opencode = collections.Counter()
                for model, count in con.execute("SELECT model, COUNT(*) FROM session WHERE model IS NOT NULL AND model != '' GROUP BY model"):
                    name = opencode_model_name(model)
                    if name:
                        opencode[name] += int(count)
            finally:
                con.close()
            if opencode:
                signals["opencode"] = dict(opencode.most_common())
        except (sqlite3.Error, OSError, PermissionError):
            pass
    return signals


def parse_sources(value: str) -> list[str]:
    if value.strip().lower() == "auto":
        presence = source_presence()
        return [name for name in SOURCE_NAMES if presence[name]["detected"]]
    selected = []
    for raw in value.split(","):
        name = raw.strip().lower().replace("claude-code", "claude")
        if name not in SOURCE_NAMES:
            raise argparse.ArgumentTypeError(f"unknown source {raw!r}; use auto or: {', '.join(SOURCE_NAMES)}")
        if name not in selected:
            selected.append(name)
    if not selected:
        raise argparse.ArgumentTypeError("at least one source is required")
    return selected


def limitations(name: str) -> list[str]:
    shared = "Counts reflect histories retained locally; deleted, cloud-only, incognito, and disabled-history sessions are unavailable."
    return {
        "codex": [shared, "Codex schemas vary by app/CLI version; encrypted reasoning is never decrypted or sampled.", "Token totals may be incomplete when cumulative token events are absent."],
        "claude": [shared, "Claude Code sidechain/subagent files are counted as sessions and identified separately.", "Cached/system-only records and attachments are not treated as conversational messages."],
        "cursor": [shared, "Cursor local storage changes between releases; the scanner reads composerHeaders and locally retained composerData only.", "Some Cursor model names and token counts are not persisted in readable local fields."],
        "opencode": [shared, "OpenCode reads its local SQLite session store in read-only mode, including its active WAL; cloud-shared or deleted sessions are not available.", "Only text parts and tool names are sampled; reasoning, tool arguments, outputs, diffs, and attachments are not retained."],
    }[name]


def residual_sensitive_patterns(values: Iterable[str]) -> int:
    """Count redactable patterns left in user-controlled output fields."""
    hits = 0
    for value in values:
        for pattern, _replacement in SECRET_PATTERNS:
            hits += len(pattern.findall(value))
    return hits


def validate_workflow_cases(cases: list[dict[str, Any]]) -> None:
    """Fail closed: case output is restricted to a closed, non-content schema."""
    expected = {"case_id", "source", "period", "session_type", "models", "intent", "tool_sequence", "event_locators", "counts", "signals", "limitations"}
    for case in cases:
        if set(case) != expected:
            raise ValueError("workflow case privacy validation failed: unexpected fields")
        if not re.fullmatch(r"[0-9a-f]{16}", case["case_id"]):
            raise ValueError("workflow case privacy validation failed: invalid local hash")
        if case["source"] not in SOURCE_NAMES or case["session_type"] not in {"parent", "subagent"}:
            raise ValueError("workflow case privacy validation failed: invalid source or session flag")
        period = case["period"]
        if set(period) != {"start", "end"} or any(value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in period.values()):
            raise ValueError("workflow case privacy validation failed: invalid period")
        if not isinstance(case["models"], list) or any(value not in MODEL_FAMILIES for value in case["models"]):
            raise ValueError("workflow case privacy validation failed: unsafe model label")
        if case["intent"] not in INTENT_LABELS.values():
            raise ValueError("workflow case privacy validation failed: unsafe intent")
        if not isinstance(case["tool_sequence"], list) or len(case["tool_sequence"]) > 24 or any(value not in TOOL_CATEGORIES for value in case["tool_sequence"]):
            raise ValueError("workflow case privacy validation failed: unsafe tool sequence")
        locators = case["event_locators"]
        if not isinstance(locators, list) or len(locators) != len(case["tool_sequence"]):
            raise ValueError("workflow case privacy validation failed: invalid event locators")
        for index, locator in enumerate(locators):
            if set(locator) != {"event_id", "ordinal", "event_type"}:
                raise ValueError("workflow case privacy validation failed: unexpected locator fields")
            if not re.fullmatch(r"[0-9a-f]{12}", locator["event_id"]) or locator["ordinal"] != index or locator["event_type"] != case["tool_sequence"][index]:
                raise ValueError("workflow case privacy validation failed: invalid event locator")
        counts = case["counts"]
        if set(counts) != {"messages", "tool_calls", "tool_categories"}:
            raise ValueError("workflow case privacy validation failed: invalid counts")
        if not isinstance(counts["tool_calls"], int) or counts["tool_calls"] < 0:
            raise ValueError("workflow case privacy validation failed: invalid tool count")
        if any(k not in {"user", "assistant", "system", "developer"} or not isinstance(v, int) or v < 0 for k, v in counts["messages"].items()):
            raise ValueError("workflow case privacy validation failed: invalid message counts")
        if any(k not in TOOL_CATEGORIES or not isinstance(v, int) or v < 0 for k, v in counts["tool_categories"].items()):
            raise ValueError("workflow case privacy validation failed: invalid category counts")
        if set(case["signals"]) != set(SIGNAL_NAMES) or any(type(value) is not bool for value in case["signals"].values()):
            raise ValueError("workflow case privacy validation failed: invalid signals")
        if not isinstance(case["limitations"], list) or any(value not in CASE_LIMITATIONS for value in case["limitations"]):
            raise ValueError("workflow case privacy validation failed: unsafe limitation")


def build_report(selected: list[str], days: int, max_samples: int, role: str | None,
                 include_projects: set[str] | None = None,
                 exclude_projects: set[str] | None = None,
                 max_cases_per_month: int = 2) -> dict[str, Any]:
    generated = utc_now()
    cutoff = generated - dt.timedelta(days=days) if days else None
    scanners = {"codex": scan_codex, "claude": scan_claude, "cursor": scan_cursor, "opencode": scan_opencode}
    results: dict[str, Metrics] = {}
    for name in selected:
        if name == "claude":
            results[name] = scan_claude(cutoff, max_samples, include_projects, exclude_projects, max_cases_per_month)
        else:
            results[name] = scanners[name](cutoff, max_samples, max_cases_per_month)
    presence = source_presence()
    all_models: collections.Counter[str] = collections.Counter()
    total_messages: collections.Counter[str] = collections.Counter()
    total = {"sessions": 0, "tool_calls": 0, "subagent_sessions": 0, "input_tokens": 0, "output_tokens": 0}
    samples: list[dict[str, Any]] = []
    workflow_cases: list[dict[str, Any]] = []
    for metric in results.values():
        all_models.update(metric.models)
        total_messages.update(metric.messages)
        total["sessions"] += metric.sessions
        total["tool_calls"] += metric.tool_calls
        total["subagent_sessions"] += metric.subagent_sessions
        total["input_tokens"] += metric.input_tokens
        total["output_tokens"] += metric.output_tokens
    # Round-robin across sources so one large history cannot consume the whole
    # qualitative budget. Ordering within each source stays newest-first.
    source_samples = {
        name: sorted(metric.samples, key=lambda x: x.get("timestamp") or "", reverse=True)
        for name, metric in results.items()
    }
    while len(samples) < max_samples and any(source_samples.values()):
        for name in selected:
            if source_samples.get(name) and len(samples) < max_samples:
                samples.append(source_samples[name].pop(0))
    # Recency preference: fill from the MOST RECENT months first, so stale older
    # behavior does not dilute the sample when the total budget binds (how a person
    # works with AI changes over time). Per-month depth is already capped at
    # ingestion by --max-cases-per-month; a global source round-robin keeps one
    # large history from consuming the whole case budget. Cap is --max-samples.
    source_cases: dict[str, list[dict[str, Any]]] = {}
    for name, metric in results.items():
        ordered: list[dict[str, Any]] = []
        for bucket in sorted(metric.workflow_case_buckets, reverse=True):  # newest month first
            ordered.extend(metric.workflow_case_buckets[bucket])
        source_cases[name] = ordered
    while len(workflow_cases) < max_samples and any(source_cases.values()):
        for name in selected:
            if source_cases.get(name) and len(workflow_cases) < max_samples:
                workflow_cases.append(source_cases[name].pop(0))
    validate_workflow_cases(workflow_cases)
    coverage = {}
    for name in SOURCE_NAMES:
        metric = results.get(name)
        coverage[name] = {
            **presence[name],
            "requested": name in selected,
            "scanned": metric is not None,
            "files_examined": metric.files_examined if metric else 0,
            "records_examined": metric.records_examined if metric else 0,
            "errors": metric.errors if metric else [],
        }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso(generated),
        "scan_parameters": {"days": days, "cutoff": iso(cutoff), "sources": selected, "max_samples": max_samples, "max_cases_per_month": max_cases_per_month, "case_selection": "recent_months_first", "role": redact(role, 160) if role else None,
            "claude_project_filter": {
                "applied": include_projects is not None or bool(exclude_projects),
                "included_count": len(include_projects) if include_projects is not None else None,
                "excluded_count": len(exclude_projects) if exclude_projects else 0,
            }},
        "privacy": {
            "mode": "read-only",
            "raw_conversations_included": False,
            "credentials_included": False,
            "sample_policy": "Short user-message excerpts only; secrets, common personal identifiers, URL queries, and home-directory paths are redacted.",
            "workflow_case_locators": {"method": "hmac-sha256", "salt_scope": "assessment_local", "salt_persisted": False},
        },
        "coverage": coverage,
        "aggregate_metrics": {
            "overall": {**total, "messages": dict(sorted(total_messages.items())), "models": dict(all_models.most_common())},
            "by_source": {name: metric.as_dict() for name, metric in results.items()},
        },
        "qualitative_samples": samples,
        "workflow_cases": workflow_cases,
        "source_limitations": {name: limitations(name) for name in selected},
    }
    privacy_fields = [str(sample.get("text", "")) for sample in samples]
    privacy_fields += [str(sample.get("model", "")) for sample in samples if sample.get("model")]
    privacy_fields += [str(report["scan_parameters"].get("role") or "")]
    privacy_fields += [str(error) for item in coverage.values() for error in item.get("errors", [])]
    residuals = residual_sensitive_patterns(privacy_fields)
    report["privacy"]["post_redaction_scan"] = {
        "performed": True,
        "pattern_families": len(SECRET_PATTERNS),
        "residual_matches": residuals,
        "workflow_cases_validated": len(workflow_cases),
    }
    if residuals:
        raise ValueError("post-redaction privacy validation failed; no output was written")
    return report


def safe_output_dir(value: str) -> Path:
    return Path(value).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=safe_output_dir, help="Directory for history-scan.json")
    parser.add_argument("--days", type=int, default=90, help="Lookback in days; 0 scans all retained history (default: 90)")
    parser.add_argument("--max-samples", type=int, default=300, help="Maximum redacted qualitative samples and workflow cases; recent-first (default: 300)")
    parser.add_argument("--max-cases-per-month", type=int, default=50, help="Max representative workflow cases kept per calendar month per source (default: 50)")
    parser.add_argument("--sources", default="auto", help="auto or comma list: codex,claude,cursor,opencode")
    parser.add_argument("--role", default=None, help="Optional self-described role stored as assessment context")
    parser.add_argument("--list-projects", action="store_true", help="Enumerate Claude project directories (read-only) and exit; writes projects.json for a scope gate")
    parser.add_argument("--include-projects", default=None, help="Comma-separated Claude project keys to include exclusively (from --list-projects)")
    parser.add_argument("--exclude-projects", default=None, help="Comma-separated Claude project keys to exclude, e.g. background-agent session stores")
    args = parser.parse_args(argv)
    if args.days < 0:
        parser.error("--days must be 0 or greater")
    if not 0 <= args.max_samples <= 2000:
        parser.error("--max-samples must be between 0 and 2000")
    if not 1 <= args.max_cases_per_month <= 500:
        parser.error("--max-cases-per-month must be between 1 and 500")
    include_projects = {p.strip() for p in args.include_projects.split(",") if p.strip()} if args.include_projects else None
    exclude_projects = {p.strip() for p in args.exclude_projects.split(",") if p.strip()} if args.exclude_projects else None
    if args.list_projects:
        presence = source_presence()
        inventory = {
            "generated_at": iso(utc_now()),
            "claude_projects": list_claude_projects(),
            "codex": {**presence.get("codex", {}), **(codex_session_estimate() if presence.get("codex", {}).get("detected") else {"sessions": 0, "last_modified": None})},
            "cursor": {**presence.get("cursor", {}), "sessions": None, "note": "Cursor guarda sessoes em SQLite; a contagem exige o scan completo"},
            "opencode": {**presence.get("opencode", {}), **opencode_session_estimate()},
            "llm_signals": llm_signals(exclude_background=True),
            "llm_signals_note": "Modelos (LLMs) com sinais por fonte, como {modelo: sessoes}. Claude exclui diretorios de agente de background. Escolha quais fontes/LLMs seguir na analise.",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            args.output_dir.chmod(0o700)
        except OSError:
            pass
        listing = args.output_dir / "projects.json"
        listing.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            listing.chmod(0o600)
        except OSError:
            pass
        print(listing)
        return 0
    try:
        selected = parse_sources(args.sources)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    try:
        report = build_report(selected, args.days, args.max_samples, args.role, include_projects, exclude_projects, args.max_cases_per_month)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"scan_histories: {exc}", file=sys.stderr)
        return 2
    if report["aggregate_metrics"]["overall"]["sessions"] == 0:
        checked = [path for source in report["coverage"].values() for path in source["locations_checked"]]
        print("scan_histories: no supported local history found; checked " + ", ".join(checked), file=sys.stderr)
        return 3
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        args.output_dir.chmod(0o700)
    except OSError:
        pass
    output = args.output_dir / "history-scan.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        output.chmod(0o600)
    except OSError:
        pass
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
