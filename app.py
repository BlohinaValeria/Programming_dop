# ============================================================
# АСИНХРОННОЕ ВЕБ-ПРИЛОЖЕНИЕ ДЛЯ ПОИСКА ПУБЛИКАЦИЙ В CROSSREF
# ============================================================
# Технологии: Flask, aiohttp, asyncio, Bootstrap
# Дисциплина: Программирование на Python
# ============================================================

import asyncio
import aiohttp
import json
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import logging
from typing import List, Dict, Optional, Any

# Настройка логирования для отслеживания ошибок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# ИНИЦИАЛИЗАЦИЯ FLASK ПРИЛОЖЕНИЯ
# ============================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С API
# ============================================================

class CrossrefAPI:
    """Класс для работы с API Crossref"""

    BASE_URL = "https://api.crossref.org/works"

    @staticmethod
    def extract_publication_data(item: Dict) -> Dict:
        """
        Извлекает данные публикации из ответа API Crossref.

        Chain of Thought (CoT) размышление:
        1. Сначала проверяем наличие основных полей (title, author, etc.)
        2. Извлекаем название статьи (может быть список, берем первый)
        3. Извлекаем имя первого автора
        4. Извлекаем название журнала из container-title
        5. Извлекаем год публикации из issued
        6. Извлекаем аффилиацию первого автора (если есть)
        """
        # Шаг 1: Извлечение названия статьи
        # В API Crossref title может быть списком, берем первый элемент
        title = item.get('title', ['Без названия'])[0] if item.get('title') else 'Без названия'

        # Шаг 2: Извлечение авторов
        # Получаем список авторов, берем первого
        authors = item.get('author', [])
        first_author = authors[0] if authors else {}

        # Шаг 3: Формирование имени автора
        # Используем given (имя) и family (фамилия)
        author_name = ""
        if first_author:
            given = first_author.get('given', '')
            family = first_author.get('family', '')
            author_name = f"{given} {family}".strip()
            if not author_name:
                author_name = "Автор не указан"

        # Шаг 4: Извлечение названия журнала/сборника
        # container-title может быть списком
        container = item.get('container-title', ['Не указано'])[0] if item.get('container-title') else 'Не указано'

        # Шаг 5: Извлечение даты публикации
        # Используем issued поле
        publication_year = "Не указан"
        issued = item.get('issued', {})
        if issued and 'date-parts' in issued:
            date_parts = issued['date-parts']
            if date_parts and date_parts[0]:
                publication_year = str(date_parts[0][0])  # Берем год

        # Шаг 6: Извлечение аффилиации первого автора
        # Аффилиация находится в affiliation у автора
        affiliation = "Не указано"
        if first_author and 'affiliation' in first_author:
            affiliations = first_author['affiliation']
            if affiliations and isinstance(affiliations, list):
                # Берем первую аффилиацию
                aff = affiliations[0]
                if isinstance(aff, dict) and 'name' in aff:
                    affiliation = aff['name']
                elif isinstance(aff, str):
                    affiliation = aff

        # Шаг 7: Извлечение DOI (идентификатор)
        doi = item.get('DOI', '')

        return {
            'title': title,
            'author': author_name,
            'container': container,
            'year': publication_year,
            'affiliation': affiliation,
            'doi': doi,
            'url': f"https://doi.org/{doi}" if doi else '#'
        }

    @staticmethod
    async def search_by_author(session: aiohttp.ClientSession,
                               author_name: str,
                               rows: int = 20) -> List[Dict]:
        """
        Асинхронный поиск публикаций по автору.

        Асинхронная конструкция:
        - Используем async/await для неблокирующего выполнения
        - aiohttp.ClientSession для управления соединениями
        - asyncio для параллельных запросов

        Аргументы:
            session: aiohttp сессия для выполнения запросов
            author_name: имя автора для поиска
            rows: количество результатов (10-20)
        """
        params = {
            'query.author': author_name,
            'rows': rows,
            'sort': 'relevance'
        }

        try:
            # Асинхронный GET-запрос к API Crossref
            async with session.get(CrossrefAPI.BASE_URL, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                # Извлекаем публикации из ответа
                items = data.get('message', {}).get('items', [])

                # Преобразуем каждую публикацию в удобный формат
                publications = [CrossrefAPI.extract_publication_data(item) for item in items]

                logger.info(f"Найдено {len(publications)} публикаций по автору '{author_name}'")
                return publications

        except aiohttp.ClientTimeout:
            logger.error(f"Таймаут при запросе по автору '{author_name}'")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка клиента: {e}")
            return []
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")
            return []

    @staticmethod
    async def search_by_title(session: aiohttp.ClientSession,
                              title: str,
                              rows: int = 20) -> List[Dict]:
        """
        Асинхронный поиск публикаций по названию.

        Асинхронная конструкция аналогична search_by_author.
        """
        params = {
            'query.title': title,
            'rows': rows,
            'sort': 'relevance'
        }

        try:
            async with session.get(CrossrefAPI.BASE_URL, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                items = data.get('message', {}).get('items', [])
                publications = [CrossrefAPI.extract_publication_data(item) for item in items]

                logger.info(f"Найдено {len(publications)} публикаций по названию '{title}'")
                return publications

        except aiohttp.ClientTimeout:
            logger.error(f"Таймаут при запросе по названию '{title}'")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка клиента: {e}")
            return []
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")
            return []

    @staticmethod
    async def search_multiple(session: aiohttp.ClientSession,
                              authors: List[str] = None,
                              titles: List[str] = None,
                              rows: int = 20) -> List[Dict]:
        """
        Асинхронный поиск по нескольким авторам и названиям (параллельно).

        Ключевая асинхронная конструкция:
        - asyncio.gather() для параллельного выполнения нескольких запросов
        - Эффективное использование ресурсов при множественных запросах

        Аргументы:
            session: aiohttp сессия
            authors: список имен авторов
            titles: список названий
            rows: количество результатов на запрос
        """
        tasks = []

        # Создаем задачи для каждого поискового запроса
        if authors:
            for author in authors:
                if author.strip():
                    tasks.append(CrossrefAPI.search_by_author(session, author.strip(), rows))

        if titles:
            for title in titles:
                if title.strip():
                    tasks.append(CrossrefAPI.search_by_title(session, title.strip(), rows))

        if not tasks:
            return []

        # Асинхронное выполнение всех задач параллельно
        # asyncio.gather - ключевая конструкция для параллельных запросов
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Объединяем результаты
        combined = []
        for result in results:
            if isinstance(result, list):
                combined.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Ошибка при параллельном запросе: {result}")

        return combined


# ============================================================
# АСИНХРОННЫЙ ОБРАБОТЧИК ДЛЯ ПОИСКА
# ============================================================

async def perform_search(query_type: str, query_value: str, multiple: bool = False) -> Dict:
    """
    Основной асинхронный обработчик для выполнения поиска.

    Асинхронные конструкции в этом обработчике:
    1. async def - асинхронная функция
    2. async with - асинхронный контекстный менеджер для aiohttp
    3. await - ожидание завершения асинхронных операций

    Аргументы:
        query_type: тип поиска ('author', 'title', 'multiple')
        query_value: значение для поиска или список для множественного поиска
        multiple: флаг множественного поиска

    Возвращает:
        словарь с результатами поиска
    """
    # Создаем асинхронную сессию для HTTP-запросов
    # aiohttp.ClientSession - управляет пулом соединений
    async with aiohttp.ClientSession() as session:
        try:
            # Проверяем тип поиска и выполняем соответствующий запрос
            if multiple and isinstance(query_value, list):
                # Множественный поиск (параллельные запросы)
                # Негативный промпт: проверяем что не пустой список
                if not query_value:
                    return {'success': False, 'error': 'Список запросов пуст'}

                # Разделяем авторы и названия
                authors = [v for v in query_value if v.strip()]
                titles = [v for v in query_value if v.strip()]
                # Негативный промпт: исключаем пустые значения
                # Если есть и авторы и названия, ищем по обоим параметрам
                results = await CrossrefAPI.search_multiple(
                    session=session,
                    authors=authors,
                    titles=titles,
                    rows=20
                )

            elif query_type == 'author':
                results = await CrossrefAPI.search_by_author(session, query_value, rows=20)
            elif query_type == 'title':
                results = await CrossrefAPI.search_by_title(session, query_value, rows=20)
            else:
                return {'success': False, 'error': 'Неизвестный тип поиска'}

            return {
                'success': True,
                'results': results,
                'count': len(results)
            }

        except aiohttp.ClientError as e:
            logger.error(f"Ошибка соединения с API Crossref: {e}")
            return {
                'success': False,
                'error': 'Нет соединения с API Crossref. Проверьте интернет-соединение.'
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Превышено время ожидания ответа от сервера.'
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return {
                'success': False,
                'error': f'Произошла ошибка: {str(e)}'
            }


def run_async_search(query_type: str, query_value, multiple: bool = False):
    """
    Синхронная обертка для запуска асинхронной функции.

    Это необходимо для интеграции async кода с Flask (который синхронный).
    Создаем новый цикл событий для выполнения async операций.
    """
    # Создаем новый цикл событий для каждого запроса
    # Это позволяет избежать проблем с повторным использованием циклов
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Запускаем асинхронную функцию и ждем результат
        result = loop.run_until_complete(
            perform_search(query_type, query_value, multiple)
        )
        return result
    finally:
        # Закрываем цикл событий для освобождения ресурсов
        loop.close()


# ============================================================
# МАРШРУТЫ FLASK
# ============================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Главная страница с формой поиска.

    GET: отображает форму
    POST: обрабатывает поисковый запрос
    """
    # Негативный промпт: начальное состояние без ошибок
    error = None
    results = []
    search_type = None
    query_value = None

    if request.method == 'POST':
        # Получаем данные из формы
        search_type = request.form.get('search_type', 'author')
        query_value = request.form.get('query_value', '').strip()
        multiple_mode = request.form.get('multiple_mode', 'false') == 'true'

        # Негативный промпт: проверка на пустой запрос
        if not query_value and not multiple_mode:
            error = 'Пожалуйста, введите значение для поиска'
        else:
            # Подготовка данных для множественного поиска
            if multiple_mode and query_value:
                # Разделяем запросы по запятой или точке с запятой
                import re
                # Chain of Thought: обрабатываем разные разделители
                queries = re.split(r'[;,]\s*', query_value)
                # Негативный промпт: исключаем пустые строки
                queries = [q.strip() for q in queries if q.strip()]

                if not queries:
                    error = 'Введите хотя бы один запрос для множественного поиска'
                else:
                    # Выполняем множественный асинхронный поиск
                    result = run_async_search('multiple', queries, multiple=True)

                    if result['success']:
                        results = result['results']
                    else:
                        error = result.get('error', 'Ошибка при выполнении поиска')
            else:
                # Обычный поиск (по автору или названию)
                result = run_async_search(search_type, query_value, multiple=False)

                if result['success']:
                    results = result['results']
                else:
                    error = result.get('error', 'Ошибка при выполнении поиска')

    # Рендерим шаблон с результатами
    return render_template('index.html',
                           results=results,
                           error=error,
                           search_type=search_type,
                           query_value=query_value)


@app.route('/api/search', methods=['POST'])
def api_search():
    """
    API эндпоинт для поиска (возвращает JSON).

    Используется для AJAX-запросов с фронтенда.
    """
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'Неверный формат запроса'}), 400

    search_type = data.get('search_type', 'author')
    query_value = data.get('query_value', '').strip()

    if not query_value:
        return jsonify({'success': False, 'error': 'Введите значение для поиска'}), 400

    # Выполняем поиск
    result = run_async_search(search_type, query_value)

    if result['success']:
        return jsonify({'success': True, 'results': result['results'], 'count': result['count']})
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Ошибка поиска')}), 500


# ============================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================

if __name__ == '__main__':
    # Запускаем Flask приложение
    # debug=False для избежания проблем с asyncio
    app.run(debug=False, host='0.0.0.0', port=5000)