"""The fleet manager's one screen: who is on the road tonight, who is sleepy, what Hoshiyar did about it.

Plain HTML built from data/calls.jsonl and data/drivers.json, refreshed by the browser every 20 s.
No JavaScript, no template engine: the page is small enough to be a string. The sleepiness meters and
the reply-delay sparklines are inline SVG drawn here. Colour never carries meaning alone: every status
ships with a glyph and a label, and every number on a mark is also in the call log table.
"""

from datetime import datetime, timedelta
from html import escape

from hoshiyar import records, scheduler, trials, langs

REFRESH_SECONDS = 20
NIGHT_HOURS = 24  # "tonight" = calls in the last 24 h
CALL_LOG_ROWS = 30

# Status of a driver from his latest call: label, severity token, glyph. Worst first.
STATUS = {
    "UNRESPONSIVE": ("Unresponsive", "critical", "!"),
    "MISSED": ("Did not answer", "serious", "?"),  # busy or no-answer after every redial
    "BREAK": ("On break", "warning", "&#9749;"),  # a finished wake-up call clears this
    "HEAVY": ("Sleepy", "serious", "z"),
    "TIRED": ("Tired", "warning", "~"),
    "FRESH": ("Fresh", "good", "&#10003;"),
    "OK": ("OK", "good", "&#10003;"),
    "NONE": ("Not called yet", "muted", "&middot;"),
}
ALERT_KIND = {  # severity token, what the manager reads
    "HEAVY": ("serious", "Very sleepy"),
    "UNRESPONSIVE": ("critical", "Not answering"),
    "BREAK": ("warning", "Break agreed"),
}


def status_of(call: dict | None) -> tuple[str, str, str]:
    if call is None:
        return STATUS["NONE"]
    if call.get("status", "completed") not in ("completed", "timeout"):
        return STATUS["MISSED"]
    if call["unresponsive"]:
        return STATUS["UNRESPONSIVE"]
    if call["break_taken"] and call["kind"] == "checkin":
        return STATUS["BREAK"]
    if call["mode"] == "HEAVY":
        return STATUS["HEAVY"]
    if call["mode"] == "QUIET":
        return STATUS["FRESH"]
    if call["scores"] and call["scores"][-1][1] >= 5:
        return STATUS["TIRED"]
    return STATUS["OK"]


def severity_of(score: int) -> str:
    """1-3 fresh, 4-6 tiring, 7-8 sleepy, 9 eyes closing: the same bands the brain uses for its modes."""
    return "good" if score <= 3 else "warning" if score <= 6 else "serious" if score <= 8 else "critical"


def meter(score: int | None) -> str:
    """Nine segments, 2 px surface gaps, the filled part in the severity colour, the rest a faint track of it."""
    sev = severity_of(score) if score else "muted"
    cells = "".join(
        f"<i class='{sev}{' on' if score and i <= score else ''}{' end' if score and i == score else ''}'></i>"
        for i in range(1, 10)
    )
    label = f"{score}<small>/9</small>" if score else "<small>no score</small>"
    return f"<div class='meter'>{cells}</div><div class='meterval'>{label}</div>"


