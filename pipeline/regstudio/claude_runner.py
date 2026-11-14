"""Run Claude Code headless on the Mac mini and return schema-checked JSON.

Calls `claude -p --output-format json` with the prompt on stdin, under whatever account
the CLI is signed in with (the jouleWise subscription). Extra flags can be passed with
REGSTUDIO_CLAUDE_ARGS, e.g. "--model opus".
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess

import jsonschema

from . import config


class ClaudeError(RuntimeError):
    pass


class UsageLimitReached(ClaudeError):
    """The subscription limit was hit; stop the run and let the next one resume."""


FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)
LIMIT_HINTS = ("usage limit", "rate limit", "limit reached", "quota")


def _extract_json(text: str):
    text = text.strip()
    m = FENCE.search(text)
    if m:
        text = m.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ClaudeError("no JSON object in the model's reply")
        text = text[start:end + 1]
    return json.loads(text)


def _call(prompt: str) -> str:
    cmd = [config.CLAUDE_BIN, "-p", "--output-format", "json"]
    if config.CLAUDE_MODEL:
        cmd += ["--model", config.CLAUDE_MODEL]
    cmd += shlex.split(os.environ.get("REGSTUDIO_CLAUDE_ARGS", ""))
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=config.CLAUDE_TIMEOUT_S)
    except FileNotFoundError as e:
        raise ClaudeError(f"claude CLI not found at '{config.CLAUDE_BIN}'") from e
    except subprocess.TimeoutExpired as e:
        raise ClaudeError("claude CLI timed out") from e
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if "not enabled in this environment" in out or "only `claude -p" in out:
        raise ClaudeError("this shell cannot run Claude Code; run the stage from the Mac's own Terminal")
    blob = (out + " " + err).lower()
    if proc.returncode != 0:
        if any(h in blob for h in LIMIT_HINTS):
            raise UsageLimitReached(err or out)
        raise ClaudeError(f"claude exited {proc.returncode}: {(err or out)[:500]}")
    try:
        envelope = json.loads(out)
    except json.JSONDecodeError:
        return out  # older CLI printing plain text
    if envelope.get("is_error"):
        msg = str(envelope.get("result", ""))
        if any(h in msg.lower() for h in LIMIT_HINTS):
            raise UsageLimitReached(msg)
        raise ClaudeError(msg[:500])
    return str(envelope.get("result", ""))


def ask_json(prompt: str, schema: dict, retries: int = 1) -> dict:
    """Send the prompt; parse and validate the JSON reply; retry once with the errors."""
    validator = jsonschema.validators.validator_for(schema)(schema)
    from .learning import with_notes   # the legal team's approved house notes go with every request
    prompt = with_notes(prompt)
    attempt_prompt = prompt
    last_error = ""
    for _ in range(retries + 1):
        reply = _call(attempt_prompt)
        try:
            data = _extract_json(reply)
            errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if not errors:
                return data
            last_error = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        except (ClaudeError, json.JSONDecodeError) as e:
            last_error = str(e)
        attempt_prompt = (prompt + "\n\nYour previous reply was not valid: " + last_error
                          + "\nReturn ONLY the corrected JSON object.")
    raise ClaudeError(f"invalid JSON after retry: {last_error}")
