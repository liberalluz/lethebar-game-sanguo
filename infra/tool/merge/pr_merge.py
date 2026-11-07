"""Check, and build, the message a squash merge leaves on the default branch.

`gh pr merge --squash` already does the merging. What nothing covers is the two
ends around it:

* The message. With more than one commit GitHub either takes the pull request
  title (Chinese, by convention) or concatenates every commit body, so the
  English subject and the `Why:` / `Batch:` lines get lost. Passing `--subject`
  and `--body-file` fixes that, but the text has to be assembled by hand.
* The result. `infra/checks/check_commit_body.py` reads `origin/main..HEAD` on a
  branch, which means a squashed commit on the default branch is never read by
  anything. A missing `Why:` therefore stays invisible.

This tool covers both ends and nothing in between: it builds the message for a
pull request, and it checks the commit a merge produced.

    python infra/tool/merge/pr_merge.py --self-test
    python infra/tool/merge/pr_merge.py --show --pr 35
    python infra/tool/merge/pr_merge.py --verify-only

Exit codes: 0 no problems, 1 problems found, 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from typing import Any

TYPES = ("feat", "fix", "docs", "test", "refactor", "chore", "ci")

SUBJECT = re.compile(r"^(feat|fix|docs|test|refactor|chore|ci)\([a-z0-9-]+\): \S")
NUMBERED = re.compile(r"\(#\d+\)$")
BATCH_VALUE = re.compile(r"^(B\d+[a-z]?|none)$")
KEY_LINE = re.compile(r"^[A-Z][A-Za-z]*:")
INLINE_CODE = re.compile(r"`([^`\n]*)`")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
FENCE = re.compile(r"^```")
# A commit message is read in a terminal and in `git log`, not rendered: a
# paragraph that arrives as one 700-character line is unreadable there, which is
# what `#80` did. Everything this tool emits is wrapped at this width.
BODY_WIDTH = 72


class MessageError(Exception):
    """The message cannot be built, or the built one does not follow the rules."""


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]


def split_message(text: str) -> tuple[str, str]:
    """Split a full commit message into its subject line and everything below it."""
    lines = _lines(text)
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return "", ""
    subject = lines[0].strip()
    body = "\n".join(lines[1:]).strip("\n")
    return subject, body


def _field(body: str, name: str, multiline: bool = True) -> str | None:
    """Return everything after `<name>:`, including the lines that follow it.

    A reason is often longer than one line, and the existing commit-body gate
    already reads it that way: the text runs until the next `Key:` line. Values
    that are a single word, such as `Batch:`, stop at the end of their line so a
    paragraph after them is not swallowed.
    """
    lines = _lines(body)
    for index, line in enumerate(lines):
        if not line.startswith(name + ":"):
            continue
        value = [line[len(name) + 1 :].strip()]
        if multiline:
            for follow in lines[index + 1 :]:
                if KEY_LINE.match(follow):
                    break
                value.append(follow.strip())
        return "\n".join(part for part in value if part).strip()
    return None


def plain_body(body: str) -> str:
    """Turn a rendered pull-request body into a commit-message body.

    Inline code and bold arrive as literal backticks and asterisks, and one long
    source line stays one long line in `git log`. Fenced blocks are data and are
    left exactly as they are.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False
    fence_lines: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if FENCE.match(line):
            if current:
                paragraphs.append(_wrap(" ".join(current)))
                current = []
            in_fence = not in_fence
            fence_lines.append(line)
            if not in_fence:
                paragraphs.append("\n".join(fence_lines))
                fence_lines = []
            continue
        if in_fence:
            fence_lines.append(line)
            continue
        if not line.strip():
            if current:
                paragraphs.append(_wrap(" ".join(current)))
                current = []
            continue
        if KEY_LINE.match(line) and current:
            # `Why:` and `Batch:` are fields, not prose. Joining them into one
            # paragraph would hide the second one from the reader and from the
            # gate that looks for it at the start of a line.
            paragraphs.append(_wrap(" ".join(current)))
            current = []
        current.append(line.strip())
    if current:
        paragraphs.append(_wrap(" ".join(current)))
    if fence_lines:
        paragraphs.append("\n".join(fence_lines))
    return "\n\n".join(paragraphs).strip("\n")


