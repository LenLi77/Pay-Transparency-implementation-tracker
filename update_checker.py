#!/usr/bin/env python3
"""
EU Pay Transparency Directive - Daily Update Checker
Searches for news via Claude's web_search tool, summarises changes, sends email to Ellen.
"""

import os
import re
import smtplib
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import anthropic

# ── Configuration ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]        # ellen.liigus@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"] # Gmail App Password (not account password)
EMAIL_TO          = "ellen.liigus@gmail.com"

TRACKER_URL = "https://pay-transparency-implementation-tra.vercel.app/"
TRACKER_HTML = Path(__file__).with_name("index.html")


def _strip_tags(html: str) -> str:
    """Collapse an HTML fragment to plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def build_current_status() -> str:
    """Read the current status from the tracker's index.html, so the baseline
    given to Claude stays in sync with the published tracker. Country data lives
    in the COUNTRIES JS array (the single source of truth); the 'last updated'
    line and context notices are still static HTML."""
    html = TRACKER_HTML.read_text(encoding="utf-8")

    lines = []

    # "Last updated" footer line
    updated = re.search(r'class="updated">(.*?)</div>', html, re.DOTALL)
    if updated:
        lines.append(_strip_tags(updated.group(1)))

    # Notice bars carry key context (deadline, infringement outlook)
    for notice in re.findall(r'class="notice-bar"[^>]*>(.*?)</div>', html, re.DOTALL):
        lines.append(f"CONTEXT: {_strip_tags(notice)}")

    # Country rows are rendered client-side from the COUNTRIES array — parse it.
    array = re.search(r"const COUNTRIES = \[(.*?)\n    \];", html, re.DOTALL)
    if not array:
        raise RuntimeError(f"Could not find COUNTRIES array in {TRACKER_HTML}")

    # Each object closes with a 6-space-indented "}," — split on that boundary.
    for chunk in array.group(1).split("\n      },"):
        name = re.search(r"name:\s*'([^']+)'", chunk)
        status = re.search(r"status:\s*'([^']*)'", chunk)
        if not (name and status):
            continue  # trailing/empty chunk
        expected = re.search(r"expected:\s*'([^']*)'", chunk)
        details = re.search(r"details:\s*`([^`]*)`", chunk)
        detail_text = f" | Known details: {details.group(1)}" if details else ""
        lines.append(
            f"- {name.group(1)} | Status: {status.group(1)} | "
            f"Expected: {expected.group(1) if expected else '—'}{detail_text}"
        )

    country_count = sum(1 for line in lines if line.startswith("- "))
    if country_count == 0:
        raise RuntimeError(f"Could not parse any country rows from {TRACKER_HTML}")

    return "\n".join(lines)

# Topics Claude should search for (guidance, not literal queries)
SEARCH_TOPICS = """
- EU pay transparency directive transposition status (deadline was 7 June 2026)
- Estonia and Sweden refusal to transpose / EC infringement proceedings
- Germany (Lohntransparenzrichtlinie) draft law progress
- France (transparence salariale) draft law progress
- Lithuania, Finland, Cyprus, Romania, Latvia adoption progress
- Malta, Austria, Portugal, Hungary, Greece, Luxembourg, Slovenia, Croatia transposition news
"""

# Each pause_turn continuation re-sends the whole accumulated turn (incl. fetched
# web content) as fresh input, so keep this low — it is a token-cost multiplier.
MAX_PAUSE_TURN_CONTINUATIONS = 3


def get_updates_from_claude() -> str:
    """Have Claude search the web and identify meaningful updates."""
    # A server-side web_search turn can take several minutes; stream (below) to
    # keep the connection alive, and cap retries so a genuinely stuck request
    # fails fast instead of burning 3 × 10 min on timeouts.
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=900.0, max_retries=1)

    today = date.today().strftime("%d %B %Y")
    current_status = build_current_status()

    system_prompt = """You are an expert analyst tracking EU employment law.
Your task: search the web for today's news and identify ONLY genuinely new developments
for the EU Pay Transparency Directive tracker.

Use the web_search tool to find recent news. Prefer official government sources,
EC statements, and reputable law firm trackers. Search in local languages where useful.

