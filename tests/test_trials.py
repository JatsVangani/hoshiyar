"""Try-flow tests. Run from the repo root: uv run python tests/test_trials.py
Uses a temp data folder; never touches data/. Dialing is mocked."""

import asyncio, os, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ.update({
    "TRIALS_FILE": str(tmp / "trials.json"), "SCHEDULE_FILE": str(tmp / "schedule.json"),
    "ROSTER_FILE": str(tmp / "drivers.json"), "CALLS_FILE": str(tmp / "calls.jsonl"),
    "TRIALS_PER_NIGHT": "4", "LOCAL_SERVER_URL": "https://example.test",
})
from fastapi.testclient import TestClient
from hoshiyar import server, trials, scheduler, vobiz

dialed = []
async def fake_dial(to, base_url, answer_path="/answer"):
    dialed.append((to, answer_path)); return {"request_uuid": f"uuid{len(dialed)}"}
vobiz.dial = fake_dial

passed = 0
def ok(cond, what):
    global passed
    assert cond, what; passed += 1; print("  ok", what)

with TestClient(server.app, follow_redirects=False) as c:
    print("form page")
    r = c.get("/fleet"); ok(r.status_code == 200 and "Call me with a code" in r.text and "<dialog id=\"try\">" in r.text and "http-equiv" not in r.text, "fleet page carries the closed Try dialog, no meta refresh")
    ok("setInterval" in r.text and "if(!d.open)refresh()" in r.text and "sessionStorage.setItem('fleetY'" in r.text, "script refreshes only while the dialog is closed, keeping the scroll position")
    ok("history.replaceState(null,'','/fleet')" in r.text, "error and done states drop their query string on load")

    r = c.get("/"); ok(r.status_code == 200 and "deserves <em>a co-driver.</em>" in r.text and "1 January 2028" in r.text and 'href="/fleet"' in r.text, "homepage renders with the corrected copy and links to /fleet")

    print("refusals before any call")
    r = c.post("/try", content="name=A&phone=12345&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    ok(r.status_code == 303 and "valid+Indian" in r.headers["location"], "bad number refused")
    r = c.post("/try", content="name=&phone=9876543210&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("name" in r.headers["location"], "empty name refused")

    print("happy path")
    r = c.post("/try", content="name=Ravi&phone=98765+43210&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    tid = r.headers["location"].split("try=")[1]
    ok(len(tid) == 10, "redirected to code box")
    ok(dialed[-1] == ("+919876543210", f"/otp/{tid}"), "code call dialed with answer path")
    r = c.get(f"/fleet?try={tid}"); ok("Type the four digits" in r.text and "<dialog id=\"try\" open>" in r.text, "code box opens the dialog on load")
    code = trials.get(tid)["code"]
    r = c.post(f"/otp/{tid}"); ok(", ".join(code) in r.text and 'loop="2"' in r.text, "speak xml reads the digits")

    print("duplicate while pending")
    r = c.post("/try", content="name=Ravi&phone=9876543210&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    ok(r.headers["location"] == f"/fleet?try={tid}" and len(dialed) == 1, "same number again: back to its code box, no new call")

    print("wrong codes")
    wrong = "0000" if code != "0000" else "0001"
    r = c.post("/verify", content=f"id={tid}&code={wrong}", headers={"content-type": "application/x-www-form-urlencoded"})
    ok(f"try={tid}" in r.headers["location"] and "2+tries" in r.headers["location"], "wrong code: 2 tries left, stays in box")
    r = c.post("/verify", content=f"id={tid}&code={wrong}", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("1+try+left" in r.headers["location"], "wrong code: 1 try left")

    print("call again")
    r = c.post(f"/try/{tid}/again"); ok(len(dialed) == 2 and f"try={tid}" in r.headers["location"], "second code call allowed")
    r = c.post(f"/try/{tid}/again"); ok("called+twice" in r.headers["location"], "third code call refused")

    print("right code")
    r = c.post("/verify", content=f"id={tid}&code={code}", headers={"content-type": "application/x-www-form-urlencoded"})
    ok(f"done={tid}" in r.headers["location"], "verified")
    r = c.get(f"/fleet?done={tid}"); ok("Scheduled." in r.text and "Ravi" in r.text and "if(true)" in r.text and "trial</small>" in r.text, "booking opens the dialog, closes itself, trial card in the grid")
    ok(trials.drivers()[0]["name"] == "Ravi" and trials.drivers()[0]["checkins"] == ["23:00"], "verified trial is a one-night driver")
    r = c.post("/try", content="name=Ravi&phone=9876543210&at=23:30", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("already+has+a+call+booked" in r.headers["location"], "second booking refused while the first is still pending")
    rows = trials.load(); rows[0]["due"] = time.time() - 60; trials._save(rows)  # the booked call time has passed
    r = c.post("/try", content="name=Ravi&phone=9876543210&at=23:30", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("try=" in r.headers["location"], "same number can book again once its call time has passed")
    rows = trials.load(); rows[0]["due"] = trials.get(tid)["due"] + 86400; trials._save(rows)  # keep the first entry for the tick check below

    print("lockout")
    r = c.post("/try", content="name=Sita&phone=9123456789&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    t2 = r.headers["location"].split("try=")[1]
    bad = "0000" if trials.get(t2)["code"] != "0000" else "0001"
    for _ in range(2):
        c.post("/verify", content=f"id={t2}&code={bad}", headers={"content-type": "application/x-www-form-urlencoded"})
    r = c.post("/verify", content=f"id={t2}&code={bad}", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("locked" in r.headers["location"] and "try=" not in r.headers["location"], "third wrong code locks, back to form")
    r = c.post("/try", content="name=Sita&phone=9123456789&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("locked" in r.headers["location"], "locked number refused")

    print("nightly cap (4 calls)")
    r = c.post("/try", content="name=Mo&phone=9988776655&at=23:00", headers={"content-type": "application/x-www-form-urlencoded"})
    ok("No+more+trials" in r.headers["location"], "cap reached after 4 code calls")

    print("expiry")
    rows = trials.load(); rows[0]["created"] -= 3600; trials._save(rows)
    ok("expired" in trials.speak_text(tid), "stale code call says expired")

    print("scheduler tick")
    now = datetime.now()
    due = datetime.fromtimestamp(trials.get(tid)["due"])
    placed = []
    async def fake_place(driver, kind):
        placed.append((driver["name"], kind)); return "completed"
    scheduler.place_call = fake_place
    async def ticks():
        a = scheduler.tick(due + timedelta(minutes=1)); await asyncio.sleep(0)
        b = scheduler.tick(due + timedelta(minutes=2)); c_ = scheduler.tick(due - timedelta(minutes=30)); await asyncio.sleep(0)
        return a, b, c_
    a, b, c_ = asyncio.run(ticks())
    ok(a == [f"+919876543210@{due:%Y-%m-%d %H:%M}"], "tick starts the verified trial at its due time")
    ok(placed == [("Ravi", "checkin")], "placed as a check-in call for Ravi")
    ok(b == [] and c_ == [], "not started twice, not started before due")

    print("due_at")
    n = datetime(2026, 10, 31, 23, 0)
    ok(trials.due_at("23:30", n).day == 31, "later tonight -> today")
    ok(trials.due_at("22:50", n).day == 31, "10 min ago -> now (grace)")
    ok(trials.due_at("22:00", n).day == 1, "an hour ago -> tomorrow")

print("missed calls")
from hoshiyar import records, fleet
records.save_missed("Ravi", "checkin", "busy", 2, time.time())
html = fleet.render()
ok("Did not answer" in html and "busy &times;2" in html, "a busy-after-redial call shows as Did not answer and busy x2")
ok("Need attention now</label><b>1</b>" in html, "a missed driver counts as needing attention")

print(f"\n{passed} checks passed")