def _wrap(paragraph: str) -> str:
    """Strip the two inline markers and fill to `BODY_WIDTH`."""
    text = INLINE_CODE.sub(r"\1", paragraph)
    text = BOLD.sub(r"\1", text)
    return textwrap.fill(text, width=BODY_WIDTH) if text.strip() else ""


def _markdown_in_prose(body: str) -> list[str]:
    """Name the markers that survived into the prose."""
    outside: list[str] = []
    in_fence = False
    for line in body.replace("\r\n", "\n").split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    prose = "\n".join(outside)
    problems: list[str] = []
    if INLINE_CODE.search(prose):
        problems.append("the body uses backticks; a commit message is plain text")
    if BOLD.search(prose):
        problems.append("the body uses bold markers; a commit message is plain text")
    long_lines = [line for line in outside if len(line) > BODY_WIDTH + 20]
    if long_lines:
        problems.append(
            f"the body has a line of {max(len(line) for line in long_lines)} characters; "
            f"wrap the prose at {BODY_WIDTH}"
        )
    return problems


def message_problems(
    subject: str, body: str, pr_number: int | None = None, merged: bool = False
) -> list[str]:
    """Every rule this repository puts on a squashed commit, in one place.

    `merged` says the commit already sits on the default branch. Those commits
    always carry the pull request they came from, so the number is required even
    when the caller does not know which pull request it was.
    """
    problems: list[str] = []
    if not subject:
        problems.append("the subject line is empty")
    elif not SUBJECT.match(subject):
        problems.append(
            f"the subject must read 'type(scope): summary', got {subject!r}; "
            f"types are {', '.join(TYPES)}"
        )
    if pr_number is not None:
        if not subject.endswith(f"(#{pr_number})"):
            problems.append(f"the subject must end with '(#{pr_number})'")
    elif merged and not NUMBERED.search(subject):
        problems.append(
            "the subject must end with '(#<number>)'; a commit on the default branch "
            f"always carries its pull request, got {subject!r}"
        )

    why = _field(body, "Why")
    if why is None:
        problems.append("the body has no 'Why:' line")
    elif not why:
        problems.append("the 'Why:' line is empty")

    batch = _field(body, "Batch", multiline=False)
    if batch is None:
        problems.append("the body has no 'Batch:' line")
    elif not batch:
        problems.append("the 'Batch:' line is empty")
    else:
        token, _, rest = batch.partition(" ")
        rest = rest.strip()
        if not BATCH_VALUE.match(token) or (
            rest and not (rest.startswith("(") and rest.endswith(")"))
        ):
            problems.append(
                "'Batch:' must read 'B<number>', 'B<number><letter>' or 'none', "
                f"optionally followed by a parenthetical note; got {batch!r}"
            )

    problems.extend(_markdown_in_prose(body))

    return problems


def _numbered(subject: str, pr_number: int) -> str:
    """Append `(#n)` unless the caller already wrote it.

    The number belongs to the rule, not to the sentence, so a subject that was
    pasted in finished must not come out with the number twice.
    """
    suffix = f"(#{pr_number})"
    if subject.endswith(suffix):
        return subject
    return f"{subject} {suffix}"


