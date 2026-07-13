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
    """Read the current per-country status straight from the tracker's index.html,
    so the baseline given to Claude is always in sync with the published tracker."""
    html = TRACKER_HTML.read_text(encoding="utf-8")

    lines = []

    # "Last updated" footer line
    updated = re.search(r'class="updated">(.*?)</div>', html, re.DOTALL)
    if updated:
        lines.append(_strip_tags(updated.group(1)))

    # Notice bars carry key context (deadline, infringement outlook)
    for notice in re.findall(r'class="notice-bar"[^>]*>(.*?)</div>', html, re.DOTALL):
        lines.append(f"CONTEXT: {_strip_tags(notice)}")

    # Per-country rows from the Implementation Status tab
    status_tab = html.split('id="tab-status"', 1)[1].split("end tab-status", 1)[0]
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", status_tab, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 6:
            continue  # header row or malformed
        name = _strip_tags(re.search(r'class="country-name">(.*?)</div>', cells[0], re.DOTALL).group(1))
        name = name.replace("BALTIC", "").strip()
        status = _strip_tags(cells[1])
        details = _strip_tags(cells[3])
        expected = _strip_tags(cells[4])
        lines.append(f"- {name} | Status: {status} | Expected: {expected} | Known details: {details}")

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

MAX_PAUSE_TURN_CONTINUATIONS = 5


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

    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}]
    messages = [{"role": "user", "content": user_prompt}]

    # Stream so the long server-side search doesn't hit the request timeout.
    # pause_turn means the server tool loop hit its cap — re-send to continue.
    response = None
    for _ in range(MAX_PAUSE_TURN_CONTINUATIONS):
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=messages,
            system=system_prompt,
            tools=tools,
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason != "pause_turn":
            break
        messages = [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": response.content},
        ]

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
