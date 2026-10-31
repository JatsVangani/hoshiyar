"""The languages Hoshiyar speaks besides Hindi, and the fixed lines it says in each.

Hindi stays in brain.py exactly as it was; this module only adds Telugu, Kannada, Marathi and English.
A call runs in one language at a time: the roster or the Try form can fix it, or "auto" (the default)
starts in Hindi and offers these choices the first time the driver answers in one of them.
Strings here are first drafts for a native speaker to correct; the keys are what the code depends on.
"""

DEFAULT = "auto"  # start in Hindi, switch if the driver speaks one of the others
SUPPORTED = ("hi", "te", "kn", "mr", "en")

# Spoken lines per language. Hindi values are filled in from brain.py at import so there is one source.
STRINGS: dict[str, dict[str, str]] = {
    "te": {
        "name": "తెలుగు",
        "code": "te-IN",
        "opener_checkin": "నమస్కారం, నేను హోషియార్ మాట్లాడుతున్నాను. మీరు ఎలా ఉన్నారు?",
        "opener_wakeup": "లేవండి అన్నా, ఇరవై నిమిషాలు అయ్యాయి. హోషియార్ మాట్లాడుతున్నాను. ముందుకు వెళ్ళడానికి సిద్ధమా?",
        "check_in": "నిద్ర రావడం లేదు కదా? కళ్ళు బరువుగా లేవు కదా?",
        "first_nudge": "హలో, వినిపిస్తోందా? ",
        "nudge": "మళ్ళీ అడుగుతున్నాను, ",
        "nudge_heavy": "అన్నా! వింటున్నారా? మాట్లాడండి, జవాబు చెప్పండి!",
        "alarm": "బండి పక్కన ఆపండి, ఇప్పుడే! అన్నా, మాట్లాడండి!",
        "drift": "అన్నా, జవాబు చెప్పడానికి ఇప్పుడు ఆలస్యం అవుతోంది. నిజం చెప్పండి, నిద్ర వస్తోందా?",
        "menu": "నేను హిందీ, తెలుగు, కన్నడ, మరాఠీ, ఇంగ్లీష్ మాట్లాడగలను. మీకు ఏ భాష కావాలి?",
        "note": "Ab se sirf Telugu mein baat karo aur Telugu script mein likho. 'Bhai' ki jagah 'anna' bolo. "
                "Baaki sab niyam waise hi: chhote vaakya, koi lecture nahi, jo nahi pata woh mat banao. Driver doosri bhasha maange toh switch_language call karo; ek jawab mein bhashaon ko mat milao.",
    },
    "kn": {
        "name": "ಕನ್ನಡ",
        "code": "kn-IN",
        "opener_checkin": "ನಮಸ್ಕಾರ, ನಾನು ಹೋಶಿಯಾರ್ ಮಾತಾಡ್ತಿದ್ದೀನಿ. ನೀವು ಹೇಗಿದ್ದೀರಾ?",
        "opener_wakeup": "ಏಳಿ ಅಣ್ಣಾ, ಇಪ್ಪತ್ತು ನಿಮಿಷ ಆಯ್ತು. ಹೋಶಿಯಾರ್ ಮಾತಾಡ್ತಿದ್ದೀನಿ. ಮುಂದೆ ಹೋಗೋಕೆ ರೆಡಿನಾ?",
        "check_in": "ನಿದ್ದೆ ಬರ್ತಿಲ್ಲ ತಾನೇ? ಕಣ್ಣು ಭಾರ ಆಗಿಲ್ಲ ತಾನೇ?",
        "first_nudge": "ಹಲೋ, ಕೇಳಿಸ್ತಿದೆಯಾ? ",
        "nudge": "ಮತ್ತೆ ಕೇಳ್ತಿದ್ದೀನಿ, ",
        "nudge_heavy": "ಅಣ್ಣಾ! ಕೇಳಿಸ್ತಿದೆಯಾ? ಮಾತಾಡಿ, ಉತ್ತರ ಕೊಡಿ!",
        "alarm": "ಗಾಡಿ ಬದಿಗೆ ನಿಲ್ಲಿಸಿ, ಈಗಲೇ! ಅಣ್ಣಾ, ಮಾತಾಡಿ!",
        "drift": "ಅಣ್ಣಾ, ಉತ್ತರ ಕೊಡೋಕೆ ಈಗ ತಡ ಆಗ್ತಿದೆ. ನಿಜ ಹೇಳಿ, ನಿದ್ದೆ ಬರ್ತಿದೆಯಾ?",
        "menu": "ನಾನು ಹಿಂದಿ, ತೆಲುಗು, ಕನ್ನಡ, ಮರಾಠಿ, ಇಂಗ್ಲಿಷ್ ಮಾತಾಡಬಲ್ಲೆ. ನಿಮಗೆ ಯಾವ ಭಾಷೆ ಬೇಕು?",
        "note": "Ab se sirf Kannada mein baat karo aur Kannada script mein likho. 'Bhai' ki jagah 'anna' bolo. "
                "Baaki sab niyam waise hi: chhote vaakya, koi lecture nahi, jo nahi pata woh mat banao. Driver doosri bhasha maange toh switch_language call karo; ek jawab mein bhashaon ko mat milao.",
    },
    "mr": {
        "name": "मराठी",
        "code": "mr-IN",
        "opener_checkin": "नमस्कार, मी होशियार बोलतोय. तुम्ही कसे आहात?",
        "opener_wakeup": "उठा भाऊ, वीस मिनिटं झाली. होशियार बोलतोय. पुढे जायला तयार आहात का?",
        "check_in": "झोप येत नाहीये ना? डोळे जड झाले नाहीत ना?",
        "first_nudge": "हॅलो, ऐकू येतंय का? ",
        "nudge": "पुन्हा विचारतोय, ",
        "nudge_heavy": "भाऊ! ऐकताय का? बोला, उत्तर द्या!",
        "alarm": "गाडी बाजूला लावा, आत्ता! भाऊ, बोला!",
        "drift": "भाऊ, उत्तर द्यायला आता उशीर होतोय. खरं सांगा, झोप येतेय का?",
        "menu": "मी हिंदी, तेलुगू, कन्नड, मराठी किंवा इंग्रजी बोलू शकतो. तुम्हाला कोणती भाषा हवी?",
        "note": "Ab se sirf Marathi mein baat karo aur Devanagari mein likho. 'Bhai' ki jagah 'bhau' bolo. "
                "Baaki sab niyam waise hi: chhote vaakya, koi lecture nahi, jo nahi pata woh mat banao. Driver doosri bhasha maange toh switch_language call karo; ek jawab mein bhashaon ko mat milao.",
    },
    "en": {
        "name": "English",
        "code": "en-IN",
        "opener_checkin": "Hello, this is Hoshiyar. How are you doing?",
        "opener_wakeup": "Wake up bhai, it has been twenty minutes. Hoshiyar here. Ready to drive on?",
        "check_in": "Not feeling sleepy? Eyes not getting heavy?",
        "first_nudge": "Hello, can you hear me? ",
        "nudge": "Asking again, ",
        "nudge_heavy": "Bhai! Can you hear me? Talk to me, answer!",
        "alarm": "Pull over, right now! Bhai, talk to me!",
        "drift": "Bhai, you are taking longer to answer now. Tell me honestly, are you getting sleepy?",
        "menu": "I can speak Hindi, Telugu, Kannada, Marathi or English. Which do you prefer?",
        "note": "Ab se sirf Indian English mein baat karo, Roman script mein. 'Bhai' chal sakta hai. "
                "Baaki sab niyam waise hi: short sentences, no lectures, never invent what you do not know. Driver doosri bhasha maange toh switch_language call karo; ek jawab mein bhashaon ko mat milao.",
    },
}

