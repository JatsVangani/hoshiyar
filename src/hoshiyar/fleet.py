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
    "MISSED": ("Did not answer", "critical", "?"),  # busy or no-answer after every redial
    "BREAK": ("On break", "info", "&#9749;"),  # a finished wake-up call clears this
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
    return f"<div class='meter'>{cells}</div><div class='meterval {sev}'>{label}</div>"


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
        f"<polyline points='{path}'/><circle class='end' cx='{ex:.1f}' cy='{ey:.1f}' r='3'/>"
        f"<g class='truck' transform='translate({ex - 7:.1f} {ey - 18:.1f}) scale(.6)'>{TRUCK_PATHS}</g>{hits}</svg>"
        f"<div class='sparkval'>{TRUCK_ICON}<b>{last:.1f} s</b> <span class='{arrow[1]}'>{arrow[0]}</span> <small>from {first:.1f} s</small></div>"
    )


TRUCK_PATHS = ("<path d='M2 6h12v11H2z'/><path d='M14 10h4l4 4v3h-8z'/><circle cx='6' cy='18' r='2'/>"
               "<circle cx='18' cy='18' r='2'/><path d='M16 10v4h6'/>")
TRUCK_ICON = (f"<svg class='ti' viewBox='0 0 24 24' width='16' height='16' fill='none' stroke='currentColor' stroke-width='1.7' "
              f"stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{TRUCK_PATHS}</svg>")
PHONE_ICON = ("<svg viewBox='0 0 24 24' width='28' height='28' fill='currentColor' aria-hidden='true'><path d='M7.1 3.5c.5-.5 1.3-.6 1.9-.2l2.2 1.5c.7.5.9 1.4.5 2.1l-1.1 1.8a1.5 1.5 0 0 0 .2 1.8l2.7 2.7a1.5 1.5 0 0 0 1.8.2l1.8-1.1c.7-.4 1.6-.2 2.1.5l1.5 2.2c.4.6.3 1.4-.2 1.9l-1.3 1.3c-.9.9-2.2 1.3-3.4 1-3.1-.8-6.1-2.8-8.6-5.3S3.1 8.4 2.3 5.3c-.3-1.2.1-2.5 1-3.4z'/></svg>")


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
            f"<div class='row'><div class='stat2'><label>Sleepiness</label>{meter(score)}</div>"
            f"<div class='stat2'><label>Reply delay</label>{sparkline(c['reply_delays'] if c else [])}</div></div>"
            f"<footer><span>Last call<b>{c['started_at'][11:16] if c else '&ndash;'}</b></span>"
            f"<span>Next<b>{next_checkin(d['checkins'], now)}</b></span>"
            f"<span>Alerts<b class='{'hot' if c and c['alerts'] else ''}'>{len(c['alerts']) if c else 0}</b></span></footer></article>"
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
            f"<li class='{sev}'><time>{_clock(started, t)}</time><span class='who'>{escape(driver)}</span>"
            f"<span class='kind'>{what}</span><p>{escape(body)}</p></li>"
        )
    alerts_html = f"<ul class='feed'>{''.join(alert_items)}</ul>" if alert_items else "<div class='empty'>No alerts tonight. Good.</div>"

    log_rows = [
        f"<tr><td>{c['started_at'][5:16]}</td><td><b>{escape(c['driver'])}</b></td>"
        f"<td>{c['kind']}{'' if c.get('lang', 'hi') in ('auto', 'hi') else ' - ' + c['lang']}</td>"
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
        hero_svg=HERO_SVG,
        phone_icon=PHONE_ICON,
        refresh=REFRESH_SECONDS,
        dialog=try_block(now, try_id, done_id, error),
        open_attr=" open" if opened else "",
        done_js="true" if done else "false",
        now=f"{now:%A %d %b, %H:%M}",
        n_drivers=len(roster),
        n_calls=len(calls),
        n_alerts=len(alerts),
        attention=attention,
        attention_sev="critical" if attention else "",
        cards="".join(cards),
        alerts=alerts_html,
        log=log_html,
    )