def build_message(
    pr_number: int,
    commits: list[dict[str, str]],
    why: str | None = None,
    batch: str | None = None,
    note: str | None = None,
    subject: str | None = None,
) -> str:
    """Assemble the message for a squash merge.

    One commit keeps the logic the repository already used: the commit's own
    subject, the pull request number appended, and the commit's own body, so a
    single-commit pull request needs no arguments at all. More than one commit
    carries no single reason, so `why` and `batch` are required there and the
    body is built from them; the subject falls back to the first commit's own
    subject, which the rule already keeps in English.
    """
    if not commits:
        raise MessageError("the pull request has no commits")
    if pr_number <= 0:
        raise MessageError("--pr must be a positive number")

    if len(commits) == 1:
        subject_line, body = split_message(commits[0].get("message", ""))
        if not subject_line:
            raise MessageError("the commit has no subject line")
        subject = _numbered(subject_line, pr_number)
    else:
        if not subject:
            raise MessageError(
                f"this pull request holds {len(commits)} commits, so --subject is required: "
                "neither the first nor the last commit describes the whole change"
            )
        chosen = subject.strip()
        if not chosen:
            raise MessageError("--subject is empty")
        subject = _numbered(chosen, pr_number)
        if not why:
            raise MessageError(
                f"this pull request holds {len(commits)} commits, so --why is required: "
                "there is no single reason to take from them"
            )
        if not batch:
            raise MessageError(
                f"this pull request holds {len(commits)} commits, so --batch is required "
                "(B<number> for a batch card, none otherwise)"
            )
        body = f"Why: {why.strip()}\nBatch: {batch.strip()}"

    if note:
        body = f"{body}\n\n{note.strip()}" if body else note.strip()

    problems = message_problems(subject, body, pr_number)
    if problems:
        raise MessageError("; ".join(problems))
    return f"{subject}\n\n{body}\n"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise MessageError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def read_commit(ref: str) -> tuple[str, str]:
    subject, body = split_message(_git("log", "-1", "--format=%B", ref))
    return subject, body


