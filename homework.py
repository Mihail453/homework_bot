import os
from dotenv import load_dotenv
import time
import logging
from telebot import TeleBot
import requests
from http import HTTPStatus


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    all_tokens = True
    for name, token in tokens.items():
        if token:
            logging.debug(
                f'Переменная окружения {name} = {token} поступила корректно.'
            )
        else:
            logging.critical(
                'Отсутствует обязательная переменная окружения '
                f'{name} = {token}.'
            )
            all_tokens = False
    if not all_tokens:
        raise SystemExit(
            'Программа принудительно остановлена из-за отсутствия '
            'обязательных переменных окружения.'
        )


def send_message(bot, message):
    """Отправляет смс в тг."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f"✅ Сообщение отправлено: {message}")
        return True
    except Exception as e:
        text = (f"Ошибка при отправке сообщения: {e}")
        logging.error(text)
        send_message(bot, text)
        return False


def get_api_answer(timestamp):
    """Проверяет корректность ответа API."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        raise ConnectionError('Сбой работы')
    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError(
            'Ошибка HTTP: {status_code}. Причина: {reason}. '
            'Текст ответа: {text}.'.format(**response)
        )
    logging.debug('Запрос к эндпоинту API-сервиса прошёл успешно.')
    return response.json()


def check_response(response):
    """Проверяет корректность ответа API."""
    # Проверка на пустой ответ
    if not response:
        logging.error("❌ Пустой ответ API")
        raise TypeError("Ответ API пустой. Ожидался непустой ответ.")

    # Проверка на то, что ответ является словарем
    if not isinstance(response, dict):
        text = '❌ Ошибка: ожидаемый словарь, а получен тип'
        raise TypeError(f"{text} {type(response)}")

    # Проверка на наличие ключа 'homeworks'
    if 'homeworks' not in response:
        raise TypeError("❌ Ошибка: отсутствует ключ 'homeworks' в ответе API.")

    homeworks = response.get('homeworks')

    # Проверка, что 'homeworks' является списком
    if not isinstance(homeworks, list):
        raise TypeError(f"❌ Получен неправильный тип {type(homeworks)}")

    # Если список пустой, выводим сообщение, что нет новых статусов
    if not homeworks:
        logging.debug("🔍 В ответе API нет новых статусов")
    return homeworks


def parse_status(homework):
    """Проверяет корректность статуса."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        text = "❌ Ошибка: в данных отсутствует ключ 'homework_name'. Данные:"
        raise KeyError(f"{text} {homework}")

    status = homework.get('status')
    if homework.get('status') not in HOMEWORK_VERDICTS:
        error_message = f'❌ Неизвестный статус домашней работы: {status}'
        logging.error(error_message)
        raise KeyError(f'{error_message}')

    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(status)
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logging.debug(
        f'🔍 Обнаружен новый статус: {status} для работы "{homework_name}"')
    return message


def main():
    """Основная логика работы бота."""
    check_tokens()
    # Создаем объект класса бота
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_verdict = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                first_homework = homeworks[0]
                verdict = parse_status(first_homework)
            else:
                verdict = 'Нет новых статусов.'

            if verdict != last_verdict:  # Если статус изменился
                if send_message(bot, verdict):
                    last_verdict = verdict  # Запоминаем отправленный статус
            elif verdict == 'Нет новых статусов.':
                send_message(bot, verdict)

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            if last_verdict != message:
                send_message(bot, message)
                last_verdict = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