def try_block(now: datetime, try_id: str | None, done_id: str | None, error: str | None) -> str:
    """Three numbered steps. Which step is live follows the server state: details and time first, the code
    only once the phone has been rung, then the booking. Nothing is typed into a step that is not live."""
    err = f"<p class='err'>{escape(error)}</p>" if error else ""
    entry = trials.get(try_id) if try_id else None
    done = trials.get(done_id) if done_id else None
    head = ("<header><h2>Try Hoshiyar</h2><p>We ring your number, read a four-digit code, and schedule the check-in "
            "call once you type it. Only you can book your number.</p></header>")
    if done and done["verified"]:
        return (
            f"{head}<ol class='steps'>"
            f"<li class='done'><b>Your details</b><span>{escape(done['name'])} &middot; {trials.masked(done['phone'])}</span></li>"
            f"<li class='done'><b>Pick a time</b><span>{done['at']}</span></li>"
            f"<li class='done'><b>Verified</b><span class='ok'>Scheduled. Hoshiyar will call {escape(done['name'])} at <b>{done['at']}</b>. "
            "The call will appear on this page as it happens.</span></li></ol>"
        )
    if entry and not entry["verified"]:
        return (
            f"{head}<ol class='steps'>"
            f"<li class='done'><b>Your details</b><span>{escape(entry['name'])} &middot; {trials.masked(entry['phone'])}</span></li>"
            f"<li class='done'><b>Pick a time</b><span>{entry['at']}</span></li>"
            f"<li class='live'><b>Verify with code</b><span>Calling <b>{trials.masked(entry['phone'])}</b> now. Type the four digits you hear.</span>{err}"
            f"<form method='post' action='/verify' class='row'><input type='hidden' name='id' value='{entry['id']}'>"
            "<input name='code' class='code' inputmode='numeric' pattern='[0-9]{4}' maxlength='4' placeholder='0000' autofocus required>"
            "<button class='cta'>Verify</button></form>"
            f"<form method='post' action='/try/{entry['id']}/again' class='again'><button class='link'>Did not get the call? Call again</button></form>"
            "</li></ol>"
        )
    soon = f"{now + timedelta(minutes=2):%H:%M}"
    return (
        f"{head}<form method='post' action='/try'><ol class='steps'>"
        f"<li class='live'><b>Your details</b><span>Enter your name, mobile number and the language you want.</span>{err}"
        "<div class='row'><label>Name<input name='name' placeholder='e.g. Ramesh' maxlength='40' required></label>"
        "<label>Mobile number<span class='phone'><i>+91</i><input name='phone' inputmode='numeric' placeholder='98765 43210' maxlength='13' required></span></label></div>"
        "<label>Language<select name='lang'><option value='auto'>Hindi, or let me choose</option><option value='hi'>Hindi</option>"
        "<option value='te'>Telugu</option><option value='kn'>Kannada</option><option value='mr'>Marathi</option>"
        "<option value='en'>English</option></select></label></li>"
        "<li class='live'><b>Pick a time</b><span>We call you at this time. Default is two minutes from now; any time tonight works.</span>"
        f"<label>Time<input name='at' type='time' value='{soon}' required></label></li>"
        "<li class='wait'><b>Verify with code</b><span>We call you first. The code box opens here once the phone rings.</span></li>"
        "</ol><div class='submit'><button class='cta'>Call me with a code</button>"
        "<small>By using this, you agree to receive one automated call from Hoshiyar to verify your number and the check-in call you book.</small></div></form>"
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
:root{color-scheme:dark;--plane:#040b15;--surface:#07131f;--surface-2:#0c1a2a;--ink:#f1f4f8;--ink-2:#a9b6c6;--muted:#75859a;
 --hair:#12223a;--rule:#1a2d45;--series:#3b8fe0;--orange:#f36a3d;--amber:#ff9a45;--accent:#f36a3d;
 --good:#16c784;--warning:#ff9a45;--serious:#f36a3d;--critical:#f04444;--info:#39a9e8;
 --cta:linear-gradient(105deg,#f45a35 0%,#ff9a45 100%)}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{width:62%;margin:0 0 0 15%;padding:0 0 56px}
.hero{position:relative;overflow:hidden;background:#021c37;width:100%;height:clamp(300px,29vw,460px);display:flex;flex-direction:column;justify-content:flex-end}
.hero img,.hero svg.bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 55%;display:block}
.hero .shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,11,21,.72) 0,rgba(4,11,21,.38) 38%,rgba(4,11,21,.04) 100%),linear-gradient(0deg,var(--plane) 0,rgba(4,11,21,0) 50%)}
.hero .text{position:relative;width:62%;margin:0 0 0 15%;padding:40px 0 0;flex:1;display:flex;flex-direction:column}
.brand{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
.brand .mark{font-size:30px;font-weight:750;letter-spacing:.015em;line-height:1}
.brand .lat{font-size:13px;color:var(--ink-2);letter-spacing:.16em;text-transform:uppercase}
.sub{color:var(--ink-2);margin-top:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px}
.onair{display:inline-flex;align-items:center;gap:8px;color:var(--ink);font-weight:600} .onair i{width:9px;height:9px;border-radius:50%;background:var(--good);animation:pulse 2s infinite}
@keyframes pulse{50%{opacity:.35}} @media (prefers-reduced-motion:reduce){.onair i{animation:none}}
.strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:auto;padding-top:24px;border-top:1px solid rgba(255,255,255,.10);padding-bottom:14px}
.stat{padding:16px 22px 10px 0;border-right:1px solid var(--rule)} .stat+.stat{padding-left:22px} .stat:last-child{border-right:0}
.stat label{display:block;color:var(--ink-2);font-size:11px;letter-spacing:.09em;text-transform:uppercase}
.stat b{display:block;font-size:38px;font-weight:650;line-height:1;margin-top:6px} .stat.critical b{color:var(--critical)}
.trycta{position:relative;isolation:isolate;overflow:hidden;display:flex;align-items:center;gap:22px;min-height:112px;margin:12px 0 26px;padding:18px 24px;border:1px solid rgba(243,106,61,.42);border-radius:10px;background:linear-gradient(90deg,rgba(38,22,20,.88),rgba(4,11,21,.88))}
.trycta::before{content:"";position:absolute;inset:0;z-index:-1;background:url(/static/hero.jpg) center 56%/cover no-repeat;opacity:.12;filter:saturate(.75)}
.trycta .disc{width:64px;height:64px;flex:0 0 64px;display:grid;place-items:center;border-radius:50%;background:rgba(243,106,61,.16);color:var(--orange)}
.trycta .copy{flex:1;min-width:0} .trycta h3{margin:0;font-size:23px;font-weight:700} .trycta p{margin:6px 0 0;color:var(--ink-2);font-size:15px}
.trycta button{border:0;border-radius:8px;padding:15px 40px;min-width:220px;background:var(--cta);color:#151515;font:inherit;font-weight:750;font-size:15px;cursor:pointer;white-space:nowrap}
h2.sec{display:flex;align-items:center;gap:14px;margin:24px 0 14px;color:var(--ink);font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:700}
h2.sec::after{content:"";flex:1;height:1px;background:var(--rule)} h2.sec small{font-size:13px;letter-spacing:0;text-transform:none;color:var(--ink-2);font-weight:400}
.drivers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-bottom:1px solid var(--rule)}
.card{padding:12px 22px 14px 8px;border-right:1px solid var(--rule);min-width:0;display:flex;flex-direction:column;gap:12px}
.card:nth-child(3n){border-right:0} .card:nth-child(n+4){border-top:1px solid var(--rule)}
.card header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px} .card h3{margin:0;font-size:19px;font-weight:700}
.route{color:var(--ink-2);font-size:13px;margin-top:3px}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:650;white-space:nowrap;padding-top:4px}
.pill i{width:10px;height:10px;border-radius:50%;background:var(--muted);font-size:0}
.pill.good i{background:var(--good)} .pill.warning i{background:var(--warning)} .pill.serious i{background:var(--serious)} .pill.critical i{background:var(--critical)} .pill.info i{background:var(--info)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:16px} .stat2 label{display:block;color:var(--ink-2);font-size:13px;margin-bottom:8px}
.meter{display:flex;gap:3px;height:12px} .meter i{flex:1;border-radius:3px;opacity:.18} .meter i.on{opacity:1}
.meter i.good{background:var(--good)} .meter i.warning{background:var(--warning)} .meter i.serious{background:var(--serious)} .meter i.critical{background:var(--critical)} .meter i.muted{background:var(--muted)}
.meterval{margin-top:8px;font-size:22px;font-weight:700;line-height:1} .meterval small,.sparkval small{color:var(--ink-2);font-size:13px;font-weight:400}
.meterval.serious{color:var(--serious)} .meterval.critical{color:var(--critical)} .meterval.warning{color:var(--warning)} .meterval.good{color:var(--good)}
.spark{display:block;overflow:visible} .spark polyline{fill:none;stroke:var(--series);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.spark .end{fill:var(--series);stroke:var(--plane);stroke-width:2} .spark .hit{fill:transparent}
.spark .truck{fill:none;stroke:var(--orange);stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.spark.empty{color:var(--ink-2);font-size:14px;height:40px;display:flex;align-items:center;border:1px solid var(--rule);border-radius:8px;padding:0 14px;width:max-content;max-width:100%}
.sparkval{margin-top:2px;font-size:14px;display:flex;align-items:center;gap:5px} .sparkval .ti{color:var(--orange);flex:0 0 auto} .sparkval b{font-weight:700}
.sparkval .serious{color:var(--serious)} .sparkval .good{color:var(--good)} .sparkval .muted{color:var(--muted)}
.card footer{display:flex;gap:22px;color:var(--ink-2);font-size:14px;border-top:1px solid var(--hair);padding-top:12px} .card footer b{color:var(--ink);font-weight:700;margin-left:8px} .card footer b.hot{color:var(--critical)}
.feed{list-style:none;margin:0;padding:0}
.feed li{display:grid;grid-template-columns:72px 140px 150px minmax(0,1fr);gap:12px;align-items:baseline;padding:12px 8px 12px 18px;border-top:1px solid var(--rule);border-left:3px solid var(--muted);font-size:14px}
.feed li:last-child{border-bottom:1px solid var(--rule)}
.feed li.serious{border-left-color:var(--serious)} .feed li.critical{border-left-color:var(--critical)} .feed li.warning{border-left-color:var(--warning)}
.feed time{color:var(--ink-2);font-variant-numeric:tabular-nums} .feed .who{font-weight:600} .feed .kind{font-weight:700} .feed li.serious .kind{color:var(--serious)} .feed li.critical .kind{color:var(--critical)} .feed li.warning .kind{color:var(--warning)}
.feed p{margin:0;color:var(--ink-2)}
.scroll{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:10px}
table{width:100%;border-collapse:collapse;min-width:760px;font-size:14px} th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--rule);white-space:nowrap}
th{color:var(--ink-2);font-weight:500;background:rgba(255,255,255,.025)} tbody tr:last-child td{border-bottom:0} .num{text-align:right;font-variant-numeric:tabular-nums} td b{font-weight:600}
.empty{border:1px dashed var(--rule);border-radius:10px;padding:18px;color:var(--ink-2);text-align:center}
.card h3 .tag{font-size:11px;font-weight:700;color:var(--info);text-transform:uppercase;letter-spacing:.12em;margin-left:10px;vertical-align:middle}
dialog#try{background:#07131f;color:var(--ink);border:1px solid var(--rule);border-radius:14px;padding:26px 28px 22px;width:min(720px,calc(100% - 32px));box-sizing:border-box}
dialog#try::backdrop{background:rgba(2,9,18,.78)}
dialog#try header h2{margin:0 0 8px;font-size:28px;font-weight:700;line-height:1.1} dialog#try header p{margin:0 0 18px;color:var(--ink-2);max-width:560px}
.steps{list-style:none;margin:0;padding:0;counter-reset:s}
.steps li{position:relative;padding:14px 0 16px 48px;border-top:1px solid var(--hair);counter-increment:s}
.steps li::before{content:counter(s);position:absolute;left:0;top:14px;width:30px;height:30px;border-radius:50%;border:1.5px solid var(--ink-2);display:grid;place-items:center;font-weight:600;font-size:14px}
.steps li.done::before{content:"\\2713";border-color:var(--good);color:var(--good)} .steps li.wait{opacity:.45}
.steps li>b{display:block;font-size:17px;font-weight:600} .steps li>span{display:block;color:var(--ink-2);font-size:14px;margin-top:2px}
.steps li>span.ok{color:var(--ink)} .steps label{display:block;color:var(--ink-2);font-size:14px;margin-top:12px}
.steps input,.steps select{display:block;width:100%;margin-top:6px;font:inherit;font-size:16px;color:var(--ink);background:#040b15;border:1px solid var(--rule);border-radius:10px;padding:12px 14px}
.steps .row{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:end}
.steps .phone{display:flex;margin-top:6px} .steps .phone i{font-style:normal;color:var(--ink-2);padding:12px 0 12px 14px;background:#040b15;border:1px solid var(--rule);border-right:0;border-radius:10px 0 0 10px}
.steps .phone input{margin:0;border-radius:0 10px 10px 0;border-left:0}
.steps input.code{width:170px;font-size:26px;letter-spacing:.45em;text-align:center;padding:10px 0 10px .45em}
.steps li.live form.row{grid-template-columns:auto auto;justify-content:start;margin-top:12px}
.steps .again{margin-top:10px} .steps .link{background:none;border:0;color:var(--ink-2);font:inherit;padding:0;text-decoration:underline;cursor:pointer}
.steps .err,dialog#try .err{color:var(--critical);font-weight:600;margin:8px 0 0}
.cta{font:inherit;font-weight:750;font-size:15px;background:var(--cta);color:#151515;border:0;border-radius:8px;padding:14px 24px;cursor:pointer;white-space:nowrap}
.submit{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-top:18px} .submit small{color:var(--ink-2);font-size:13px;max-width:380px}
dialog#try .close{position:absolute;top:14px;right:14px;margin:0} dialog#try .close button{font:inherit;font-size:20px;line-height:1;background:none;border:0;color:var(--ink-2);cursor:pointer;padding:6px 10px}
@media (max-width:1100px){.wrap{width:auto;margin:0;padding:0 24px 56px} .hero .text{width:auto;margin:0;padding:40px 24px 0}}
@media (max-width:960px){.drivers{grid-template-columns:repeat(2,minmax(0,1fr))} .card:nth-child(3n){border-right:1px solid var(--rule)} .card:nth-child(2n){border-right:0} .card:nth-child(n+4){border-top:0} .card:nth-child(n+3){border-top:1px solid var(--rule)}}
@media (max-width:760px){.wrap{width:auto;margin:0;padding:0 18px 48px} .hero{height:auto;min-height:0} .hero .text{width:auto;padding:26px 18px 0} .brand .mark{font-size:25px}
 .strip{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:24px} .stat{padding:12px 10px 12px 0} .stat+.stat{padding-left:12px} .stat:nth-child(2){border-right:0} .stat:nth-child(n+3){border-top:1px solid var(--rule)} .stat b{font-size:30px}
 .trycta{align-items:flex-start;flex-wrap:wrap;gap:12px;padding:16px} .trycta .disc{width:48px;height:48px;flex-basis:48px} .trycta .copy{flex-basis:calc(100% - 64px)} .trycta h3{font-size:19px} .trycta p{font-size:13px} .trycta button{width:100%}
 .drivers{grid-template-columns:1fr} .card,.card:nth-child(n){padding:16px 4px;border-right:0;border-top:0;border-bottom:1px solid var(--rule)} .row,.steps .row{grid-template-columns:1fr}
 .feed li{grid-template-columns:54px 64px 1fr;gap:8px} .feed p{grid-column:2/-1}}
"""

HERO_SVG = (
    "<svg class='bg' viewBox='0 0 1600 420' preserveAspectRatio='xMidYMid slice' aria-hidden='true'>"
    "<defs><linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#090b16'/><stop offset='.7' stop-color='#121a33'/><stop offset='1' stop-color='#1b1f2e'/></linearGradient>"
    "<radialGradient id='glow' cx='.5' cy='.5' r='.5'><stop offset='0' stop-color='#ffd27a' stop-opacity='.9'/><stop offset='1' stop-color='#ffd27a' stop-opacity='0'/></radialGradient></defs>"
    "<rect width='1600' height='420' fill='url(#sky)'/>"
    "<g fill='#e9e4d4' opacity='.8'><circle cx='210' cy='70' r='1.4'/><circle cx='380' cy='120' r='1'/><circle cx='560' cy='50' r='1.2'/><circle cx='760' cy='95' r='1'/><circle cx='900' cy='40' r='1.4'/><circle cx='1120' cy='110' r='1'/><circle cx='1320' cy='60' r='1.3'/><circle cx='1480' cy='130' r='1'/><circle cx='1020' cy='160' r='.9'/><circle cx='1230' cy='30' r='1.1'/></g>"
    "<circle cx='1180' cy='96' r='26' fill='#f3e6b8'/><circle cx='1194' cy='88' r='24' fill='#0d1020'/>"
    "<path d='M0 300 L120 250 L260 285 L400 225 L520 265 L640 230 L760 270 L900 215 L1040 260 L1180 235 L1320 270 L1460 240 L1600 280 L1600 420 L0 420Z' fill='#0f1424'/>"
    "<path d='M0 330 L160 300 L320 325 L480 290 L640 320 L800 295 L960 322 L1120 300 L1280 326 L1440 305 L1600 330 L1600 420 L0 420Z' fill='#0a0d19'/>"
    "<path d='M700 420 L860 330 L920 330 L1250 420Z' fill='#1c1e26'/><path d='M884 330 L896 330 L1010 420 L960 420Z' fill='#e2d9b8' opacity='.35'/>"
    "<ellipse cx='905' cy='336' rx='70' ry='10' fill='url(#glow)'/>"
    "<g transform='translate(930 262)'><rect x='0' y='0' width='120' height='62' rx='4' fill='#2a2f3d'/><rect x='118' y='18' width='42' height='44' rx='4' fill='#353b4d'/><rect x='4' y='56' width='28' height='12' rx='3' fill='#ff3b30' opacity='.9'/><rect x='88' y='56' width='28' height='12' rx='3' fill='#ff3b30' opacity='.9'/>"
    "<circle cx='22' cy='70' r='7' fill='#0a0a0a'/><circle cx='98' cy='70' r='7' fill='#0a0a0a'/><circle cx='146' cy='70' r='7' fill='#0a0a0a'/></g>"
    "</svg>"
)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hoshiyar fleet</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
<div class="hero">{hero_svg}<img src="/static/hero.jpg" alt="" onerror="this.remove()"><div class="shade"></div>
<div class="text"><div class="brand"><span class="mark">HOSHIYAR</span><span class="lat">Fleet tonight</span></div>
<div class="sub"><span class="onair"><i></i>Live</span><span>{now}</span><span>&middot;</span><span>refreshes every {refresh} s</span></div>
<div class="strip">
 <div class="stat {attention_sev}"><label>Need attention now</label><b>{attention}</b></div>
 <div class="stat"><label>Drivers on roster</label><b>{n_drivers}</b></div>
 <div class="stat"><label>Calls tonight</label><b>{n_calls}</b></div>
 <div class="stat"><label>Alerts tonight</label><b>{n_alerts}</b></div>
</div></div></div>
<div class="wrap">
<section class="trycta"><div class="disc">{phone_icon}</div><div class="copy"><h3>Try Hoshiyar</h3><p>Get a check-in call on your own phone. No app installation required.</p></div>
<button type="button" onclick="document.getElementById('try').showModal()">Try it now &rarr;</button></section>
<dialog id="try"{open_attr}><form method="dialog" class="close"><button aria-label="Close">&times;</button></form>{dialog}</dialog>
<script>
(function(){{var d=document.getElementById('try');
if(d.open){{d.close();d.showModal();}}
if(location.search&&!/[?&]try=/.test(location.search))history.replaceState(null,'','/fleet');
try{{history.scrollRestoration='manual';}}catch(e){{}}
window.addEventListener('load',function(){{try{{var y=sessionStorage.getItem('fleetY');if(y!==null){{sessionStorage.removeItem('fleetY');window.scrollTo(0,+y);}}}}catch(e){{}}}});
function refresh(){{try{{sessionStorage.setItem('fleetY',String(window.scrollY));}}catch(e){{}}location.replace('/fleet');}}
if({done_js}){{setTimeout(function(){{d.close();refresh();}},8000);}}
setInterval(function(){{if(!d.open)refresh();}},{refresh}*1000);}})();
</script>
<h2 class="sec">Drivers</h2><div class="drivers">{cards}</div>
<h2 class="sec">Alerts<small>newest first</small></h2>{alerts}
<h2 class="sec">Call log</h2>{log}
</div></body></html>"""
