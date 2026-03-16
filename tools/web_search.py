# =============================================================================
# LOQ-GENESIS | tools/web_search.py
# Веб-поиск через DuckDuckGo (без API-ключа)
# =============================================================================

import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class WebSearch:
    """
    Модуль веб-поиска LOQ Agent.
    Использует DuckDuckGo Search (библиотека duckduckgo-search).
    Не требует API-ключа. Возвращает топ-N результатов.
    """

    def __init__(self, max_results: int = 5):
        self._max_results = max_results
        logger.info(f"WebSearch инициализирован. max_results={max_results}")

    def search(self, query: str) -> str:
        """
        Выполнить поиск и вернуть форматированные результаты.
        Возвращает строку для отправки в LLM.
        """
        logger.info(f"Поиск: {query}")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=self._max_results,
                    region="ru-ru",
                    safesearch="moderate",
                ))
        except Exception as e:
            logger.error(f"Ошибка DuckDuckGo: {e}")
            return f"Ошибка поиска: {e}"

        if not results:
            return "По вашему запросу ничего не найдено."

        lines = [f"Результаты поиска по запросу '{query}':\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "—")
            body  = r.get("body", "—")[:200]
            url   = r.get("href", "")
            lines.append(f"{i}. {title}\n   {body}\n   🔗 {url}\n")

        result_text = "\n".join(lines)
        logger.debug(f"Результаты поиска:\n{result_text[:300]}")
        return result_text

    def news(self, query: str) -> str:
        """Поиск по новостям."""
        logger.info(f"Поиск новостей: {query}")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(
                    query,
                    max_results=self._max_results,
                    region="ru-ru",
                ))
        except Exception as e:
            logger.error(f"Ошибка DuckDuckGo news: {e}")
            return f"Ошибка поиска новостей: {e}"

        if not results:
            return "Новости не найдены."

        lines = [f"Новости по запросу '{query}':\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "—")
            body  = r.get("body", "—")[:200]
            date  = r.get("date", "")
            url   = r.get("url", "")
            lines.append(f"{i}. [{date}] {title}\n   {body}\n   🔗 {url}\n")

        return "\n".join(lines)
