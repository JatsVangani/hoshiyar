# Hoshiyar

A voice co-driver for long-haul truck drivers. It calls the driver through the night in his own language,
hears how tired he is, keeps him talking, gets him to stop when it is not safe, and tells his fleet.
No hardware in the cab: every truck on the road tonight is covered with the phone the driver already has.

Live: https://ow2xj.aiccloud.online (homepage) and https://ow2xj.aiccloud.online/fleet (the fleet manager's
screen, with a Try button that books a real call to your own number).

## Why

- Trucks were the striking vehicle in 32,362 of India's 1,77,175 road deaths in 2024, nearly one in five.
  Only 5.5% of those killed were inside the truck. (MoRTH, Road Accidents in India 2024)
- Fatigue has no box on an Indian accident form; 70% of deaths are booked as over-speeding. Where sleep is
  studied properly it sits behind one fatal crash in five. (AAA Foundation)
- Truck drivers drive 11.9 hours a day; 49% say they drive even when sleepy. (SaveLIFE Foundation, 2020)
- India has mandated driver drowsiness warning (AIS-184) on every new truck and bus from 1 January 2028, after
  the EU did the same for all new vehicles in July 2024. The mandate covers vehicles built after 2028 and the
  mandated device only beeps. A phone call needs no retrofit and does what a co-driver does.

## What a call looks like

1. Hoshiyar rings the driver at his check-in times and asks how he is. It opens in Hindi; if the driver answers
   in Telugu, Kannada, Marathi or English it offers those and switches the whole call, speech in and out.
2. From the driver's own words it records a sleepiness score from 1 to 9 and picks a mode: QUIET (a line and
   silence), MILD (light talk with a question now and then), HEAVY (a break order, then a rapid quiz from a bank
   of questions so it never invents facts).
3. It measures how long the driver takes to start answering. Answers that slow down over the call tighten the
   check-in interval and trigger one more honest "are you getting sleepy?", whatever he said.
4. If he goes quiet it re-asks on a timer that shortens with the mode; a sleepy driver who ignores two nudges
   is marked unresponsive.
5. A HEAVY score, an unresponsive driver, or an agreed break each ring the fleet manager with a spoken alert.
   After a break the driver gets a wake-up call twenty minutes later.
6. Every call is written to a record; the fleet page shows each driver's status, score, reply-delay trend,
   alerts and the night's call log, refreshing every 20 seconds.

The design leans on the alertness literature: Oron-Gilad et al. 2008 (a trivia task kept professional truck
drivers alert in a simulator while working-memory tasks hurt driving), Atchley et al. 2014 (a late verbal task
improved lane keeping and EEG alertness) and a 2025 MDPI study (fatigued drivers want stimulating talk, alert
drivers want silence). Hence quiet by default, and no arithmetic in the quiz.

## How it is built

```
Vobiz PSTN call --wss--> FastAPI /ws --> Pipecat pipeline
    transport in -> Sarvam realtime STT (saaras:v3) -> turn-taking (3 words to interrupt, 0.2 s stop)
    -> Gemma 4 on Sarvam with tools -> Sarvam TTS (bulbul:v3) -> transport out
```

- `src/hoshiyar/brain.py`: the persona, modes, nudges and the tools the model calls: `record_sleepiness`,
  `more_questions`, `end_call`, and on language-flexible calls `offer_languages` and `switch_language`.
- `pipeline.py`: the Pipecat pipeline, turn strategies and the silence timer. `signals.py`: reply-delay
  observer and the drift rule. `trivia.py` with one question bank per language.
- `scheduler.py`: the nightly rota from `data/drivers.json`, redial on busy or no-answer, wake-up calls, all
  persisted so a restart forgets nothing. `alerts.py`: the fleet manager's voice alerts, queued one at a time.
- `trials.py` and the Try dialog: a visitor books a call after typing a four-digit code read out to their
  phone, with limits on attempts, bookings and calls per night.
- `fleet.py` and `home.py`: the two pages, server-rendered HTML with no build step.
- `records.py`: one JSON line per call in `data/calls.jsonl`.

Measured on real calls: first word 0.35 s after pickup; 0.6 s from the driver finishing to the reply starting;
Gemma 4 first token 0.1 to 0.4 s. Cost at list prices is under ₹1,000 per driver per month for three calls a night.

## Running it

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), PortAudio (for the laptop mic bot only), and
accounts for Sarvam and Vobiz. Copy `.env.example` to `.env` and fill it in.

```sh
uv sync
ngrok http 7860                      # put the https URL in LOCAL_SERVER_URL in .env
uv run python -m hoshiyar.server     # http://localhost:7860, /fleet
curl -X POST localhost:7860/dialout  # ring MY_PHONE now
```

The roster lives in `data/drivers.json` (see `drivers.example.json`); the rota re-reads it every 20 s. A driver
entry may carry `"lang": "te"` to open the call in that language instead of offering a choice.

Tests: `uv run python scratch/test_trials.py` and `uv run python scratch/test_langs.py` if you have the scratch
folder; they exercise the Try flow, the scheduler tick and the language switch without placing calls.

Deployment on a small VPS is described in `deploy.md`.

## Sources

MoRTH, Road Accidents in India 2024 · PIB release 2227148 (12 Feb 2026) on mandatory safety devices for heavy
vehicles · SaveLIFE Foundation, Status of Truck Drivers in India (2020) · AAA Foundation for Traffic Safety,
Prevalence of Drowsy Driving Crashes · Oron-Gilad, Ronen & Shinar (2008) · Atchley, Chan & Gregersen (2014).
