
import logging
import sys
import threading
import time

from config.settings import LOG_LEVEL, LOG_FILE, WAKE_WORD

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("LOQ-GENESIS")

from engine.ear    import Ear
from engine.brain  import Brain
from engine.mouth  import Mouth
from engine.vision import Vision
from tools.pc_control import PCControl
from tools.web_search  import WebSearch
from tools.scheduler   import Scheduler

# Ключевые слова для маршрутизации
_VISION_KW  = ("что на экране", "посмотри на экран", "что вижу", "анализируй экран", "посмотри экран")
_SEARCH_KW  = ("найди", "поищи", "что такое", "кто такой", "новости о", "поиск")
_REMIND_KW  = ("напомни", "напоминание", "поставь будильник")
_CLEAR_KW   = ("забудь всё", "очисти память", "сбрось историю")
_STATUS_KW  = ("статус", "как дела", "ты работаешь")

BANNER = """
╔══════════════════════════════════════════════════════╗
║  LOQ-GENESIS · Персональный ИИ-агент           ║
║  RTX 4060 · CUDA 12.4 · Silero TTS · Whisper GPU    ║
╚══════════════════════════════════════════════════════╝
"""


class LOQAgent:
    """
    Центральный хаб LOQ-GENESIS.

    Архитектура потоков:
    ┌──────────────────────────────────────────────────────┐
    │  EarCapture (daemon)  → AudioQueue                   │
    │  Scheduler   (daemon) → schedule.run_pending()       │
    │  MainLoop             → listen_for_wake_word()       │
    │                       → listen_command()             │
    │  ProcessCmd  (daemon) → Brain / Vision / Tools       │
    │  MouthSpeak  (daemon) → Silero / XTTS → sounddevice  │
    └──────────────────────────────────────────────────────┘
    """

    def __init__(self):
        print(BANNER)
        logger.info("=" * 60)
        logger.info("Инициализация LOQ-GENESIS...")
        self._running = False

        logger.info("  [1/7] Brain (Ollama)...")
        self.brain = Brain()

        logger.info("  [2/7] Mouth (Silero TTS)...")
        self.mouth = Mouth()

        logger.info("  [3/7] Ear (VAD + Whisper GPU)...")
        self.ear = Ear()

        # Interrupt logic: Ear знает о Mouth
        self.ear.set_mouth(self.mouth)

        logger.info("  [4/7] Vision (Screenshot + LLaVA)...")
        self.vision = Vision()

        logger.info("  [5/7] PCControl...")
        self.pc = PCControl()

        logger.info("  [6/7] WebSearch (DuckDuckGo)...")
        self.search = WebSearch(max_results=5)

        logger.info("  [7/7] Scheduler...")
        self.scheduler = Scheduler(speak_callback=self.mouth.speak)

        logger.info("Все модули загружены.")
        logger.info("=" * 60)

    # ──────────────────────────────────────────────────────────────────────────
    # Запуск / остановка
    # ──────────────────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        self.ear.start()
        self.scheduler.start()

        self.mouth.speak(
            f"Привет! LOQ Agent готов. Скажи «{WAKE_WORD}», чтобы обратиться."
        )
        print(f"\n⚡  Ожидаю wake-word: «{WAKE_WORD}»\n")
        self._main_loop()

    def stop(self):
        self._running = False
        self.ear.stop()
        self.scheduler.stop()
        logger.info("LOQ-GENESIS остановлен.")

    # ──────────────────────────────────────────────────────────────────────────
    # Главный цикл
    # ──────────────────────────────────────────────────────────────────────────

    def _main_loop(self):
        while self._running:
            try:
                # 1. 👂 Ожидание ключевого слова...
                print(f"👂 Ожидание ключевого слова: «{WAKE_WORD}»...")
                captured_command = self.ear.listen_for_wake_word()

                # 2. ✅ Ключевое слово обнаружено
                print(f"✅ Ключевое слово обнаружено!")

                if captured_command:
                    # Попутная команда (мысалы: "Ассистент, аш блокнот")
                    user_text = captured_command
                    print(f"👤 [попутно]: {user_text}")
                else:
                    # Тек қана "Ассистент" десе, жауап күтеміз
                    print("🎤 Слушаю ваш запрос...")
                    self.mouth.speak("Слушаю")
                    user_text = self.ear.listen_command(timeout=10.0)

                if not user_text:
                    print("💤 Пауза (запрос естілмеді)")
                    continue

                # 3. 🧠 Обработка запроса...
                print(f"🧠 Обработка: {user_text}")
                threading.Thread(
                    target=self._process,
                    args=(user_text,),
                    daemon=True,
                    name="ProcessCmd",
                ).start()

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"MainLoop қатесі: {e}")
                time.sleep(1)
    # ──────────────────────────────────────────────────────────────────────────
    # Обработка команды
    # ──────────────────────────────────────────────────────────────────────────

    def _process(self, text: str):
        tl = text.lower()

        # ── Смена голоса ──────────────────────────────────────────────────────
        if self.mouth.check_and_switch_mode(text):
            return

        # ── Анализ экрана — ЧЕРЕЗ Vision.analyze(), НЕ PCControl ─────────────
        # FIX: Раньше LLM видел запрос "посмотри на экран" и сам генерировал
        # [ACTION: screenshot/save_to_clipboard] — это неверно. Vision.analyze()
        # делает скриншот → передаёт в llava:7b → возвращает текстовый ответ.
        if any(kw in tl for kw in _VISION_KW):
            logger.info("Vision: анализ экрана...")
            # OVERFLOW FIX: очищаем очередь перед тяжёлой GPU-операцией
            self.ear._clear_queue()
            response = self.vision.analyze(self.brain, text)
            # OVERFLOW FIX: очищаем очередь после возврата с GPU
            self.ear._clear_queue()
            self._respond(response)
            return

        # ── Веб-поиск ──────────────────────────────────────────────────────────
        if any(kw in tl for kw in _SEARCH_KW):
            results = self.search.search(text)
            augmented = f"Запрос: {text}\n\nРезультаты поиска:\n{results}"
            response = self.brain.think(augmented)
            self._respond(response)
            return

        # ── Напоминание ────────────────────────────────────────────────────────
        if any(kw in tl for kw in _REMIND_KW):
            result = self.scheduler.set_reminder(text)
            self._respond(result)
            return

        # ── Очистить память ────────────────────────────────────────────────────
        if any(kw in tl for kw in _CLEAR_KW):
            self.brain.clear_memory()
            self._respond("Память очищена.")
            return

        # ── Статус ─────────────────────────────────────────────────────────────
        if any(kw in tl for kw in _STATUS_KW):
            ollama_ok = self._check_ollama()
            self._respond(
                f"Работаю нормально. TTS: {self.mouth.mode}. "
                f"История: {self.brain.history_len} сообщений. "
                f"Ollama: {'✓' if ollama_ok else '✗ недоступен'}."
            )
            return

        # ── Основной путь: LLM ─────────────────────────────────────────────────
        print("🧠  ...")
        response = self.brain.think(text)
        print(f"\n🤖  {response}\n")

        # ── ACTION: выполнить команду ПК ───────────────────────────────────────
        action = self.brain.extract_action(response)
        if action:
            # FIX: НИКОГДА не передаём скриншот в PCControl для Vision-запросов
            # Но если LLM сам решил сделать скриншот — выполняем
            result = self.pc.execute(action)
            logger.info(f"ACTION результат: {result}")
            # Озвучиваем только короткий результат, не весь ответ
            self.mouth.speak(result)
        else:
            self.mouth.speak(response)

    def _respond(self, text: str):
        print(f"\n🤖  {text}\n")
        self.mouth.speak(text)

    def _check_ollama(self) -> bool:
        """Быстрая проверка доступности Ollama."""
        try:
            import requests as req
            r = req.get(f"{__import__('config.settings', fromlist=['OLLAMA_BASE_URL']).OLLAMA_BASE_URL}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False


# =============================================================================
if __name__ == "__main__":
    agent = LOQAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\nЗавершение LOQ-GENESIS...")
        agent.stop()
        sys.exit(0)
