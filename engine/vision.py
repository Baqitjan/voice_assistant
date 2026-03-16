# =============================================================================
# LOQ-GENESIS | engine/vision.py — ФИНАЛЬНАЯ ВЕРСИЯ
#
# FIX: Vision.analyze() теперь правильно работает:
#   1. Делает скриншот.
#   2. Конвертирует в base64.
#   3. Передаёт в Brain с llava:7b (НЕ через PCControl.execute).
#
# Лог показал: агент раньше вызывал PCControl.execute(screenshot) вместо
# Vision.analyze(). Исправлено в main.py — здесь логика остаётся чистой.
# =============================================================================

import base64
import logging
import os

import pyautogui
from config.settings import SCREENSHOT_PATH, SCREENSHOT_REGION

logger = logging.getLogger(__name__)


class Vision:
    """
    Модуль зрения LOQ Agent.
    1. capture()  — скриншот → файл.
    2. get_b64()  — файл → base64 строка для llava.
    3. analyze()  — capture + get_b64 + Brain.think(llava) → текстовый ответ.
    """

    def __init__(self):
        logger.info("Vision инициализирован.")

    def capture(self) -> str | None:
        """Делает скриншот. Возвращает путь к файлу или None."""
        try:
            region = SCREENSHOT_REGION  # None = весь экран
            img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            img.save(SCREENSHOT_PATH)
            logger.info(f"Скриншот: {SCREENSHOT_PATH}")
            return SCREENSHOT_PATH
        except Exception as e:
            logger.error(f"Скриншот ошибка: {e}")
            return None

    def get_b64(self) -> str | None:
        """Кодирует последний скриншот в base64 для llava."""
        if not os.path.exists(SCREENSHOT_PATH):
            logger.warning("Скриншот не найден.")
            return None
        try:
            with open(SCREENSHOT_PATH, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"base64 ошибка: {e}")
            return None

    def analyze(self, brain, question: str) -> str:
        """
        Делает скриншот → отправляет в llava:7b через Brain.
        brain — экземпляр класса Brain.
        question — вопрос пользователя о содержимом экрана.

        ВАЖНО: Brain автоматически выберет llava:7b при наличии image_b64.
        """
        if not self.capture():
            return "Не удалось сделать скриншот."

        b64 = self.get_b64()
        if not b64:
            return "Не удалось загрузить скриншот."

        # Запрос в LLaVA через Brain — image_b64 переключает на llava:7b
        prompt = f"Внимательно посмотри на скриншот и ответь: {question}"
        logger.info("Vision: отправляю скриншот в llava:7b...")
        return brain.think(prompt, image_b64=b64)