Be concise and factual. Flag only real changes — new drafts published,
laws adopted, confirmed delays, political decisions. Ignore duplicate news
and anything already in the current status summary provided.

Format your response as a clean email section with:
1. A brief verdict (updates found / no significant updates)
2. Country-by-country bullet points for any changes, with source links
3. A recommendation: update tracker now / wait for more info"""

    user_prompt = f"""Today is {today}.

CURRENT TRACKER STATUS (parsed from the live tracker page):
{current_status}

TOPICS TO SEARCH FOR:
{SEARCH_TOPICS}

Search the web for recent news on these topics, then identify any meaningful updates
that are NOT already reflected in the current tracker status.
Focus especially on: laws adopted, new drafts published, confirmed delays, political decisions,
infringement proceedings launched by EC."""

    # max_uses kept low: each search also runs dynamic-filtering code execution,
    # and going past the server's ~10-iteration cap triggers an expensive
    # pause_turn re-send. 4 searches stays comfortably under it.
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 4}]
    # Cache the (stable) system prompt so it isn't re-billed on every continuation.
    system_blocks = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": user_prompt}]

    # Stream so the long server-side search doesn't hit the request timeout.
    # pause_turn means the server tool loop hit its cap — re-send to continue.
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "searches": 0}
    response = None
    for _ in range(MAX_PAUSE_TURN_CONTINUATIONS):
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=messages,
            system=system_blocks,
            tools=tools,
        ) as stream:
            # Print live progress so the CI log shows the run is working, not hung,
            # during the minutes the server spends searching.
            for event in stream:
                if event.type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block is not None and getattr(block, "type", "") == "server_tool_use":
                        print("  ...running a web search", flush=True)
            response = stream.get_final_message()

        u = response.usage
        totals["input"] += u.input_tokens
        totals["output"] += u.output_tokens
        totals["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        totals["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        server_use = getattr(u, "server_tool_use", None)
        if server_use:
            totals["searches"] += getattr(server_use, "web_search_requests", 0) or 0

        if response.stop_reason != "pause_turn":
            break
        messages = [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": response.content},
        ]

    print(
        f"Token usage — input {totals['input']:,} "
        f"(cache read {totals['cache_read']:,}, write {totals['cache_write']:,}), "
        f"output {totals['output']:,}, web searches {totals['searches']}"
    )

    return "\n".join(block.text for block in response.content if block.type == "text")


def send_email(subject: str, body_html: str, body_text: str):
    """Send email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

    print(f"Email sent to {EMAIL_TO}")


def build_email(analysis: str) -> tuple[str, str]:
    """Build HTML and plain text email bodies."""
    today = date.today().strftime("%d %B %Y")
    subject = f"🇪🇺 Pay Transparency Tracker — Daily Update {today}"

    html = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; color: #111;">
  <div style="background: #1e3a5f; padding: 20px; border-radius: 8px 8px 0 0;">
    <h2 style="color: white; margin: 0;">EU Pay Transparency Tracker</h2>
    <p style="color: #93c5fd; margin: 4px 0 0;">Daily Update — {today}</p>
  </div>
  <div style="background: #f8fafc; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
    <div style="white-space: pre-wrap; line-height: 1.6;">{analysis}</div>
    <hr style="margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;">
    <p style="font-size: 13px; color: #6b7280;">
      View tracker: <a href="{TRACKER_URL}">{TRACKER_URL}</a><br>
      This email is generated automatically. Reply to update the tracker manually.
    </p>
  </div>
</body></html>
"""

    plain = f"""EU Pay Transparency Tracker — Daily Update {today}

{analysis}

---
View tracker: {TRACKER_URL}
"""
    return subject, html, plain


def main():
    print("Starting EU Pay Transparency update check...")

    # 1. Search + analyse in a single Claude call (server-side web search)
    print("Searching and analysing with Claude...")
    analysis = get_updates_from_claude()
    print("Analysis complete.")
    print(analysis)

    # 2. Send email
    subject, html, plain = build_email(analysis)
    send_email(subject, html, plain)
    print("Done.")


if __name__ == "__main__":
    main()
