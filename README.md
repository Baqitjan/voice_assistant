# LOQ-GENESIS 🤖

Персональный модульный ИИ-агент для Бахыта.  
**Lenovo LOQ | RTX 4060 8GB | 24GB RAM | Windows 11 | CUDA 12.4**

---

## Структура проекта

```
loq-genesis/
├── main.py                  # Центральный хаб, главный цикл
├── requirements.txt         # Зависимости pip
├── install.bat              # Установщик Windows
├── config/
│   ├── __init__.py
│   └── settings.py          # Все константы и пути
├── engine/
│   ├── __init__.py
│   ├── ear.py               # VAD + Faster-Whisper (GPU)
│   ├── brain.py             # Ollama LLM + память диалога
│   ├── mouth.py             # Kokoro TTS / XTTS v2
│   └── vision.py            # Скриншот + LLaVA анализ
├── tools/
│   ├── __init__.py
│   ├── pc_control.py        # Управление Windows
│   ├── web_search.py        # DuckDuckGo поиск
│   └── scheduler.py         # Напоминания
├── data/
│   ├── my_voice.wav         # Референс голоса (запишите сами, 5-10 сек)
│   └── screenshot.png       # Авто-генерируется
├── logs/
│   └── loq_genesis.log
└── kokoro-v0_19.onnx        # Скачать вручную
    voices.bin               # Скачать вручную
```

---

## Быстрый старт

### 1. Установка

```bat
# Запустить установщик (от имени администратора):
.\install.bat
```

### 2. Ollama модели

```bash
ollama pull llama3.1:8b
ollama pull kazllm
ollama pull llava:7b
```

### 3. Файлы Kokoro TTS

Скачай [отсюда](https://github.com/thewh1teagle/kokoro-onnx/releases):
- `kokoro-v0_19.onnx`
- `voices.bin`

Положи в корень проекта.

### 4. Запись голоса (для клонирования)

Запишите 5–10 секунд речи в WAV 22050 Hz моно:
```python
import sounddevice as sd
import soundfile as sf
audio = sd.rec(int(8 * 22050), samplerate=22050, channels=1)
sd.wait()
sf.write("data/my_voice.wav", audio, 22050)
```

### 5. Запуск

```bash
python main.py
```

---

## Голосовые команды

| Команда | Действие |
|---|---|
| `Ассистент` | Wake-word, активация |
| `что на экране?` | Скриншот + анализ через LLaVA |
| `найди [запрос]` | Веб-поиск DuckDuckGo |
| `напомни через 10 минут [о чём]` | Напоминание |
| `напомни в 14:30 [о чём]` | Напоминание в определённое время |
| `говори моим голосом` | Переключение на XTTS v2 (клон) |
| `статус` | Статус агента |
| `забудь всё` | Очистить историю диалога |

---

## Формат ACTION-команд

LLM возвращает команды для ПК в формате:
```
[ACTION: {"cmd": "open_app", "args": "notepad"}]
```

Доступные `cmd`:
- `open_app` — открыть приложение
- `close_app` — закрыть процесс
- `type_text` — напечатать текст
- `press_key` — нажать клавишу
- `hotkey` — комбинация клавиш (ctrl+c)
- `move_mouse` — переместить мышь (x,y)
- `click` — клик (x,y,button)
- `screenshot` — сделать скриншот
- `run_cmd` — выполнить консольную команду

---

## Требования

- Python 3.10+
- CUDA 12.4
- PyTorch 2.6.0+cu124
- Ollama запущен (`ollama serve`)
- Микрофон подключён
