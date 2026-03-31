"""HTML dashboard for pipeline monitoring."""

from __future__ import annotations

import html
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import (
    AuditEvent,
    CanonicalDirective,
    Pack,
    RawDirective,
    Source,
    SourceSnapshot,
    Verdict,
)

router = APIRouter(tags=["dashboard"])

_DASHBOARD_CSS = """
:root {
    --bg: #0a0a0a;
    --fg: #e0e0e0;
    --accent: #6c9bff;
    --accent2: #a78bfa;
    --card-bg: #141414;
    --border: #2a2a2a;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.6;
}
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
header { padding: 32px 0 24px; text-align: center; }
h1 {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}
.subtitle { color: #888; font-size: 1rem; }
.section { margin: 32px 0; }
.section h2 { font-size: 1.25rem; margin-bottom: 16px; color: var(--fg); }
.dim-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
}
.dim-item {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}
.dim-item .count { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
.dim-item .label { font-size: 0.85rem; color: #888; }
table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--accent); font-size: 0.85rem; }
tr:last-child td { border-bottom: none; }
.muted { color: #888; font-size: 0.85rem; }
code { background: #1a1a2e; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
footer { text-align: center; padding: 32px 0; color: #555; font-size: 0.85rem; border-top: 1px solid var(--border); margin-top: 48px; }
"""


def _counts(db: Session) -> dict[str, int]:
    return {
        "sources": db.scalar(select(func.count()).select_from(Source)) or 0,
        "snapshots": db.scalar(select(func.count()).select_from(SourceSnapshot)) or 0,
        "raw": db.scalar(select(func.count()).select_from(RawDirective)) or 0,
        "canonical": db.scalar(select(func.count()).select_from(CanonicalDirective)) or 0,
        "verdicts": db.scalar(select(func.count()).select_from(Verdict)) or 0,
        "packs": db.scalar(select(func.count()).select_from(Pack)) or 0,
    }


def _render_dashboard_html(db: Session) -> str:
    c = _counts(db)
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(25)).all()
    packs = db.scalars(select(Pack).order_by(Pack.pack_key)).all()

    stat_rows = [
        ("Sources", c["sources"]),
        ("Snapshots", c["snapshots"]),
        ("Raw directives", c["raw"]),
        ("Canonical directives", c["canonical"]),
        ("Verdicts", c["verdicts"]),
        ("Packs", c["packs"]),
    ]
    stats_html = "".join(
        f'<div class="dim-item"><div class="count">{n}</div><div class="label">{html.escape(label)}</div></div>'
        for label, n in stat_rows
    )

    pack_rows = []
    for p in packs:
        pack_rows.append(
            "<tr>"
            f"<td><code>{html.escape(p.pack_key)}</code></td>"
            f"<td>{html.escape(p.pack_name)}</td>"
            f"<td>{html.escape(p.status)}</td>"
            f"<td>{html.escape(p.pack_type)}</td>"
            "</tr>"
        )
    packs_table = (
        "<table><thead><tr><th>Key</th><th>Name</th><th>Status</th><th>Type</th></tr></thead><tbody>"
        + ("".join(pack_rows) if pack_rows else '<tr><td colspan="4" class="muted">No packs</td></tr>')
        + "</tbody></table>"
    )

    event_rows = []
    for ev in events:
        ts = ev.created_at
        ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        payload_preview = html.escape(str(ev.payload)[:120] + ("…" if len(str(ev.payload)) > 120 else ""))
        event_rows.append(
            "<tr>"
            f"<td class='muted'>{html.escape(ts_str)}</td>"
            f"<td><code>{html.escape(ev.action)}</code></td>"
            f"<td>{html.escape(ev.object_kind)}</td>"
            f"<td class='muted'>{payload_preview}</td>"
            "</tr>"
        )
    events_table = (
        "<table><thead><tr><th>When</th><th>Action</th><th>Object</th><th>Payload (preview)</th></tr></thead><tbody>"
        + ("".join(event_rows) if event_rows else '<tr><td colspan="4" class="muted">No audit events</td></tr>')
        + "</tbody></table>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DKB Runtime — Dashboard</title>
    <style>{_DASHBOARD_CSS}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>DKB Runtime</h1>
            <p class="subtitle">Pipeline status, packs, and recent audit activity</p>
        </header>

        <section class="section">
            <h2>Pipeline status</h2>
            <div class="dim-grid">{stats_html}</div>
        </section>

        <section class="section">
            <h2>Pack status</h2>
            {packs_table}
        </section>

        <section class="section">
            <h2>Recent audit events</h2>
            {events_table}
        </section>

        <footer>
            <a href="/docs">API docs</a>
            ·
            <a href="/api/v1/healthz">Health</a>
        </footer>
    </div>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(db: DbSession) -> HTMLResponse:
    """Serve a minimal HTML dashboard backed by the live database session."""
    body = _render_dashboard_html(db)
    return HTMLResponse(content=body)
