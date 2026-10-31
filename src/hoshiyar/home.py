"""The homepage at /: the pitch as a landing page, matching Jatin's homepage mock (2026-10-31).

One HTML string, no build step. Illustrations are files in static/home/ (see its README). The mock runs the
pictures under the sections rather than between them, sets body copy in a serif, and keeps the page dense;
this follows the mock where the handoff tokens disagreed. Every number comes from scratch/pitch.md.
"""

STATS = [
    ("1 in 5", "of India's road deaths involve a truck as the striking vehicle."),
    ("32,362", "people killed in truck-related accidents out of 1,77,175 road deaths in 2024."),
    ("70%", "of all road deaths were booked as over-speeding. Fatigue has no box on the form."),
]

STEPS = [
    ("phone", "Calls him", "Regular check-ins through the night"),
    ("wave", "Reads him", "Detects fatigue from his words and reply speed"),
    ("chat", "Keeps him company", "Real conversation, a quiz when sleepy"),
    ("pin", "Gets him off the road", "A 20-minute stop when it is not safe"),
    ("bell", "Wakes him up", "Calls back at the right time"),
]

ICONS = {  # from the design handoff (scratch/homepage-tokens.md lists the source); 24x24 line icons
    "bell": "<path d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4'/>",
    "bolt": "<path d='M13 2 3 14h7l-1 8 12-14h-7l-1-6z'/>",
    "chat": "<path d='M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z'/>",
    "phone": "<path d='M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.4 19.4 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.7 2z'/>",
    "pin": "<path d='M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0z'/><circle cx='12' cy='10' r='2.5'/>",
    "shield": "<path d='M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z'/><path d='m9 12 2 2 4-4'/>",
    "truck": "<path d='M3 6h11v12H3zM14 10h4l3 3v5h-7z'/><circle cx='7.5' cy='19' r='1.5'/><circle cx='17.5' cy='19' r='1.5'/>",
    "wave": "<path d='M2 10v4M6 6v12M10 3v18M14 7v10M18 5v14M22 10v4'/>",
}

OPENER = "नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?"


def icon(name: str, size: int = 24) -> str:
    return (f"<svg viewBox='0 0 24 24' width='{size}' height='{size}' fill='none' stroke='currentColor' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{ICONS[name]}</svg>")