HINDI_MENU = "मैं हिंदी, तेलुगु, कन्नड़, मराठी या अंग्रेज़ी बोल सकता हूँ। आप कौन सी भाषा चाहते हो?"

# What the Hindi-first call is told on top of the normal persona. Only in "auto" mode.
AUTO_NOTE = (
    "Agar driver ka koi poora jawab (pehla ya baad ka) Hindi ke bajaye Telugu, Kannada, Marathi ya English mein ho, toh kuch aur "
    "bolne se pehle offer_languages tool call karo (detected mein te, kn, mr ya en). Ek-do shabd ya galat sune "
    "shabd par mat karo, poora vaakya dusri bhasha mein ho tabhi. Driver jab bhasha chune, switch_language call "
    "karo. Driver Hindi hi bole toh kuch mat badlo. "
)


def spoken(lang: str, key: str) -> str:
    """One fixed line in the language of the call. Hindi and auto read brain.py's own strings."""
    from hoshiyar import brain  # late import: brain imports this module

    if lang in STRINGS:
        s = STRINGS[lang]
        if key == "nudge":
            return s["nudge"] + s["check_in"]
        if key == "first_nudge":
            return s["first_nudge"] + s["check_in"]
        return s[key]
    return {
        "opener_checkin": brain.OPENERS["checkin"],
        "opener_wakeup": brain.OPENERS["wakeup"],
        "check_in": brain.CHECK_IN,
        "first_nudge": "हैलो, सुनाई दे रहा है? " + brain.CHECK_IN,
        "nudge": brain.NUDGES["QUIET"],
        "nudge_heavy": brain.NUDGES["HEAVY"],
        "alarm": brain.ALARM,
        "drift": brain.DRIFT_LINE,
        "menu": HINDI_MENU,
        "name": "हिंदी",
        "code": "hi-IN",
    }[key]


def code(lang: str) -> str:
    """Sarvam language code for STT and TTS. Auto starts as Hindi."""
    return STRINGS[lang]["code"] if lang in STRINGS else "hi-IN"


def name(lang: str) -> str:
    return STRINGS[lang]["name"] if lang in STRINGS else "हिंदी"
