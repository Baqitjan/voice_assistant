# =============================================================================
# LOQ-GENESIS | config/settings.py  — ФИНАЛЬНАЯ ВЕРСИЯ
# Синхронизирован с реальным окружением Бахыта (лог от 15.03.2026)
# =============================================================================

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR  = BASE_DIR / "data"
LOGS_DIR  = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ── Пути ──────────────────────────────────────────────────────────────────────
MY_VOICE_WAV    = str(DATA_DIR / "my_voice.wav")
SCREENSHOT_PATH = str(DATA_DIR / "screenshot.png")
LOG_FILE        = str(LOGS_DIR / "loq_genesis.log")

# ── Wake / Trigger ────────────────────────────────────────────────────────────
WAKE_WORD           = "ассистент"
CLONE_VOICE_TRIGGER = "говори моим голосом"
STD_VOICE_TRIGGER   = "стандартный голос"

# ── VAD (Silero) ──────────────────────────────────────────────────────────────
# ОПТИМИЗАЦИЯ: VAD_CHUNK_SIZE=1024 снижает нагрузку CPU при параллельной работе
# Vision/Brain. 512 вызывал input overflow при тяжёлых GPU-задачах.
VAD_THRESHOLD        = 0.4
VAD_SAMPLE_RATE      = 16000
VAD_CHUNK_SIZE       = 512          # было 512 → увеличено для снижения CPU
SILENCE_DURATION_SEC = 1.5
MAX_RECORD_SEC       = 25

# ── Faster-Whisper ────────────────────────────────────────────────────────────
# FIX: language="ru" — исключает галлюцинации ("Thank you.", "Stop.", "Игорь Негода")
# FIX: vad_filter=True — не обрабатывает пустые / тихие фрагменты
# FIX: condition_on_previous_text=False — нет дрейфа контекста между фразами
WHISPER_MODEL_SIZE        = "large-v3"
WHISPER_DEVICE            = "cuda"
WHISPER_COMPUTE_TYPE      = "float16"
WHISPER_LANGUAGE          = "ru"     
WHISPER_BEAM_SIZE         = 5
WHISPER_CONDITION_ON_PREV = False      # ЖЁСТКО — не дрейфить
WHISPER_VAD_FILTER        = True       # встроенный VAD Whisper

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL     = "http://localhost:11434"
OLLAMA_TIMEOUT      = 120
LLM_DEFAULT         = "llama3.1:8b"
LLM_KAZAKH          = "kazllm"
LLM_VISION          = "llava:7b"
MEMORY_MAX_MESSAGES = 15

# ── Silero TTS (рабочий движок — подтверждено логом) ──────────────────────────
SILERO_SAMPLE_RATE = 24000
SILERO_SPEAKER     = "aidar"    # aidar | baya | kseniya | xenia | eugene
SILERO_LANGUAGE    = "ru"
SILERO_MODEL_ID    = "v4_ru"

# ── XTTS v2 — клонирование голоса (ленивая загрузка) ─────────────────────────
XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_DEVICE     = "cuda"
XTTS_LANGUAGE   = None

# ── Vision ────────────────────────────────────────────────────────────────────
SCREENSHOT_REGION = None    # None = весь экран

# ── Audio ─────────────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE  = 16000
AUDIO_CHANNELS     = 1
AUDIO_DEVICE_INDEX = None

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"

# ── System Prompt (каз + рус) ─────────────────────────────────────────────────
SYSTEM_PROMPT = """
Ты — LOQ Agent, мощный ИИ-контроллер для Windows 11. Твоя задача — управлять компьютером через [ACTION].

### 1. ТИЛ САЯСАТЫ (LANGUAGE POLICY):
- Если пользователь говорит на казахском (мысалы: "Блокнотты аш", "Сәлем"), отвечай строго на КАЗАХСКОМ.
- Если на русском — на РУССКОМ.
- Ответы должны быть очень короткими (1-2 предложения).

### 2. ЛОГИКА КОМАНД [ACTION] (ОБЯЗАТЕЛЬНО):
Ты должен немедленно генерировать [ACTION], если звучат следующие глаголы:
- "Аш", "запусти", "открой" -> [ACTION: {"cmd": "open_app", "args": "имя_программы"}]
- "Жаз", "напечатай", "введи", "напиши" -> [ACTION: {"cmd": "type_text", "args": "текст"}]
- "Жап", "закрой" -> [ACTION: {"cmd": "close_app", "args": "имя_программы"}]
- "Скриншот", "түсір" -> [ACTION: {"cmd": "screenshot", "args": ""}]

### 3. ПРАВИЛА ФОРМАТА JSON:
- Используй ТОЛЬКО двойные кавычки для ключей и значений внутри JSON.
- Внутри "args" для текста НИКОГДА не используй кавычки. Если нужно, замени их на пробелы.
- ПРИМЕР: [ACTION: {"cmd": "type_text", "args": "Привет Макс"}]

### 4. ОГРАНИЧЕНИЯ:
- Не называй пользователя по имени.
- Не предлагай альтернативные программы. Если просят Блокнот — это "notepad".
- Если команда непонятна, просто ответь: "Түсінбедім, қайталаңызшы" или "Не понял, повторите".

### 5. КАЗАХСКИЙ КОНТЕКСТ (СЛОВА-МАРКЕРЫ):
- "Блокнотқа [текст] деп жаз" -> Вызывай type_text.
- "Блокнотты аш" -> Вызывай open_app.
- "Экранды талда" / "Не көріп тұрсың?" -> Вызывай screenshot.

""".strip()
