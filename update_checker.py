#!/usr/bin/env python3
"""
EU Pay Transparency Directive - Daily Update Checker
Searches for news, summarises changes via Claude API, sends email to Ellen.
"""

import os
import smtplib
import json
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import urllib.request
import urllib.parse

# ── Configuration ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]        # ellen.liigus@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"] # Gmail App Password (not account password)
EMAIL_TO          = "ellen.liigus@gmail.com"

TRACKER_URL = "https://pay-transparency-implementation-tra.vercel.app/"

# Countries we track and their current status (update this when tracker changes)
CURRENT_STATUS = """
LAW ADOPTED (2): Slovakia, Italy
DRAFT PUBLISHED (5): Lithuania, Finland, Cyprus, Romania, Latvia
PARTIAL / DELAYED (13): Netherlands (Jan 2027), Sweden (suspended/renegotiating),
  Denmark (Jan 2027, elections uncertainty), France (Sep 2026), Ireland (phased),
  Czechia (Jan 2027), Belgium (partial), Poland (Jan 2027), Spain (H2 2026),
  Croatia (expected), Slovenia (expected), Bulgaria (deadline missed),
  Germany (H2 2026)
NO INFO / SUSPENDED (7): Estonia (suspended), Austria, Greece, Hungary,
  Portugal, Luxembourg, Malta (partial only, employer association requested postponement)

KEY CONTEXT: June 7 2026 is the transposition deadline. EC confirmed no postponement.
Estonia and Sweden are actively refusing to transpose. Most countries will miss the deadline.
Last tracker update: 26 May 2026.
"""

# Search queries to run
SEARCH_QUERIES = [
    "EU pay transparency directive transposition June 2026",
    "EU pay transparency directive Estonia Sweden infringement proceedings",
    "EU Lohntransparenzrichtlinie Germany draft law June 2026",
    "directive transparence salariale France loi juin 2026",
    "EU pay transparency Lithuania Finland Cyprus Romania adopted law",
    "Malta Austria Portugal Hungary Greece Luxembourg pay transparency directive 2026",
]


def search_web(query: str) -> str:
    """Simple DuckDuckGo search via their API."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        results = []
        # Abstract
        if data.get("AbstractText"):
            results.append(f"[Abstract] {data['AbstractText'][:500]}")
        # Related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text'][:300]}")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


def get_updates_from_claude(search_results: str) -> str:
    """Ask Claude to analyse search results and identify meaningful updates."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = date.today().strftime("%d %B %Y")

    system_prompt = """You are an expert analyst tracking EU employment law.
Your task: review search results and identify ONLY genuinely new developments
for the EU Pay Transparency Directive tracker.

Be concise and factual. Flag only real changes — new drafts published,
laws adopted, confirmed delays, political decisions. Ignore duplicate news
and anything already in the current status summary provided.

Format your response as a clean email section with:
1. A brief verdict (updates found / no significant updates)
2. Country-by-country bullet points for any changes
3. A recommendation: update tracker now / wait for more info"""

    user_prompt = f"""Today is {today}.

CURRENT TRACKER STATUS:
{CURRENT_STATUS}

SEARCH RESULTS FROM TODAY:
{search_results}

Please identify any meaningful updates that are NOT already reflected in the current tracker status.
Focus especially on: laws adopted, new drafts published, confirmed delays, political decisions,
infringement proceedings launched by EC."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )
    return response.content[0].text


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

    # 1. Run searches
    all_results = []
    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        result = search_web(query)
        all_results.append(f"QUERY: {query}\n{result}\n")

    combined_results = "\n---\n".join(all_results)

    # 2. Analyse with Claude
    print("Analysing results with Claude...")
    analysis = get_updates_from_claude(combined_results)
    print("Analysis complete.")
    print(analysis)

    # 3. Send email
    subject, html, plain = build_email(analysis)
    send_email(subject, html, plain)
    print("Done.")


if __name__ == "__main__":
    main()
