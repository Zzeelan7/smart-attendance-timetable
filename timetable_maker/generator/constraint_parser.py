"""
constraint_parser.py — Translates natural language scheduling constraints
into structured JSON rules using the Google Gemini API.

No extra packages needed — uses only the built-in `requests` library.
"""

import os
import json
import requests
from pathlib import Path

# Load .env from project root so GEMINI_API_KEY is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-2.0-flash:generateContent"
)

_PROMPT = """\
You are a university timetable scheduling constraint parser.
Convert the natural language constraint below into a single JSON rule object.

Available actions:
  block_teacher_day      — Block a teacher on a specific day
    Required: teacher (str), day (Monday‥Friday), periods ([0‥5] or "all")
  block_teacher_period   — Block a teacher from one period on ALL days
    Required: teacher (str), period (int 0‥5)
  only_available_days    — Teacher is ONLY available on listed days
    Required: teacher (str), days ([day names])
  max_classes_per_day    — Override daily teaching limit for a teacher
    Required: teacher (str), limit (int 1‥6)
  no_consecutive         — Teacher must not have back-to-back classes
    Required: teacher (str)
  block_section_day      — Block a section/semester from having classes at given times
    Required: day (str), periods ([0‥5] or "all"),
              semester (sem number as str, or "all"), section ("A"/"B"/"all")
  unknown                — Cannot parse this constraint
    Required: reason (str)

Period numbers:
  0 = 9:00–10:00  (P1)   1 = 10:00–11:00 (P2)   2 = 11:15–12:15 (P3)
  3 = 12:15–1:15  (P4)   4 = 2:00–3:00   (P5)   5 = 3:00–4:00   (P6)
"Morning" = [0,1,2]   "Afternoon" = [3,4,5]   "All day" = [0,1,2,3,4,5]

Rules:
- Respond with ONLY a valid JSON object. No markdown, no explanation.
- If a teacher name appears in the text, preserve it exactly as written.

Examples:
  "Dr. Shashi unavailable on Wednesday"
  → {"action":"block_teacher_day","teacher":"Dr. Shashi","day":"Wednesday","periods":[0,1,2,3,4,5]}

  "Keep Friday afternoons free for Sem 4 Section A"
  → {"action":"block_section_day","day":"Friday","periods":[3,4,5],"semester":"4","section":"A"}

  "Dr. Priya should not have back-to-back classes"
  → {"action":"no_consecutive","teacher":"Dr. Priya"}

  "Dr. Kumar can teach max 3 periods per day"
  → {"action":"max_classes_per_day","teacher":"Dr. Kumar","limit":3}

  "No classes on Monday morning for all sems"
  → {"action":"block_section_day","day":"Monday","periods":[0,1,2],"semester":"all","section":"all"}

  "Dr. Mehta only available on Tuesdays and Thursdays"
  → {"action":"only_available_days","teacher":"Dr. Mehta","days":["Tuesday","Thursday"]}

Now parse this constraint:
"""


# ── API key helpers ────────────────────────────────────────────────

def _config_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ai_config.json'
    )

def load_api_key() -> str:
    """Return Gemini API key from env-var or ai_config.json."""
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if key:
        return key
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f).get('gemini_api_key', '').strip()
        except Exception:
            pass
    return ''

def save_api_key(key: str):
    """Persist Gemini API key to ai_config.json."""
    with open(_config_path(), 'w', encoding='utf-8') as f:
        json.dump({'gemini_api_key': key.strip()}, f)


# ── Core parser ───────────────────────────────────────────────────

def parse_constraint(text: str, api_key: str = '') -> dict:
    """Send one constraint text to Gemini. Returns a structured rule dict."""
    api_key = api_key or load_api_key()
    if not api_key:
        return {
            'action': 'unknown',
            'reason': 'Gemini API key not configured',
            'original': text,
        }

    prompt = _PROMPT + f'"{text}"'
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 300},
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()

        # Strip markdown fences if Gemini wraps the JSON
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        raw = raw.strip()

        rule = json.loads(raw)
        rule['original'] = text
        return rule

    except requests.exceptions.Timeout:
        return {'action': 'unknown', 'reason': 'Gemini API timed out', 'original': text}
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else 0
        msg = 'Invalid API key — check your Gemini key' if code in (400, 403) else f'HTTP {code}'
        return {'action': 'unknown', 'reason': msg, 'original': text}
    except requests.exceptions.RequestException as e:
        return {'action': 'unknown', 'reason': f'Network error: {e}', 'original': text}
    except (json.JSONDecodeError, KeyError, IndexError):
        return {'action': 'unknown', 'reason': 'AI returned an unreadable response', 'original': text}


def parse_all_constraints(custom_list: list, api_key: str = '') -> list:
    """
    Parse every item in custom_list.
    Each item is either a str or a dict with keys: text, type (hard/soft).
    Returns a list of rule dicts, each with an 'original' and 'constraint_type' key.
    """
    rules = []
    for item in custom_list:
        if isinstance(item, dict):
            text = item.get('text', '').strip()
            ctype = item.get('type', 'soft')
        else:
            text = str(item).strip()
            ctype = 'soft'
        if not text:
            continue
        rule = parse_constraint(text, api_key)
        rule['constraint_type'] = ctype
        rules.append(rule)
    return rules
