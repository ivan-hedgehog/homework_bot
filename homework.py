import logging
import os
import requests
import sys
import time
import telegram
import exceptions

from dotenv import load_dotenv

from logging import StreamHandler, Formatter
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
environment_variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
MESSAGE = ''


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
handler.setFormatter(Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s'))
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Сообщение не отправленно!')
        raise AssertionError(
            'при отправке сообщения из бота возникает ошибка.'
        )


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': 0}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
        response = homework_statuses.json()
        logger.debug(
            'Функция get_api_answer задачу выполнила, замечания отсутствуют'
        )
    except Exception as error:
        logger.error(error, exc_info=True)
        raise exceptions.APIConnectError('Не удалось получить доступ к API')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise exceptions.HttpStatusError(
            f'Неверный статус ответа: {homework_statuses.status_code}')
    return response


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API-сервера содержит неверный тип данных.')
    if 'homeworks' not in response:
        raise KeyError('Ответ от API не содержит ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('В ответ API-сервера содержит неверный тип данных.')
    logger.debug('Ответ от API-сервера корректен')
    homeworks = response['homeworks']
    homework = homeworks[-1]
    return homework


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    try:
        homework_name = homework['homework_name']
        logger.debug('Достаем из словаря имя работы')
    except KeyError:
        raise KeyError('В словаре нет ключа homework_name')
    try:
        homework_status = homework['status']
        logger.debug('Достаем статус работы')
    except KeyError:
        raise KeyError('В словаре нет ключа status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise exceptions.StatusWorkException(
            'Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    message = (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )
    logger.debug(
        'Функция parse_status задачу выполнила,'
        'замечания отсутствуют'
    )
    return message


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_old = ''

    if not check_tokens():
        logger.critical(' Отсутствует переменная окружения')
        sys.exit(' Отсутствует переменная окружения,завершение программы')

    while True:
        try:
            response = get_api_answer(timestamp)
            logger.debug('Исполнение get_api_answer')
            homework = check_response(response)
            logger.debug('Исполнение check_response')
            message = parse_status(homework)
            logger.debug('Исполнение parse_status')
            if message != message_old:
                send_message(bot, message)
                message_old = message
                logger.debug('Исполнение send_message')
            else:
                message = 'Отсутствие новых статусов'
                send_message(bot, message)
                logger.debug('Отсутствие новых статусов')

        except Exception as error:
            logger.error('Бот не смог отправить сообщение')
            message = (f'Сбой в работе программы: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