def render() -> str:
    parts = {
        "stats": "".join(f"<div class='stat'><b>{n}</b><p>{t}</p></div>" for n, t in STATS),
        "steps": "".join(
            f"<li><span class='disc'>{icon(k)}</span><b>{i}. {name}</b><p>{what}</p></li>"
            for i, (k, name, what) in enumerate(STEPS, start=1)
        ),
        "trucks": "".join(f"<span class='{'hot' if i == 5 else ''}'>{icon('truck', 30)}</span>" for i in range(6)),
        "bars": "".join(f"<i style='height:{h}px'></i>" for h in (6, 12, 20, 9, 16, 24, 11, 18, 7, 14, 22, 10, 15, 6)),
        "opener": OPENER,
        "bolt": icon("bolt", 30),
        "shield": icon("shield", 30),
    }
    page = PAGE
    for key, value in parts.items():
        page = page.replace("{" + key + "}", value)  # plain replace: the CSS is full of braces
    return page


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hoshiyar</title>
<meta name="description" content="A voice co-driver that calls truck drivers through the night, hears how tired they are, keeps them sharp, gets them to stop, and tells the fleet.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&family=Inter:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{--cream:#fff7eb;--cream-2:#f8ecda;--ink:#0f2a44;--ink-2:#3a3a3a;--muted:#6f6a63;--rule:#d9ccb4;--red:#ef3b2d;--navy:#07182b;
 --display:Fraunces,Georgia,"Times New Roman",serif;--serif:"Source Serif 4",Georgia,"Times New Roman",serif;--sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
 --gutter:40px;--canvas:1024px}
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;background:#050f1c;color:var(--ink);font:13px/1.45 var(--serif)}
.canvas{max-width:var(--canvas);margin:0 auto;background:var(--cream);box-shadow:0 0 60px rgba(0,0,0,.5)}
a{color:inherit}
.wrap{padding:0 var(--gutter)}
/* every section is a picture with text on it; .art paints the image, .fade paints the readable area */
section,header.hero,footer{position:relative;overflow:hidden;background:var(--cream)}
.art{position:absolute;inset:0;background-size:cover;background-position:center;background-repeat:no-repeat}
.fade{position:absolute;inset:0}
.wrap{position:relative}
nav{position:sticky;top:0;z-index:5;background:var(--navy);color:#fff}
nav .wrap{max-width:var(--canvas);margin:0 auto}
nav .wrap{display:flex;align-items:center;justify-content:space-between;height:52px;gap:20px}
nav .mark{font:700 23px/1 var(--sans);letter-spacing:.04em;text-decoration:none}
nav ul{list-style:none;margin:0;padding:0;display:flex;gap:30px;font:500 13px var(--serif)} nav ul a{text-decoration:none}
.btn{display:inline-block;background:var(--red);color:#fff;text-decoration:none;font:600 12px/1 var(--sans);padding:10px 15px;border-radius:999px;white-space:nowrap}
.btn.ghost{background:none;color:var(--red);border:1px solid var(--red)}
.num{font:600 10px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--red);margin-bottom:5px}
h2{font:600 27px/1.08 var(--display);margin:0 0 6px;letter-spacing:-.01em} .lead{font:400 14px/1.4 var(--serif);color:var(--ink-2);margin:0}
/* hero */
.hero{color:#fff;height:330px}
.hero .art{background-image:url(/static/home/hero.jpg);background-position:center 60%}
.hero .fade{background:linear-gradient(90deg,rgba(7,24,43,.7) 0,rgba(7,24,43,.3) 50%,rgba(7,24,43,0) 68%)}
.hero .wrap{display:grid;grid-template-columns:1fr 244px;gap:40px;align-items:center;height:100%}
.eyebrow{font:600 11px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:#ff6b57}
h1{font:600 31px/1.06 var(--display);margin:6px 0 10px;max-width:420px;letter-spacing:-.01em;text-shadow:0 2px 14px rgba(0,0,0,.4)} h1 em{font-style:normal;color:#ff5a45;white-space:nowrap}
.hero p{font:400 13.5px/1.42 var(--serif);max-width:370px;margin:0 0 14px;color:#f6f2ea;text-shadow:0 1px 10px rgba(0,0,0,.5)}
.phone{width:240px;background:#0e1322;border:1px solid rgba(255,255,255,.14);border-radius:16px;padding:11px;box-shadow:0 24px 50px rgba(0,0,0,.5);font-size:11px}
.phone .top{display:flex;justify-content:space-between;color:#cfd3dc;font-size:10.5px}
.phone .face{width:74px;height:74px;border-radius:50%;margin:9px auto 5px;background:radial-gradient(circle at 50% 40%,#f1c27d,#c98a4f 70%,#6b3f1f);display:grid;place-items:center;font:700 24px var(--display);color:#2a1a0c;border:3px solid #ff5a45;overflow:hidden}
.phone .face img{width:100%;height:100%;border-radius:50%;object-fit:cover;display:block}
.phone .who{text-align:center} .phone .who b{display:block;font:700 14px var(--sans);letter-spacing:.06em} .phone .who span{color:#aeb4c2;font-size:10.5px}
.bubble{display:flex;gap:8px;align-items:center;background:#1b2234;border-radius:11px;padding:7px 9px;margin:9px 0 8px}
.bars{display:flex;gap:2px;align-items:center;height:20px;flex:0 0 auto} .bars i{width:2px;border-radius:2px;background:#ff5a45;display:block}
.bubble p{margin:0;font:500 12px/1.3 var(--serif);color:#fff}
.phone .resp{font:600 11px var(--sans);color:#cfd3dc;margin:0 0 5px}
.chips{display:flex;gap:4px;flex-wrap:nowrap} .chips span{border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:4px 7px;font:500 10px var(--sans);color:#fff;white-space:nowrap} .chips span.on{background:var(--red);border-color:var(--red)}
.phone small{display:block;text-align:center;color:#8d94a3;margin-top:8px;font-size:9.5px}
/* 01 problem: heading and stats on cream, the crash scene filling the lower two thirds */
.problem{height:330px}
.problem .art{background-image:url(/static/home/problem.jpg);background-position:center 40%}
.problem .fade{background:linear-gradient(180deg,var(--cream) 0,var(--cream) 36%,rgba(255,247,235,.7) 46%,rgba(255,247,235,0) 58%)}
.problem .wrap{display:grid;grid-template-columns:1fr 1.25fr;gap:28px;align-items:start;padding-top:18px}
.problem .tag{position:absolute;right:var(--gutter);top:18px;font:600 9px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);margin-top:14px}
.stat{padding:0 14px;border-left:1px solid var(--rule)} .stat:first-child{padding-left:0;border-left:0}
.stat b{display:block;font:600 30px/1 var(--display);color:var(--red)} .stat p{margin:7px 0 0;color:var(--ink-2);font-size:11.5px;line-height:1.4}
/* 02 why now: the truck on the right, text and figure on cream */
.mandate{height:230px}
.mandate .art{background-image:url(/static/home/mandate.jpg);background-position:right 40%;background-size:52% auto}
.mandate .fade{background:linear-gradient(90deg,var(--cream) 0,var(--cream) 48%,rgba(255,247,235,.95) 62%,rgba(255,247,235,.4) 74%,rgba(255,247,235,0) 86%)}
.mandate .wrap{display:grid;grid-template-columns:1fr .85fr .65fr;gap:22px;align-items:center;height:100%}
.date{font:600 11px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--red)} .year{font:700 64px/1 var(--display);color:var(--red);margin:2px 0 10px;letter-spacing:-.02em}
.laws{display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:270px} .laws div{border-left:1px solid var(--rule);padding-left:10px} .laws b{display:flex;align-items:center;gap:6px;font:700 11.5px var(--sans)} .laws b i{font-style:normal;font-size:15px;line-height:1} .laws p{margin:4px 0 0;color:var(--ink-2);font-size:11.5px;line-height:1.4}
.mandate .figure{border-left:1px solid var(--rule);padding-left:20px}
/* 03 the gap: dark, the fleet behind */
.gap{color:#fff;height:210px}
.gap .art{background-image:url(/static/home/fleet.jpg);background-position:center 55%}
.gap .fade{background:linear-gradient(90deg,rgba(7,24,43,.82) 0,rgba(7,24,43,.5) 40%,rgba(7,24,43,.12) 68%,rgba(7,24,43,.45) 100%)}
.gap .wrap{display:grid;grid-template-columns:1.4fr .6fr;gap:26px;align-items:center;height:100%}
.gap h2{color:#fff;font-size:26px;max-width:340px;text-shadow:0 2px 12px rgba(0,0,0,.4)} .gap .lead{color:#eef0f3;font-size:13px;max-width:360px;text-shadow:0 1px 8px rgba(0,0,0,.5)}
.trucks{display:flex;gap:8px;margin-top:10px;color:#d7dbe2} .trucks .hot{color:var(--red)}
.gap aside{border-left:1px solid rgba(255,255,255,.4);padding-left:18px;font:600 24px/1.15 var(--display);color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.45)}
/* 04 steps, 05 proof: faint road behind cream */
.how{height:190px} .how .art{background-image:url(/static/home/footer.jpg);background-position:center 30%;opacity:.14} .how .fade{background:linear-gradient(180deg,rgba(255,247,235,.5),rgba(255,247,235,.15))}
.how .wrap{display:grid;grid-template-columns:.65fr 1.9fr;gap:26px;align-items:center;height:100%}
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(5,1fr);gap:8px;text-align:center}
.steps li{border-left:1px solid var(--rule);padding:0 5px} .steps li:first-child{border-left:0}
.disc{display:grid;place-items:center;width:46px;height:46px;border-radius:50%;background:var(--red);color:#fff;margin:0 auto 7px} .disc svg{width:20px;height:20px}
.steps b{display:block;font:700 12px var(--sans)} .steps p{margin:2px 0 0;color:var(--ink-2);font-size:11px;line-height:1.35}
.proof{height:110px;background:var(--cream-2)} .proof .art{background-image:url(/static/home/mandate.jpg);background-position:center 70%;opacity:.1}
.proof .wrap{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;align-items:center;height:100%}
.proof .pf{display:flex;gap:12px;align-items:center;border-left:1px solid var(--rule);padding-left:18px} .proof .ring{width:48px;height:48px;border-radius:50%;border:2px solid var(--red);color:var(--red);display:grid;place-items:center;flex:0 0 48px} .proof .ring svg{width:24px;height:24px}
.proof b{font:600 26px/1 var(--display);color:var(--red)} .proof p{margin:3px 0 0;color:var(--ink-2);font-size:11.5px}
footer{color:#fff;height:120px}
footer .art{background-image:url(/static/home/footer.jpg);background-position:center 72%}
footer .fade{background:linear-gradient(90deg,rgba(7,24,43,.75) 0,rgba(7,24,43,.2) 55%,rgba(7,24,43,.5) 100%)}
footer .wrap{display:flex;justify-content:space-between;align-items:center;gap:20px;height:100%}
footer .mark{font:700 25px/1 var(--sans);letter-spacing:.04em} footer p{margin:3px 0 0;font:400 13.5px var(--serif);color:#f3efe6}
@media (max-width:900px){:root{--gutter:18px} .canvas{box-shadow:none} .hero,.problem,.mandate,.gap,.how,.proof,footer{height:auto;padding:24px 0}
 .hero .wrap,.problem .wrap,.mandate .wrap,.gap .wrap,.how .wrap,.proof .wrap{grid-template-columns:1fr} .problem .fade{background:rgba(255,247,235,.86)} .mandate .fade{background:rgba(255,247,235,.88)} .mandate .wrap>:last-child{display:none} .mandate .figure{border-left:0;padding-left:0}
 .stats{grid-template-columns:1fr;gap:10px;margin-top:12px} .stat{padding:0;border-left:0} .steps{grid-template-columns:repeat(2,1fr);gap:14px} .steps li{border-left:0} h1{font-size:28px} h2{font-size:24px} .year{font-size:52px} nav ul{display:none} .problem .tag{display:none}}
</style></head><body>
<nav><div class="wrap"><a class="mark" href="/">HOSHIYAR</a><ul><li><a href="#problem">The Problem</a></li><li><a href="#how">How it works</a></li><li><a href="#proof">Proof</a></li></ul><a class="btn" href="/fleet">Tonight's fleet &rarr;</a></div></nav>

<div class="canvas">
<header class="hero"><div class="art"></div><div class="fade"></div><div class="wrap">
<div><div class="eyebrow">NH48 &middot; 02:17 AM</div>
<h1>Every driver on the road tonight deserves <em>a co-driver.</em></h1>
<p>Hoshiyar is a voice co-driver, in the driver's own language, who never sleeps. It calls him through the night, hears how tired he is, keeps him sharp, gets him to stop, and tells his fleet.</p>
<a class="btn" href="#how">See how it works &rarr;</a></div>
<div class="phone"><div class="top"><span>&#9742; Incoming call &hellip;</span><span>02:17 AM</span></div>
<div class="face"><img src="/static/home/avatar.png" alt="" onerror="this.parentNode.textContent='हो'"></div>
<div class="who"><b>HOSHIYAR</b><span>Night check-in</span></div>
<div class="bubble"><div class="bars">{bars}</div><p>{opener}</p></div>
<p class="resp">Your response</p><div class="chips"><span>I'm fine</span><span class="on">A little sleepy</span><span>Very sleepy</span></div>
<small>Illustrative conversation &middot; not a live call</small></div>
</div></header>

<section class="problem" id="problem"><div class="art"></div><div class="fade"></div><span class="tag">India &middot; Road safety</span><div class="wrap">
<div><div class="num">01 / The problem</div><h2>A moment of fatigue<br>can change many lives.</h2><p class="lead">A driver nods off. A vehicle keeps moving.<br>Someone else pays the price.</p></div>
<div class="stats">{stats}</div></div></section>

<section class="mandate" id="why"><div class="art"></div><div class="fade"></div><div class="wrap">
<div><div class="num">02 / Why now</div><h2>The 2028 mandate<br>is a real opportunity.</h2>
<p class="lead">The EU required drowsiness warning on every new vehicle from July 2024. India requires it on every new truck and bus from 1 January 2028 under AIS-184.</p>
<p style="margin:12px 0 0"><a class="btn ghost" href="https://www.pib.gov.in/PressReleasePage.aspx?PRID=2227148">Learn more about the regulation &rarr;</a></p></div>
<div class="figure"><div class="date">01 January</div><div class="year">2028</div>
<div class="laws"><div><b><i>&#x1F1EA;&#x1F1FA;</i>EU</b><p>Drowsiness and attention warning on all new vehicles since July 2024.</p></div>
<div><b><i>&#x1F1EE;&#x1F1F3;</i>India</b><p>AIS-184 on every new truck and bus from 1 January 2028.</p></div></div></div>
<div></div></div></section>

<section class="gap" id="gap"><div class="art"></div><div class="fade"></div><div class="wrap">
<div><div class="num">03 / The opportunity</div><h2>The uncovered fleet<br>is the real gap.</h2>
<p class="lead">Millions of drivers are on the road every night. Most are still without a co-driver, and the mandate covers only trucks built after 2028.</p>
<div class="trucks">{trucks}</div></div>
<aside>A massive<br>untapped<br>opportunity.</aside></div></section>

<section class="how" id="how"><div class="art"></div><div class="fade"></div><div class="wrap">
<div><div class="num">04 / How it works</div><h2>Five simple steps.<br>A safer journey.</h2><p class="lead">Hoshiyar works like a real co-driver, not a device, not a distraction.</p>
<p style="margin:10px 0 0"><a class="btn ghost" href="/fleet">See the full flow &rarr;</a></p></div>
<ol class="steps">{steps}</ol></div></section>

<section class="proof" id="proof"><div class="art"></div><div class="wrap">
<div><div class="num">05 / Proof</div><h2>Built around<br>real-time response.</h2></div>
<div class="pf"><span class="ring">{bolt}</span><div><b>0.35s</b><p>to first word<br>(average)</p></div></div>
<div class="pf"><span class="ring">{shield}</span><div><b>0.6s</b><p>for stop detection /<br>reply initiation</p></div></div>
</div></section>

<footer><div class="art"></div><div class="fade"></div><div class="wrap"><div><div class="mark">HOSHIYAR</div><p>A co-driver for every night.</p></div><a class="btn" href="/fleet">Get in touch &rarr;</a></div></footer>
</div></body></html>"""
