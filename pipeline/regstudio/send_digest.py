"""Email an approved, published weekly digest to confirmed subscribers via a Resend broadcast.

Needs RESEND_API_KEY, RESEND_SEGMENT_ID, RESEND_FROM and REGSTUDIO_SITE_URL in the environment.
By default it creates the broadcast as a draft in Resend; pass send=True to send it now.
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request

from . import config


class DigestError(RuntimeError):
    pass


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise DigestError(f"{name} is not set")
    return v


def build_html(digest: dict, orders: dict, site: str) -> str:
    esc = html.escape
    items = []
    for oid in digest["items"]:
        o = orders.get(oid)
        if not o or o.get("sample"):
            continue
        title = (o.get("impact") or {}).get("headline") or o.get("headline") or o.get("title") or o.get("case_number") or "Order"
        items.append(
            f'<tr><td style="padding:14px 0;border-bottom:1px solid #e3e6eb">'
            f'<div style="font-size:12px;color:#5a6474;font-weight:600">{esc(o["commission"].upper())}'
            f'{" · " + esc(o["date"]) if o.get("date") else ""}</div>'
            f'<div style="font-size:17px;margin:4px 0"><a href="{site}{o["path"]}" style="color:#0f5c8c">{esc(title)}</a></div>'
            f'<div style="font-size:15px;line-height:1.55;color:#17202e">{esc(o["summary"])}</div></td></tr>')
    if not items:
        raise DigestError("digest has no publishable items")
    extra = ""
    if digest.get("key_points"):
        extra += ('<tr><td style="font-size:13px;color:#5a6474;font-weight:600;padding-top:14px">KEY POINTS</td></tr><tr><td><ul style="padding-left:18px;margin:6px 0">'
                  + "".join(f'<li style="font-size:15px;line-height:1.55;color:#17202e;margin:6px 0">{esc(p["text"])}</li>' for p in digest["key_points"])
                  + "</ul></td></tr>")
    if digest.get("numbers"):
        extra += ('<tr><td style="font-size:13px;color:#5a6474;font-weight:600;padding-top:10px">NUMBERS TO KNOW</td></tr><tr><td><table role="presentation" cellpadding="0" cellspacing="0" width="100%">'
                  + "".join(f'<tr><td style="padding:6px 12px 6px 0;font-size:17px;font-weight:bold;color:#17202e;white-space:nowrap;vertical-align:top">{esc(n["value"])}</td>'
                            f'<td style="padding:6px 0;font-size:14px;color:#17202e">{esc(n["label"])} <span style="color:#5a6474">({esc(n["code"].upper())})</span></td></tr>'
                            for n in digest["numbers"]) + "</table></td></tr>")
    if digest.get("watch"):
        extra += ('<tr><td style="font-size:13px;color:#5a6474;font-weight:600;padding-top:10px">DATES TO WATCH</td></tr>'
                  + "".join(f'<tr><td style="font-size:14px;color:#17202e;padding:3px 0"><b>{esc(w["date"])}</b> {esc(w["text"])}</td></tr>' for w in digest["watch"]))
    extra += '<tr><td style="font-size:13px;color:#5a6474;font-weight:600;padding-top:14px">IN THIS EDITION</td></tr>' 
    return f"""<!doctype html><html><body style="margin:0;background:#fbfaf7">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;font-family:Arial,sans-serif;padding:24px 16px">
<tr><td style="font-family:Georgia,serif;font-size:22px;font-weight:bold;color:#17202e">Regulatory Studio</td></tr>
<tr><td style="font-size:13px;color:#5a6474;padding-bottom:12px">Weekly digest, edition of {esc(digest.get("edition") or digest["to"])} · jouleWise and Urja Praxis</td></tr>
<tr><td style="font-size:16px;line-height:1.6;color:#17202e;padding-bottom:8px">{esc(digest["intro"])}</td></tr>
{extra}
{''.join(items)}
<tr><td style="font-size:12px;color:#5a6474;padding-top:16px">Summaries are reviewed by our legal team and are for information only, not legal advice.
Read every order in full on <a href="{site}{digest["path"]}" style="color:#0f5c8c">the website</a>.<br>
<a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}" style="color:#5a6474">Unsubscribe</a></td></tr>
</table></td></tr></table></body></html>"""


def run(week: str | None = None, send: bool = False) -> dict:
    snap = config.SNAPSHOT
    digests = json.loads((snap / "digests.json").read_text()) if (snap / "digests.json").exists() else []
    if not digests:
        raise DigestError("no published digest; approve one and run `regstudio publish` first")
    digest = next((d for d in digests if d["id"] == week), None) if week else digests[0]
    if not digest:
        raise DigestError(f"digest {week} is not published")
    orders = {o["id"]: o for o in json.loads((snap / "orders.json").read_text())}
    if (snap / "consultations.json").exists():
        orders |= {c["id"]: {**c, "date": c.get("comment_deadline") and f"comments by {c['comment_deadline']}"}
                   for c in json.loads((snap / "consultations.json").read_text())}
    site = _env("REGSTUDIO_SITE_URL").rstrip("/")
    body = {
        "segment_id": _env("RESEND_SEGMENT_ID"), "from": _env("RESEND_FROM"),
        "subject": f"Regulatory Studio weekly digest, {digest.get('edition') or digest['to']}",
        "name": f"Weekly digest {digest['id']}", "html": build_html(digest, orders, site), "send": bool(send),
    }
    req = urllib.request.Request("https://api.resend.com/broadcasts", data=json.dumps(body).encode(), method="POST",
                                 headers={"authorization": f"Bearer {_env('RESEND_API_KEY')}",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise DigestError(f"Resend refused the broadcast ({e.code}): {e.read()[:300]!r}") from e
    return {"digest": digest["id"], "broadcast_id": out.get("id"), "sent": bool(send),
            "note": "sent to subscribers" if send else "created as a draft in Resend; review it there, or rerun with --send"}
