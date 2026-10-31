"""Language tests. Run from the repo root: uv run python tests/test_langs.py

Proves the Hindi call is unchanged against a saved baseline (tests/fixtures/hindi_baseline.json), then checks
the language tables, the offer and switch tools on a language-flexible call, bookings, records and the page.
No calls are placed. Regenerate the baseline only when a Hindi prompt change is deliberate."""

import asyncio, json, os, sys, tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ.update({"TRIALS_FILE": str(tmp / "trials.json"), "CALLS_FILE": str(tmp / "calls.jsonl"),
                   "ROSTER_FILE": str(tmp / "drivers.json"), "SCHEDULE_FILE": str(tmp / "schedule.json")})

from hoshiyar import brain, langs, trivia, trials, records, fleet

passed = 0
def ok(cond, what):
    global passed
    assert cond, what; passed += 1; print("  ok", what)

base = json.loads((Path(__file__).parent / "fixtures" / "hindi_baseline.json").read_text(encoding="utf-8"))

print("hindi path unchanged")
ok(brain.persona_for("checkin", "hi") == base["persona_checkin"], "check-in persona matches the baseline")
ok(brain.persona_for("wakeup", "hi") == base["persona_wakeup"], "wake-up persona matches the baseline")
ok(langs.spoken("hi", "opener_checkin") == base["opener_checkin"] and langs.spoken("hi", "opener_wakeup") == base["opener_wakeup"], "openers match")
st = brain.CallState(); out = [brain.nudge_for(st)]
st.driver_turns = 1; st.unanswered = 0; st.mode = "QUIET"; out.append(brain.nudge_for(st))
st.mode = "MILD"; out.append(brain.nudge_for(st))
st.mode = "HEAVY"; st.unanswered = 0; out.append(brain.nudge_for(st))
st.drift = "drifting"; out.append(brain.nudge_for(st))
st.unanswered = 1; st.alerts.append((0, "[UNRESPONSIVE] x")); out.append(brain.nudge_for(st))
ok(out == base["nudges"], "first nudge, QUIET, MILD, HEAVY, drift line, alarm match")
ok([t.__name__ for t in brain.make_tools(brain.CallState(lang="hi"))] == base["tools"], "a Hindi call has the same three tools")
ok(brain.persona_for("checkin", "auto") == brain.persona_for("checkin", "hi") + langs.AUTO_NOTE, "auto = Hindi persona plus the offer rule only")

print("tables")
keys = {"name", "code", "opener_checkin", "opener_wakeup", "check_in", "first_nudge", "nudge", "nudge_heavy", "alarm", "drift", "menu", "note"}
for lang in ("te", "kn", "mr", "en"):
    ok(set(langs.STRINGS[lang]) == keys and all(langs.STRINGS[lang].values()), f"{lang}: every line present")
    ok(langs.code(lang) == f"{lang}-IN", f"{lang}: Sarvam code")
    ok(len(trivia.fresh([], lang=lang)) == 5 and trivia.fresh([], lang=lang)[0] in [dict(q=i["q"], a=i["a"]) for i in trivia.BANKS[lang]], f"{lang}: trivia from its own bank")
ok(trivia.fresh([], lang="hi")[0]["q"] in {i["q"] for i in trivia.BANK} and trivia.fresh([], lang="auto")[0]["q"] in {i["q"] for i in trivia.BANK}, "hi and auto draw from the Hindi bank")
ok(langs.spoken("te", "nudge").endswith(langs.STRINGS["te"]["check_in"]) and langs.spoken("kn", "first_nudge").startswith("ಹಲೋ"), "composed nudges")

print("tools on an auto call")
class FakeLLM:
    def __init__(self): self.frames = []; self.notes = []
    async def push_frame(self, frame, direction=None): self.frames.append((type(frame).__name__, frame, direction))
    def append_system_instruction(self, text): self.notes.append(text)
class Params:
    def __init__(self, llm): self.llm = llm; self.results = []
    async def result_callback(self, result, properties=None): self.results.append((result, properties))
state = brain.CallState(lang="auto")
tools = {t.__name__: t for t in brain.make_tools(state)}
llm = FakeLLM(); p = Params(llm)
asyncio.run(tools["offer_languages"](p, detected="te"))
names = [f[0] for f in llm.frames]
ok(names == ["TTSUpdateSettingsFrame", "TTSSpeakFrame"] and llm.frames[0][1].delta.language == "te-IN", "offer: TTS switched to Telugu before the menu")
ok(llm.frames[1][1].text == langs.STRINGS["te"]["menu"] and p.results[0][1].run_llm is False, "offer: Telugu menu spoken, model told to wait")
ok(state.offered and state.lang == "auto", "offer: marked offered, language not yet switched")
asyncio.run(tools["offer_languages"](p, detected="kn"))
ok(p.results[-1][0]["status"] == "already offered" and len(llm.frames) == 2, "offer: second offer refused")
llm2 = FakeLLM(); p2 = Params(llm2)
asyncio.run(tools["switch_language"](p2, lang="kn"))
kinds = {(f[0], f[2]) for f in llm2.frames}
ok(state.lang == "kn" and ("TTSUpdateSettingsFrame", None) in kinds and ("STTUpdateSettingsFrame", brain.FrameDirection.UPSTREAM) in kinds, "switch: state, TTS downstream, STT upstream")
ok(all(f[1].delta.language == "kn-IN" for f in llm2.frames), "switch: both frames carry kn-IN")
ok(llm2.notes == [langs.STRINGS["kn"]["note"]] and langs.STRINGS["kn"]["check_in"] in p2.results[0][0]["instructions"], "switch: persona note appended, Kannada check-in in the result")
st2 = state; st2.driver_turns = 1; st2.mode = "HEAVY"; st2.unanswered = 0
ok(brain.nudge_for(st2) == langs.STRINGS["kn"]["nudge_heavy"], "nudges now in Kannada")
asyncio.run(tools["switch_language"](p2, lang="xx"))
ok("error" in p2.results[-1][0] and state.lang == "kn", "switch: unknown language refused")
s3 = brain.CallState(lang="te"); t3 = {t.__name__ for t in brain.make_tools(s3)}
ok("offer_languages" not in t3 and brain.persona_for("checkin", "te").endswith(langs.STRINGS["te"]["note"]), "fixed Telugu call: no menu tools, Telugu note in persona")

print("bookings, records, page")
e = trials.create("Priya", "9876543210", "23:05", lang="mr"); trials.note_call(e["id"])
ok(e["lang"] == "mr" and trials.create("Dev", "9123456789", "23:10", lang="zz")["lang"] == "auto", "trial language stored, unknown falls back to auto")
trials.verify(e["id"], e["code"]); ok(trials.drivers()[0]["lang"] == "mr", "verified trial carries its language to the rota")
rec = records.save(brain.CallState(lang="te", driver="Priya"), "checkin"); ok(rec["lang"] == "te", "record carries the language")
html = fleet.render()
ok("<select name='lang'>" in html and "value='te'>Telugu" in html, "form has the language choice")
ok("&middot; తెలుగు" in html and "checkin - te" in html, "card and log show the call's language")
print(f"\n{passed} checks passed")
