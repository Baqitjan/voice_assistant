# =============================================================================
# LOQ-GENESIS | tools/scheduler.py
# Напоминания через библиотеку schedule
# =============================================================================

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

import schedule

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Модуль планировщика LOQ Agent.
    Позволяет устанавливать напоминания с колбэком (озвучка через Mouth).
    Запускает schedule в фоновом потоке.
    """

    def __init__(self, speak_callback: Callable[[str], None]):
        """
        speak_callback — функция озвучки, например mouth.speak.
        """
        self._speak = speak_callback
        self._jobs: list[dict] = []
        self._running = False
        self._thread: threading.Thread | None = None
        logger.info("Scheduler инициализирован.")

    def start(self):
        """Запустить планировщик в фоновом потоке."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="Scheduler"
        )
        self._thread.start()
        logger.info("Scheduler: фоновый поток запущен.")

    def stop(self):
        """Остановить планировщик."""
        self._running = False
        schedule.clear()

    def set_reminder(self, args: str) -> str:
        """
        Установить напоминание.
        args форматы:
          "через 10 минут напомни о встрече"
          "в 14:30 напомни позвонить маме"
          "каждые 30 минут делай перерыв"
        Возвращает строку подтверждения.
        """
        args_lower = args.lower()

        # --- Парсинг "через N минут" ---
        if "через" in args_lower and "минут" in args_lower:
            return self._set_relative(args_lower, args)

        # --- Парсинг "в HH:MM" ---
        if args_lower.startswith("в ") or " в " in args_lower:
            return self._set_absolute(args_lower, args)

        # --- Парсинг "каждые N минут" ---
        if "каждые" in args_lower or "каждый" in args_lower:
            return self._set_repeating(args_lower, args)

        # --- Fallback: напомнить через 1 минуту ---
        message = args
        self._schedule_once(60, message)
        return f"Напомню через 1 минуту: {message}"

    def list_reminders(self) -> str:
        """Вернуть список активных напоминаний."""
        if not self._jobs:
            return "Активных напоминаний нет."
        lines = ["Активные напоминания:"]
        for i, job in enumerate(self._jobs, 1):
            lines.append(f"  {i}. [{job['time']}] {job['message']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Внутренние методы парсинга
    # ------------------------------------------------------------------

    def _set_relative(self, args_lower: str, original: str) -> str:
        import re
        match = re.search(r"через\s+(\d+)\s+минут", args_lower)
        if not match:
            return "Не удалось распознать время напоминания."
        minutes = int(match.group(1))
        # Вычленяем текст напоминания (всё после "напомни")
        message = self._extract_message(original)
        self._schedule_once(minutes * 60, message)
        return f"Напомню через {minutes} мин.: {message}"

    def _set_absolute(self, args_lower: str, original: str) -> str:
        import re
        match = re.search(r"(\d{1,2}):(\d{2})", args_lower)
        if not match:
            return "Не удалось распознать время (формат ЧЧ:ММ)."
        hour, minute = int(match.group(1)), int(match.group(2))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay_sec = (target - now).total_seconds()
        message = self._extract_message(original)
        self._schedule_once(delay_sec, message)
        time_str = target.strftime("%H:%M")
        return f"Напомню в {time_str}: {message}"

    def _set_repeating(self, args_lower: str, original: str) -> str:
        import re
        match = re.search(r"каждые?\s+(\d+)\s+минут", args_lower)
        if not match:
            return "Не удалось распознать интервал напоминания."
        minutes = int(match.group(1))
        message = self._extract_message(original)
        job_entry = {"time": f"каждые {minutes} мин.", "message": message}
        self._jobs.append(job_entry)
        schedule.every(minutes).minutes.do(self._speak, message)
        logger.info(f"Повторяющееся напоминание каждые {minutes} мин.: {message}")
        return f"Буду напоминать каждые {minutes} мин.: {message}"

    def _schedule_once(self, delay_sec: float, message: str):
        """Одноразовое напоминание через delay_sec секунд."""
        job_entry = {
            "time": f"+{int(delay_sec)}сек",
            "message": message,
        }
        self._jobs.append(job_entry)

        def _fire():
            self._speak(f"Напоминание: {message}")
            schedule.cancel_job(job_ref)
            if job_entry in self._jobs:
                self._jobs.remove(job_entry)

        job_ref = schedule.every(delay_sec).seconds.do(_fire)
        logger.info(f"Напоминание через {delay_sec:.0f}сек: {message}")

    @staticmethod
    def _extract_message(text: str) -> str:
        """Вычленить текст напоминания из строки."""
        triggers = ["напомни", "напоминай", "напоминание"]
        text_lower = text.lower()
        for t in triggers:
            idx = text_lower.find(t)
            if idx != -1:
                after = text[idx + len(t):].strip()
                # Убираем "о", "про", "что" в начале
                for prep in ["о ", "об ", "про ", "что "]:
                    if after.lower().startswith(prep):
                        after = after[len(prep):]
                return after.strip() or text.strip()
        return text.strip()

    def _run_loop(self):
        """Фоновый цикл запуска schedule."""
        while self._running:
            schedule.run_pending()
            time.sleep(0.5)