def commits_from_payload(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Turn what `gh pr view --json commits` returns into full commit messages.

    gh splits a commit into `messageHeadline` and `messageBody`; this tool wants
    the message whole, the same shape `git log --format=%B` produces.
    """
    commits: list[dict[str, str]] = []
    for item in items:
        headline = str(item.get("messageHeadline", "") or "").strip()
        body = str(item.get("messageBody", "") or "").strip()
        commits.append({"message": f"{headline}\n\n{body}" if body else headline})
    return commits


def repair_cut_headline(items: list[dict[str, Any]], local: str) -> list[dict[str, Any]]:
    """Replace a cut single-commit headline with the local commit.

    gh cuts `messageHeadline` at about seventy characters and moves the rest into
    `messageBody`, so rebuilding the message from the payload starts the body
    with the leftover. The local commit is the truth; use it when it continues
    the cut headline, and refuse rather than emit the leftover.
    """
    if len(items) != 1:
        return items
    headline = str(items[0].get("messageHeadline", "") or "").strip()
    if not headline.endswith(("…", "...")):
        return items
    first, _, rest = local.partition("\n")
    cut = headline.removesuffix("…").removesuffix("...").strip()
    if not first.strip().startswith(cut) or rest.strip().startswith("…"):
        raise MessageError(
            "GitHub cut this commit's headline and the local commit does not continue it: "
            "check out the pull request branch, or pass --subject and --body"
        )
    return [{"messageHeadline": first.strip(), "messageBody": rest.strip()}]


def _local_message() -> str:
    return _git("log", "-1", "--format=%B", "HEAD").strip()


def _gh_commits(pr_number: int) -> list[dict[str, str]]:
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "commits"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise MessageError(f"gh pr view {pr_number} failed: {result.stderr.strip()}")
    payload: dict[str, Any] = json.loads(result.stdout or "{}")
    items = payload.get("commits", [])
    return commits_from_payload(repair_cut_headline(items, _local_message()))


def _self_test() -> int:
    failures = 0

    def check(name: str, got: Any, want: Any) -> None:
        nonlocal failures
        if got != want:
            failures += 1
            print(f"FAIL {name}: got {got!r}, want {want!r}")
        else:
            print(f"ok   {name}")

    def error_of(call) -> str:
        try:
            call()
        except MessageError as exc:
            return str(exc)
        return ""

    one = [
        {
            "message": "feat(app): draw the picture\n\n"
            "Why: assets were validated and then ignored.\nBatch: B9\n"
        }
    ]
    built = build_message(35, one)
    check("one commit keeps its subject", built.splitlines()[0], "feat(app): draw the picture (#35)")
    check("one commit keeps its body", "Why: assets were validated" in built, True)
    check("one commit keeps Batch", "Batch: B9" in built, True)

    built_subject, built_body = split_message(built)
    check(
        "the body does not start by repeating the subject",
        built_body.lstrip().startswith(built_subject),
        False,
    )

    two = [{"message": "feat(app): a\n\nWhy: a\nBatch: B9"}, {"message": "chore(infra): b"}]
    check("two commits need --subject", error_of(lambda: build_message(35, two)).startswith(
        "this pull request holds 2 commits, so --subject is required"
    ), True)
    check("two commits need --why", "--why is required" in error_of(
        lambda: build_message(35, two, subject="feat(app): both")
    ), True)
    check("two commits need --batch", "--batch is required" in error_of(
        lambda: build_message(35, two, subject="feat(app): both", why="one reason")
    ), True)

    built_two = build_message(
        35, two, subject="feat(app): both halves", why="one reason", batch="B9",
        note="Also changed the tool.",
    )
    check("two commits build Why", "Why: one reason" in built_two, True)
    check("two commits build Batch", "Batch: B9" in built_two, True)
    check("two commits append the note", built_two.rstrip().endswith("Also changed the tool."), True)
    check("two commits use the given subject", built_two.splitlines()[0], "feat(app): both halves (#35)")

    chosen = build_message(35, two, why="r", batch="B9", subject="feat(merge): check the message")
    check("an explicit subject wins", chosen.splitlines()[0], "feat(merge): check the message (#35)")

    check("a split batch id is accepted",
          message_problems("feat(app): x (#35)", "Why: y\nBatch: B5a", 35), [])
    check("a longer Why is accepted",
          message_problems("feat(app): x (#35)", "Why: first line\nsecond line\nBatch: none", 35), [])

    check("bad type is reported", any(
        "must read 'type(scope)" in problem
        for problem in message_problems("Add stuff (#35)", "Why: x\nBatch: none", 35)
    ), True)
    check("missing Why is reported", message_problems("feat(app): x (#35)", "Batch: none", 35),
          ["the body has no 'Why:' line"])
    check("empty Why is reported", message_problems("feat(app): x (#35)", "Why:\nBatch: none", 35),
          ["the 'Why:' line is empty"])
    check("Batch must be B<n> or none", message_problems("feat(app): x (#35)", "Why: y\nBatch: 9", 35),
          ["'Batch:' must read 'B<number>', 'B<number><letter>' or 'none', "
           "optionally followed by a parenthetical note; got '9'"])
    check("a parenthetical after the batch id is accepted",
          message_problems("feat(app): x (#35)", "Why: y\nBatch: B12 (budget accepted)", 35), [])
    check("a split batch id keeps its parenthetical",
          message_problems("feat(app): x (#35)", "Why: y\nBatch: B5a (merged early)", 35), [])
    check("an unparenthesized trailing word is reported", any(
        "parenthetical note" in problem
        for problem in message_problems("feat(app): x (#35)", "Why: y\nBatch: B12 over budget", 35)
    ), True)
    check("a wrong pull request number is reported", any(
        "(#34)" in problem
        for problem in message_problems("feat(app): x (#35)", "Why: y\nBatch: none", 34)
    ), True)
    check("a good message has no problems",
          message_problems("feat(app): x (#35)", "Why: y\nBatch: none", 35), [])
    check("a merged commit without a number is reported", any(
        "(#<number>)" in problem
        for problem in message_problems(
            "feat(app): x", "Why: y\nBatch: none", merged=True
        )
    ), True)
    check("a merged commit with a number is fine",
          message_problems("feat(app): x (#35)", "Why: y\nBatch: none", merged=True), [])
    check("a branch commit needs no number",
          message_problems("feat(app): x", "Why: y\nBatch: none"), [])

    singular = build_message(7, [{"message": "fix(infra): read .enabled\n\nWhy: drift\nBatch: none"}])
    check("a pull request number is appended once", singular.splitlines()[0], "fix(infra): read .enabled (#7)")
    already = build_message(
        37,
        [{"messageHeadline": "feat(app): a", "messageBody": ""},
         {"messageHeadline": "chore(infra): b", "messageBody": ""}],
        subject="fix(infra): catch a merged subject without its number (#37)",
        why="r",
        batch="none",
    )
    check("a subject that already carries the number keeps one",
          already.splitlines()[0], "fix(infra): catch a merged subject without its number (#37)")
    check("another pull request's number is not mistaken for this one",
          build_message(37, [{"messageHeadline": "feat(app): a", "messageBody": ""},
                             {"messageHeadline": "chore(infra): b", "messageBody": ""}],
                        subject="fix(infra): x (#36)", why="r",
                        batch="none").splitlines()[0],
          "fix(infra): x (#36) (#37)")

    payload = commits_from_payload(
        [
            {"messageHeadline": "feat(app): a", "messageBody": "Why: a\nBatch: B9"},
            {"messageHeadline": "chore(infra): b", "messageBody": ""},
        ]
    )
    check("gh headlines become messages", payload[0]["message"], "feat(app): a\n\nWhy: a\nBatch: B9")
    check("an empty gh body leaves the headline", payload[1]["message"], "chore(infra): b")
    check("the adapter feeds build_message",
          build_message(1, payload, subject="feat(app): both", why="r", batch="B9").splitlines()[0],
          "feat(app): both (#1)")

    cut = [{"messageHeadline": "docs(repo): move onto the single language block and the English pull …",
            "messageBody": "…request\n\nWhy: w\nBatch: B26"}]
    repaired = repair_cut_headline(
        cut, "docs(repo): move onto the single language block and the English pull request\n\nWhy: w\nBatch: B26"
    )
    check("a cut headline is replaced by the local commit",
          commits_from_payload(repaired)[0]["message"],
          "docs(repo): move onto the single language block and the English pull request\n\nWhy: w\nBatch: B26")
    check("a headline that is not cut is left alone", repair_cut_headline(payload, "anything"), payload)
    try:
        repair_cut_headline(cut, "chore(infra): unrelated")
        check("a cut headline with no matching local commit is refused", "no error", "error")
    except MessageError:
        check("a cut headline with no matching local commit is refused", "error", "error")

    rich = "Why: the engine reads `data/cards.json` and **never** shuffles.\nBatch: B42"
    flat = plain_body(rich)
    check("plain body drops backticks", "`" in flat, False)
    check("plain body drops bold markers", "**" in flat, False)
    check("plain body keeps the words", "data/cards.json" in flat and "never" in flat, True)
    check("plain body keeps the rule lines",
          flat.startswith("Why: the engine reads data/cards.json"), True)

    wide = "Why: " + "word " * 40 + "\nBatch: none"
    wrapped = plain_body(wide)
    check("plain body wraps a long paragraph",
          max(len(line) for line in wrapped.splitlines()) <= BODY_WIDTH, True)

    fenced = "Why: see below\n\n```\nlet a = `template`;\n```\n\nBatch: none"
    check("a fenced block is left alone", "`template`" in plain_body(fenced), True)

    check("backticks are reported",
          any("backticks" in problem for problem in
              message_problems("feat(app): x (#1)", "Why: `code`\nBatch: B42", 1)), True)
    check("bold markers are reported",
          any("bold" in problem for problem in
              message_problems("feat(app): x (#1)", "Why: **loud**\nBatch: B42", 1)), True)
    check("a long line is reported",
          any("characters" in problem for problem in
              message_problems("feat(app): x (#1)", "Why: " + "word " * 40 + "\nBatch: B42", 1)), True)
    check("a plain body passes",
          message_problems("feat(app): x (#1)", plain_body(rich), 1), [])

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


def _show(
    pr_number: int,
    why: str | None,
    batch: str | None,
    note: str | None,
    subject: str | None,
) -> int:
    commits = _gh_commits(pr_number)
    try:
        message = build_message(
            pr_number, commits, why=why, batch=batch, note=note, subject=subject
        )
    except MessageError as exc:
        print(f"cannot build a message: {exc}", file=sys.stderr)
        return 1
    print(f"--- message for #{pr_number} ({len(commits)} commit(s)) ---")
    print(message, end="")
    return 0


def _show_body(
    pr_number: int,
    why: str | None,
    batch: str | None,
    note: str | None,
    subject: str | None,
    out: str | None = None,
) -> int:
    """Print only the body, for `gh pr merge --body-file`.

    A merge takes the subject through `--subject` and the body through
    `--body-file`; handing it the whole message puts the subject into the body as
    well, which is what happened to #38 to #45. `--out` writes the file here
    instead of through a shell pipe, which decodes UTF-8 as the local code page and
    is how `#46` lost its em dash.
    """
    commits = _gh_commits(pr_number)
    try:
        message = build_message(
            pr_number, commits, why=why, batch=batch, note=note, subject=subject
        )
    except MessageError as exc:
        print(f"cannot build a message: {exc}", file=sys.stderr)
        return 1
    _, body = split_message(message)
    body = plain_body(body)
    text = body if body.endswith("\n") else body + "\n"
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"wrote {len(text)} characters to {out}")
        return 0
    print(text, end="")
    return 0


def _on_default_branch(ref: str) -> bool:
    """Say whether the commit is already an ancestor of the default branch."""
    for base in ("origin/main", "main"):
        done = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ref, base],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if done.returncode == 0:
            return True
    return False


def _verify(ref: str) -> int:
    subject, body = read_commit(ref)
    problems = message_problems(subject, body, merged=_on_default_branch(ref))
    print(f"commit: {subject}")
    if not problems:
        print("message: ok")
        return 0
    for problem in problems:
        print(f"problem: {problem}")
    print(f"body was:\n{body}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and check the message a squash merge leaves behind."
    )
    parser.add_argument("--self-test", action="store_true", help="run the message rules")
    parser.add_argument("--show", action="store_true", help="print the message for a pull request")
    parser.add_argument(
        "--body-only",
        action="store_true",
        help="print just the body, for `gh pr merge --body-file`",
    )
    parser.add_argument(
        "--out",
        help="write the body here instead of printing it; avoids a shell pipe",
    )
    parser.add_argument("--pr", type=int, help="pull request number, with --show or --body-only")
    parser.add_argument("--verify-only", action="store_true", help="check a merged commit")
    parser.add_argument("--ref", default="origin/main", help="commit to check, default origin/main")
    parser.add_argument("--why", help="one line saying what the pull request solves")
    parser.add_argument("--batch", help="B<number> when a batch card drove it, none otherwise")
    parser.add_argument("--note", help="an extra paragraph, usually 'Also changed'")
    parser.add_argument("--subject", help="subject for a multi-commit pull request")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.verify_only:
        return _verify(args.ref)
    if args.show:
        if args.pr is None:
            print("--show needs --pr", file=sys.stderr)
            return 2
        return _show(args.pr, args.why, args.batch, args.note, args.subject)
    if args.body_only:
        if args.pr is None:
            print("--body-only needs --pr", file=sys.stderr)
            return 2
        return _show_body(args.pr, args.why, args.batch, args.note, args.subject, args.out)

    print(
        "nothing to do: pass --self-test, --show --pr <n>, --body-only --pr <n>, or --verify-only",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
