"""Translate a pull request body.

Called through ``config.translate`` for every supported language other than the
external one; the result is marked as a machine translation next to the batch.
The translation comes from ``LETHEBAR_TRANSLATION_FILE`` when that is set, so a
body can be translated where no API key is available; otherwise it is asked of
the chat endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
MAX_BODY_CHARS = 12000
HEADER = "<!-- machine translation, en-US to {locale}; the English body is authoritative -->"

SYSTEM_PROMPT = (
    "Translate the pull request body the user sends from English into {locale}. "
    "Keep every markdown structure exactly as it is: headings, bullet markers, "
    "numbered lists, tables and fenced code blocks. Do not translate code, "
    "commands, file paths, identifiers, environment variable names or the "
    "contents of a code block. Keep placeholders such as <batch id> as they are. "
    "Output only the translated markdown, with no preamble and no closing remark."
)


def translate(body: str, locale: str, model: str, endpoint: str, timeout: float) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "DEEPSEEK_API_KEY is not set; export it to translate the pull request body"
        )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(locale=locale)},
            {"role": "user", "content": body},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise SystemExit(f"translation request failed: HTTP {error.code}: {detail}")
    except urllib.error.URLError as error:
        raise SystemExit(f"translation request failed: {error.reason}")
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        raise SystemExit(f"translation response has no message: {str(data)[:300]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="translate a pull request body")
    parser.add_argument("--body", required=True, help="the English body file")
    parser.add_argument("--locale", required=True, help="target locale, for example zh-CN")
    parser.add_argument("--out", required=True, help="where to write the translation")
    args = parser.parse_args(argv)

    body_path = Path(args.body)
    if not body_path.is_file():
        print(f"body file not found: {body_path}", file=sys.stderr)
        return 1
    text = body_path.read_text(encoding="utf-8")
    if not text.strip():
        print(f"body file is empty: {body_path}", file=sys.stderr)
        return 1
    if len(text) > MAX_BODY_CHARS:
        print(
            f"body is {len(text)} characters, over the {MAX_BODY_CHARS} limit; "
            "shorten it rather than send a truncated body",
            file=sys.stderr,
        )
        return 1
    prepared = os.environ.get("LETHEBAR_TRANSLATION_FILE", "").strip()
    if prepared:
        translated = Path(prepared).read_text(encoding="utf-8").strip()
    else:
        try:
            translated = translate(text, args.locale, DEFAULT_MODEL, DEFAULT_ENDPOINT, 120.0)
        except SystemExit as error:
            print(str(error), file=sys.stderr)
            return 1
    if not translated.strip():
        print("the model returned an empty translation", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = HEADER.format(locale=args.locale)
    out_path.write_text(f"{header}\n\n{translated}\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(translated)} characters to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