def sparkline(delays: list[list[float]]) -> str:
    """Reply delays over one call: 2 px line, 8 px end dot with a surface ring, a native tooltip per point."""
    if len(delays) < 2:
        return "<div class='spark empty'>not enough turns</div>"
    w, h, pad = 120, 36, 6
    ys = [d for _, d in delays]
    top = max(max(ys), 1.0)
    pts = [(pad + i * (w - 2 * pad) / (len(ys) - 1), h - pad - (y / top) * (h - 2 * pad)) for i, y in enumerate(ys)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    hits = "".join(
        f"<circle class='hit' cx='{x:.1f}' cy='{y:.1f}' r='10'><title>{t:.0f} s into the call: {d:.1f} s to answer</title></circle>"
        for (x, y), (t, d) in zip(pts, delays)
    )
    ex, ey = pts[-1]
    first, last = ys[0], ys[-1]
    arrow = ("&uarr;", "serious") if last > first + 1.0 else ("&darr;", "good") if last < first - 1.0 else ("&rarr;", "muted")
    return (
        f"<svg class='spark' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img' aria-label='reply delay {first:.1f} to {last:.1f} seconds'>"
        f"<polyline points='{path}'/><circle class='end' cx='{ex:.1f}' cy='{ey:.1f}' r='4'/>{hits}</svg>"
        f"<div class='sparkval'><b>{last:.1f} s</b> <span class='{arrow[1]}'>{arrow[0]}</span> <small>from {first:.1f} s</small></div>"
    )


def next_checkin(checkins: list[str], now: datetime) -> str:
    times = sorted(checkins)
    if not times:
        return "&ndash;"
    return next((t for t in times if t > f"{now:%H:%M}"), times[0])


def render(now: datetime | None = None, try_id: str | None = None, done_id: str | None = None, error: str | None = None) -> str:
    """The live page. ?try=<id>, ?done=<id> or ?err=<text> open the Try dialog in that state on load."""
    now = now or datetime.now()
    since = f"{now - timedelta(hours=NIGHT_HOURS):%Y-%m-%d %H:%M:%S}"
    calls = [c for c in records.load() if c["started_at"] >= since]
    latest: dict[str, dict] = {}
    for c in calls:
        latest[c["driver"]] = c
    roster = scheduler.load_roster() + trials.drivers()
    by_name = {d["name"]: d for d in roster}
    names = list(by_name) + [n for n in latest if n not in by_name]

    cards = []
    for name in names:
        d = by_name.get(name, {"route": "", "checkins": []})
        c = latest.get(name)
        label, sev, glyph = status_of(c)
        score = c["scores"][-1][1] if c and c["scores"] else None
        cards.append(
            f"<article class='card {sev}'>"
            f"<header><div><h3>{escape(name)}{' <small class=tag>trial</small>' if d.get('trial') else ''}</h3>"
            f"<div class='route'>{escape(d['route']) or '&nbsp;'}{_lang_tag(d, c)}</div></div>"
            f"<span class='pill {sev}'><i>{glyph}</i>{label}</span></header>"
            f"<div class='row'><div class='stat'><label>Sleepiness</label>{meter(score)}</div>"
            f"<div class='stat'><label>Reply delay</label>{sparkline(c['reply_delays'] if c else [])}</div></div>"
            f"<footer><span>Last call <b>{c['started_at'][11:16] if c else '&ndash;'}</b></span>"
            f"<span>Next <b>{next_checkin(d['checkins'], now)}</b></span>"
            f"<span>Alerts <b>{len(c['alerts']) if c else 0}</b></span></footer></article>"
        )
    if not cards:
        cards.append("<div class='empty'>No drivers on the roster yet. Add them to data/drivers.json.</div>")

    alerts = sorted(((c["started_at"], t, c["driver"], text) for c in calls for t, text in c["alerts"]), reverse=True)
    alert_items = []
    for started, t, driver, text in alerts:
        kind, _, body = text.partition("] ")
        kind = kind.strip("[")
        sev, what = ALERT_KIND.get(kind, ("muted", kind.title()))
        alert_items.append(
            f"<li class='{sev}'><time>{_clock(started, t)}</time>"
            f"<div><b>{escape(driver)}</b> <span class='kind'>{what}</span><p>{escape(body)}</p></div></li>"
        )
    alerts_html = f"<ul class='feed'>{''.join(alert_items)}</ul>" if alert_items else "<div class='empty'>No alerts tonight. Good.</div>"

    log_rows = [
        f"<tr><td>{c['started_at'][5:16]}</td><td><b>{escape(c['driver'])}</b></td>"
        f"<td>{c['kind']}{'' if c.get('lang', 'hi') in ('auto', 'hi') else ' &middot; ' + c['lang']}</td>"
        f"<td class='num'>{c['duration']:.0f} s</td><td class='num'>{', '.join(str(s) for _, s in c['scores'])}</td>"
        f"<td>{_mode_text(c)}</td>"
        f"<td class='num' title='{_all_delays(c)}'>{_trend_text(c)}</td>"
        f"<td class='num'>{len(c['alerts'])}</td></tr>"
        for c in reversed(calls[-CALL_LOG_ROWS:])
    ]
    log_html = (
        "<div class='scroll'><table><thead><tr><th>When</th><th>Driver</th><th>Kind</th><th class='num'>Length</th>"
        "<th class='num'>Scores</th><th>Mode</th><th class='num'>Reply delay</th><th class='num'>Alerts</th></tr></thead>"
        f"<tbody>{''.join(log_rows)}</tbody></table></div>"
        if log_rows else "<div class='empty'>No calls yet tonight.</div>"
    )

    attention = sum(1 for n in names if status_of(latest.get(n))[1] in ("critical", "serious"))
    opened = bool(error) or (try_id and trials.get(try_id)) or (done_id and trials.get(done_id))
    done = bool(done_id and trials.get(done_id) and trials.get(done_id)["verified"])
    return PAGE.format(
        css=CSS,
        refresh=REFRESH_SECONDS,
        dialog=try_block(now, try_id, done_id, error),
        open_attr=" open" if opened else "",
        done_js="true" if done else "false",
        now=f"{now:%A %d %b, %H:%M}",
        n_drivers=len(roster),
        n_calls=len(calls),
        n_alerts=len(alerts),
        attention=attention,
        attention_sev="critical" if attention else "good",
        cards="".join(cards),
        alerts=alerts_html,
        log=log_html,
    )


def try_block(now: datetime, try_id: str | None, done_id: str | None, error: str | None) -> str:
    err = f"<p class='err'>{escape(error)}</p>" if error else ""
    entry = trials.get(try_id) if try_id else None
    if entry and not entry["verified"]:
        return (
            "<h2>Try Hoshiyar</h2><section class='try'>"
            f"<p>Calling <b>{trials.masked(entry['phone'])}</b> now. Type the four digits you hear.</p>{err}"
            f"<form method='post' action='/verify' class='row2'><input type='hidden' name='id' value='{entry['id']}'>"
            "<input name='code' inputmode='numeric' pattern='[0-9]{4}' maxlength='4' placeholder='0000' autofocus required>"
            "<button>Verify</button></form>"
            f"<form method='post' action='/try/{entry['id']}/again' class='again'><button class='link'>Did not get the call? Call again</button></form>"
            "</section>"
        )
    done = trials.get(done_id) if done_id else None
    if done and done["verified"]:
        return (
            "<h2>Try Hoshiyar</h2><section class='try good'>"
            f"<p><b>Scheduled.</b> Hoshiyar will call {escape(done['name'])} at <b>{done['at']}</b>.</p>"
            "<p class='hint'>The call will appear on this page as it happens.</p></section>"
        )
    soon = f"{now + timedelta(minutes=2):%H:%M}"
    return (
        "<h2>Try Hoshiyar</h2><section class='try'>"
        f"{err}<form method='post' action='/try' class='row3'>"
        "<input name='name' placeholder='Your name' maxlength='40' required>"
        "<span class='phone'><i>+91</i><input name='phone' inputmode='numeric' placeholder='98765 43210' maxlength='13' required></span>"
        f"<input name='at' type='time' value='{soon}' required>"
        "<select name='lang'><option value='auto'>Hindi, or let me choose</option><option value='hi'>Hindi</option>"
        "<option value='te'>Telugu</option><option value='kn'>Kannada</option><option value='mr'>Marathi</option>"
        "<option value='en'>English</option></select>"
        "<button>Call me with a code</button></form>"
        "<p class='hint'>We ring this number, read a 4-digit code, and schedule the check-in call once you type it. "
        "Only you can book your number. Default time is two minutes from now; pick any time tonight.</p>"
        "</section>"
    )


def _lang_tag(d: dict, c: dict | None) -> str:
    """The call's language if it ended in one other than Hindi, else the roster's fixed language if any."""
    lang = (c or {}).get("lang") or d.get("lang", "auto")
    if lang in ("auto", "hi"):
        return ""
    return f" &middot; {langs.name(lang)}"


def _mode_text(c: dict) -> str:
    status = c.get("status", "completed")
    if status in ("completed", "timeout"):
        return c["mode"].title()
    return f"{escape(status)} &times;{c.get('attempts', 1)}"


def _trend_text(c: dict) -> str:
    d = c["reply_delays"]
    return f"{d[0][1]:.1f} &rarr; {d[-1][1]:.1f} s" if len(d) > 1 else ""


def _all_delays(c: dict) -> str:
    return ", ".join(f"{d:.1f}" for _, d in c["reply_delays"])


def _clock(started_at: str, seconds_into_call: float) -> str:
    t = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=seconds_into_call)
    return f"{t:%H:%M}"


