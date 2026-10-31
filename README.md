# Hoshiyar

**A voice co-driver for long-haul truck drivers.** It phones the driver through the night in his own language,
hears how tired he is, keeps him talking, gets him to stop when it is not safe, and tells his fleet.
Nothing goes into the cab: it works on the phone the driver already has.

![Hoshiyar homepage](docs/home.jpg)

**Live:** [ow2xj.aiccloud.online](https://ow2xj.aiccloud.online) · **Fleet screen:** [/fleet](https://ow2xj.aiccloud.online/fleet)
(press *Try it now* to get a real check-in call on your own phone)

---

## The problem

| | |
|---|---|
| **1 in 5** | Trucks were the striking vehicle in 32,362 of India's 1,77,175 road deaths in 2024. |
| **49%** | Truck drivers who say they drive even when sleepy, after 11.9 hours at the wheel a day. |
| **2028** | The year India makes drowsiness warning (AIS-184) mandatory, and only on new trucks. Today's fleet gets nothing. |

Fatigue has no box on an Indian accident form, so most of these deaths are booked as over-speeding.

## A call

```
Hoshiyar  नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?          Hello, Hoshiyar here. How are you?
Driver    भाई, बहुत नींद आ रही है।                               Brother, I am very sleepy.
Hoshiyar  अगले ढाबे पर बीस मिनट रुक जाओ। तब तक बताओ,         Stop for twenty minutes at the next dhaba.
          राजस्थान की राजधानी क्या है?                           Till then: what is the capital of Rajasthan?
Driver    जयपुर।                                                  Jaipur.
```

*Illustrative. The bot's lines and the question come from the real persona and question bank.*

Behind the scenes, that call recorded a HEAVY sleepiness score and rang the fleet manager with a spoken alert.
Once the driver agrees to stop, a wake-up call is booked for twenty minutes later. The fleet manager sees it here:

![Fleet screen](docs/fleet.jpg)

## How it works

```
Vobiz phone call ──wss──▶ FastAPI /ws ──▶ Pipecat pipeline
   Sarvam STT (saaras:v3) ▶ turn-taking ▶ Gemma 4 on Sarvam, with tools ▶ Sarvam TTS (bulbul:v3)
```

1. **Rota.** The scheduler rings each driver at his check-in times, redials on busy or no answer, and survives restarts.
2. **Score.** From the driver's own words the model records sleepiness from 1 to 9 and picks a mode:
   QUIET (one line, then silence), MILD (light talk), HEAVY (a break order, then a rapid quiz).
3. **Listen.** Reply delay is measured on every turn. If it climbs over the call, the bot asks again, whatever he says.
4. **Escalate.** A sleepy driver who ignores two nudges is marked unresponsive. HEAVY, unresponsive and break
   events each phone the fleet manager.
5. **Wake up.** After a break the driver gets a call back to check he is fit to drive on.

## Engineering notes

- **Language switch mid-call.** Calls open in Hindi. If the driver answers in Telugu, Kannada, Marathi or English,
  the model offers those, and one tool call switches speech-to-text, text-to-speech and the persona together
  without hanging up. The Hindi path is pinned by a baseline test.
- **Barge-in that ignores "haan".** The driver interrupts only after three words, so a background "hmm" or
  "ji" does not cut the bot off mid-sentence.
- **Reply-delay drift.** It needs both an absolute and a relative rise against the driver's own baseline, so a
  naturally slow talker is not flagged ([`signals.py`](src/hoshiyar/signals.py)).
- **No invented facts.** HEAVY quizzes come from a fixed bank per language (capitals, old films, roads), with
  no arithmetic, because working-memory puzzles hurt driving.
- **Voice OTP.** The *Try* button reads a four-digit code to your phone before it books a call, with limits on
  attempts, bookings and calls per night.
- **Measured on real calls:** first word 0.35 s after pickup; 0.6 s from the driver finishing to the reply
  starting. At list prices, three calls a night cost under ₹1,000 per driver per month.

The design follows the alertness literature: a trivia task kept truck drivers alert in a simulator
(Oron-Gilad et al. 2008), and fatigued drivers want stimulating talk while alert ones want silence. Hence the
default is quiet.

## Run it yourself

You need Python 3.12, [uv](https://docs.astral.sh/uv/), and Sarvam and Vobiz accounts.

```sh
cp .env.example .env                  # fill in the keys
uv sync
ngrok http 7860                       # put the https URL in LOCAL_SERVER_URL
uv run python -m hoshiyar.server      # http://localhost:7860 and /fleet
```

The roster is `data/drivers.json` (copy `drivers.example.json`); add `"lang": "te"` to a driver to fix his language.
For a small VPS deployment, see [`deploy.md`](deploy.md).

**Tests.** These check the Try flow, the scheduler and the language switch, and place no calls:

```sh
uv run python tests/test_trials.py
uv run python tests/test_langs.py
```

## Sources

MoRTH, *Road Accidents in India 2024* · PIB release 2227148 (12 Feb 2026), safety devices for heavy vehicles ·
SaveLIFE Foundation, *Status of Truck Drivers in India* (2020) · AAA Foundation for Traffic Safety, *Prevalence
of Drowsy Driving Crashes* · Oron-Gilad, Ronen & Shinar (2008) · Atchley, Chan & Gregersen (2014).
