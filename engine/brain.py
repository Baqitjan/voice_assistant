
import json
import logging
import re
import time
from collections import deque
from typing import Generator

import requests

from config.settings import (
    OLLAMA_BASE_URL, OLLAMA_TIMEOUT,
    LLM_DEFAULT, LLM_KAZAKH, LLM_VISION,
    MEMORY_MAX_MESSAGES, SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_KAZ_CHARS = frozenset("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
_OLLAMA_RETRIES = 3
_OLLAMA_RETRY_DELAY = 2.0


def _is_kazakh(text: str) -> bool:
    return bool(_KAZ_CHARS & set(text))


class Brain:
    """
    Мозг LOQ Agent.
    - deque(maxlen=N) — O(1) скользящее окно памяти.
    - Retry при ошибках Ollama (500, ConnectionError).
    - Автодетект казахского → kazllm.
    - Парсинг [ACTION: {...}] из ответа.
    """

    def __init__(self):
        # deque с maxlen — автоматически выбрасывает старые сообщения
        self._history: deque[dict] = deque(maxlen=MEMORY_MAX_MESSAGES)
        logger.info(
            f"Brain инициализирован. "
            f"LLM: {LLM_DEFAULT} / {LLM_KAZAKH} / {LLM_VISION} | "
            f"Memory: {MEMORY_MAX_MESSAGES} сообщений"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────────

    def think(self, user_text: str, image_b64: str | None = None) -> str:
        """Синхронный запрос к LLM с retry."""
        model = self._pick_model(user_text, bool(image_b64))
        self._history.append({"role": "user", "content": user_text})
        payload = self._build(model, image_b64, stream=False)

        reply = self._call_with_retry(payload)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def think_stream(
        self, user_text: str, image_b64: str | None = None
    ) -> Generator[str, None, None]:
        """Стриминг токенов с автосохранением в историю."""
        model = self._pick_model(user_text, bool(image_b64))
        self._history.append({"role": "user", "content": user_text})
        payload = self._build(model, image_b64, stream=True)
        buf = []

        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            buf.append(token)
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"Стриминг Ollama: {e}")
            err = "Ошибка стриминга. Проверь, что Ollama запущен."
            buf.append(err)
            yield err

        self._history.append({"role": "assistant", "content": "".join(buf)})

    def extract_action(self, text: str) -> dict | None:
        """Күшейтілген парсинг: [ACTION: {...}] немесе жай ғана {...} іздеу."""
        # 1. Алдымен стандартты [ACTION: {...}] форматын іздейміз
        m = re.search(r"\[ACTION:\s*(\{.*?\})\]", text, re.DOTALL)
        # 2. Егер ол табылмаса, мәтін ішіндегі кез келген бірінші JSON жақшаларын іздейміз
        json_str = None
        if m:
            json_str = m.group(1)
        else:
            m_raw = re.search(r"(\{.*?\})", text, re.DOTALL)
            if m_raw:
                json_str = m_raw.group(1)
        if not json_str:
            return None
        try:
            # JSON ішіндегі қате тырнақшаларды түзеуге тырысамыз (аздап "сиқыр")
            valid_json = json_str.replace("'", '"')
            action = json.loads(valid_json)
            # Міндетті өрісті тексеру
            if "cmd" in action:
                logger.info(f"ACTION табылды: {action}")
                return action
        except Exception as e:
            logger.warning(f"JSON парсинг қатесі: {e}")
        return None

    def clear_memory(self):
        self._history.clear()
        logger.info("Память очищена.")

    @property
    def history_len(self) -> int:
        return len(self._history)

    # ──────────────────────────────────────────────────────────────────────────
    # Внутренние методы
    # ──────────────────────────────────────────────────────────────────────────

    def _pick_model(self, text: str, has_image: bool) -> str:
        if has_image:
            return LLM_VISION

        tl = text.lower()
        # Егер қазақша әріптер болса НЕМЕСЕ қазақша етістіктер болса
        kaz_verbs = ["аш", "жап", "жаз", "түсір", "тап", "ізде"]
        is_kaz = _is_kazakh(text) or any(v in tl for v in kaz_verbs)

        if is_kaz:
            logger.debug("Детект: Қазақ тілі/командасы → kazllm")
            return LLM_KAZAKH

        return LLM_DEFAULT

    def _build(self, model: str, image_b64: str | None, stream: bool) -> dict:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        history_list = list(self._history)

        for msg in history_list:
            entry: dict = {"role": msg["role"], "content": msg["content"]}
            if (
                image_b64
                and msg["role"] == "user"
                and msg is history_list[-1]
            ):
                entry["images"] = [image_b64]
            messages.append(entry)

        return {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
                "num_predict": 128,
                "repeat_penalty": 1.1,
                "stop": ["[/ACTION]", "\n\n"]
            },
        }

    def _call_with_retry(self, payload: dict) -> str:
        """
        Синхронный вызов Ollama с retry.
        При 500 или ConnectionError — ждёт и повторяет.
        """
        url = f"{OLLAMA_BASE_URL}/api/chat"
        last_error = None

        for attempt in range(1, _OLLAMA_RETRIES + 1):
            try:
                r = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT)

                # Детальное логирование 500-ошибки
                if r.status_code == 500:
                    body = r.text[:300]
                    logger.error(
                        f"Ollama 500 (попытка {attempt}/{_OLLAMA_RETRIES}). "
                        f"Тело: {body}"
                    )
                    # Частая причина 500: модель не загружена
                    if "model" in body.lower() and "not found" in body.lower():
                        return (
                            f"Модель не найдена в Ollama. "
                            f"Запусти: ollama pull {payload['model']}"
                        )
                    last_error = f"Ollama 500: {body}"
                    time.sleep(_OLLAMA_RETRY_DELAY)
                    continue

                r.raise_for_status()
                return r.json()["message"]["content"].strip()

            except requests.exceptions.ConnectionError as e:
                last_error = f"Ollama недоступен: {e}"
                logger.error(
                    f"ConnectionError (попытка {attempt}/{_OLLAMA_RETRIES}). "
                    "Убедись, что запущен 'ollama serve'."
                )
                time.sleep(_OLLAMA_RETRY_DELAY * attempt)

            except Exception as e:
                last_error = str(e)
                logger.error(f"Ollama ошибка (попытка {attempt}): {e}")
                time.sleep(_OLLAMA_RETRY_DELAY)

        return f"Ошибка связи с LLM: {last_error}. Проверь 'ollama serve'."