CSS = """
:root{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--surface-2:#222221;--ink:#f0efec;--ink-2:#c3c2b7;--muted:#898781;
 --hair:#2c2c2a;--ring:rgba(255,255,255,.10);--series:#3987e5;
 --good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b}
@media (prefers-color-scheme:light){:root{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--surface-2:#f0efec;--ink:#0b0b0b;--ink-2:#52514e;
 --hair:#e1e0d9;--ring:rgba(11,11,11,.10);--series:#2a78d6}}
*{box-sizing:border-box}
body{margin:0;padding:20px 16px 48px;background:var(--plane);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1100px;margin:0 auto}
.brand{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.brand .dev{font-size:34px;font-weight:700;letter-spacing:.01em} .brand .lat{font-size:14px;color:var(--ink-2);letter-spacing:.14em;text-transform:uppercase}
.sub{color:var(--muted);margin-top:2px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.live{display:inline-flex;align-items:center;gap:6px;color:var(--ink-2)} .live i{width:8px;height:8px;border-radius:50%;background:var(--good);animation:pulse 2s infinite}
@keyframes pulse{50%{opacity:.35}} @media (prefers-reduced-motion:reduce){.live i{animation:none}}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:22px 0 28px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:12px 16px 14px}
.tile label{display:block;color:var(--muted);font-size:13px} .tile b{display:block;font-size:30px;font-weight:600;line-height:1.15;margin-top:2px}
.tile.hero b{font-size:52px} .tile.hero{grid-column:span 2} .tile.hero.critical b{color:var(--critical)} .tile.hero.good b{color:var(--good)}
h2{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;margin:28px 0 10px;font-weight:600}
.drivers{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--muted);border-radius:12px;padding:14px 16px 12px;display:flex;flex-direction:column;gap:12px}
.card.good{border-left-color:var(--good)} .card.warning{border-left-color:var(--warning)} .card.serious{border-left-color:var(--serious)} .card.critical{border-left-color:var(--critical)}
.card header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px} .card h3{margin:0;font-size:18px;font-weight:600}
.route{color:var(--muted);font-size:13px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px 3px 6px;border-radius:999px;font-size:13px;font-weight:600;background:var(--surface-2);color:var(--ink);white-space:nowrap}
.pill i{width:18px;height:18px;border-radius:50%;display:inline-grid;place-items:center;font-style:normal;font-size:12px;color:#fff;background:var(--muted)}
.pill.good i{background:var(--good)} .pill.warning i{background:var(--warning);color:#1a1a19} .pill.serious i{background:var(--serious);color:#1a1a19} .pill.critical i{background:var(--critical)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px} .stat label{display:block;color:var(--muted);font-size:12px;margin-bottom:6px}
.meter{display:flex;gap:2px;height:8px} .meter i{flex:1;border-radius:0;opacity:.18} .meter i.on{opacity:1} .meter i.end{border-radius:0 4px 4px 0}
.meter i.good{background:var(--good)} .meter i.warning{background:var(--warning)} .meter i.serious{background:var(--serious)} .meter i.critical{background:var(--critical)} .meter i.muted{background:var(--muted)}
.meterval{margin-top:6px;font-size:22px;font-weight:600;line-height:1} .meterval small,.sparkval small{color:var(--muted);font-size:12px;font-weight:400}
.spark{display:block;overflow:visible} .spark polyline{fill:none;stroke:var(--series);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.spark .end{fill:var(--series);stroke:var(--surface);stroke-width:2} .spark .hit{fill:transparent} .spark.empty{color:var(--muted);font-size:12px;height:36px;display:flex;align-items:center}
.sparkval{margin-top:2px;font-size:14px} .sparkval b{font-weight:600} .sparkval .serious{color:var(--serious)} .sparkval .good{color:var(--good)} .sparkval .muted{color:var(--muted)}
.card footer{display:flex;gap:16px;color:var(--muted);font-size:13px;border-top:1px solid var(--hair);padding-top:10px} .card footer b{color:var(--ink-2);font-weight:600}
.feed{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.feed li{display:flex;gap:14px;background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--muted);border-radius:10px;padding:10px 14px}
.feed li.serious{border-left-color:var(--serious)} .feed li.critical{border-left-color:var(--critical)} .feed li.warning{border-left-color:var(--warning)}
.feed time{color:var(--muted);font-variant-numeric:tabular-nums;min-width:44px;padding-top:1px} .feed .kind{color:var(--muted);font-size:13px;margin-left:6px} .feed p{margin:2px 0 0;color:var(--ink-2)}
.scroll{overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:12px}
table{width:100%;border-collapse:collapse;min-width:640px} th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--hair);white-space:nowrap}
th{color:var(--muted);font-weight:500;font-size:13px} tbody tr:last-child td{border-bottom:0} .num{text-align:right;font-variant-numeric:tabular-nums}
.empty{background:var(--surface);border:1px dashed var(--ring);border-radius:12px;padding:18px;color:var(--muted);text-align:center}
.try{background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--series);border-radius:12px;padding:14px 16px} .try.good{border-left-color:var(--good)}
.try p{margin:0 0 10px} .try .hint{margin:10px 0 0;color:var(--muted);font-size:13px} .try .err{color:var(--critical);font-weight:600}
.try form{display:flex;gap:10px;flex-wrap:wrap;align-items:stretch} .try input,.try button{font:inherit;border-radius:8px;padding:9px 12px;border:1px solid var(--ring);background:var(--plane);color:var(--ink)}
.try input{min-width:150px;flex:1} .try .phone{display:flex;flex:1;min-width:190px} .try .phone i{font-style:normal;color:var(--muted);padding:9px 0 9px 12px;background:var(--plane);border:1px solid var(--ring);border-right:0;border-radius:8px 0 0 8px}
.try .phone input{border-radius:0 8px 8px 0;border-left:0;min-width:0} .try input[type=time]{flex:0 0 auto;min-width:0} .try select{font:inherit;border-radius:8px;padding:9px 12px;border:1px solid var(--ring);background:var(--plane);color:var(--ink)}
.try button{background:var(--ink);color:var(--plane);font-weight:600;border:0;cursor:pointer} .try .row2 input{flex:0 0 120px;font-size:22px;letter-spacing:.3em;text-align:center}
.try .again{margin-top:8px} .try .link{background:none;color:var(--muted);font-weight:400;padding:0;text-decoration:underline}
.card h3 .tag{font-size:11px;font-weight:600;color:var(--series);text-transform:uppercase;letter-spacing:.08em;margin-left:6px;vertical-align:middle}
@media (max-width:480px){.tile.hero{grid-column:span 2} .row{grid-template-columns:1fr} .brand .dev{font-size:28px}}

.trycta{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--series);border-radius:12px;padding:16px 18px;margin:-6px 0 0}
.trycta h3{margin:0 0 4px;font-size:18px;font-weight:600} .trycta p{margin:0;color:var(--ink-2);font-size:14px;max-width:640px}
.trycta button{font:inherit;font-weight:600;font-size:16px;background:var(--ink);color:var(--plane);border:0;border-radius:10px;padding:12px 22px;cursor:pointer;white-space:nowrap}
dialog#try{background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:14px;padding:18px 20px 16px;width:min(680px,calc(100% - 32px));box-sizing:border-box}
dialog#try::backdrop{background:rgba(0,0,0,.65)} dialog#try h2{margin-top:0} dialog#try .try{border:0;padding:0;background:none}
dialog#try .close{margin-top:14px;display:flex;justify-content:flex-end} dialog#try .close button{font:inherit;background:none;border:1px solid var(--ring);color:var(--ink-2);border-radius:8px;padding:6px 12px;cursor:pointer}
.try .hint a{color:var(--ink-2)}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hoshiyar fleet</title>
<style>{css}</style></head><body><div class="wrap">
<div class="brand"><span class="dev">&#2361;&#2379;&#2358;&#2367;&#2351;&#2366;&#2352;</span><span class="lat">Hoshiyar &middot; fleet tonight</span></div>
<div class="sub"><span class="live"><i></i>live</span><span>{now}</span><span>&middot;</span><span>refreshes every {refresh} s</span></div>
<div class="tiles">
 <div class="tile hero {attention_sev}"><label>Need attention now</label><b>{attention}</b></div>
 <div class="tile"><label>Drivers on roster</label><b>{n_drivers}</b></div>
 <div class="tile"><label>Calls tonight</label><b>{n_calls}</b></div>
 <div class="tile"><label>Alerts tonight</label><b>{n_alerts}</b></div>
</div>
<section class="trycta"><div><h3>Try Hoshiyar on your own phone</h3>
<p>Book a check-in call for tonight. We ring you, read a four-digit code, you type it, and the call is yours to hear. Only you can book your number.</p></div>
<button type="button" onclick="document.getElementById('try').showModal()">Try it now</button></section>
<dialog id="try"{open_attr}>{dialog}<form method="dialog" class="close"><button>Close</button></form></dialog>
<script>
(function(){{var d=document.getElementById('try');
if(d.open){{d.close();d.showModal();}}
if(location.search&&!/[?&]try=/.test(location.search))history.replaceState(null,'','/fleet');
if({done_js}){{setTimeout(function(){{d.close();location.replace('/fleet');}},8000);}}
setInterval(function(){{if(!d.open)location.replace('/fleet');}},{refresh}*1000);}})();
</script>
<h2>Drivers</h2><div class="drivers">{cards}</div>
<h2>Alerts</h2>{alerts}
<h2>Call log</h2>{log}
</div></body></html>"""


