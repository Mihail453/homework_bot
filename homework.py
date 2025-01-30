import os
from dotenv import load_dotenv
import time
import logging
from telebot import TeleBot
import requests


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
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
    required_tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    missing_tokens = [
        name for name, value in required_tokens.items() if not value]

    if missing_tokens:
        text = "Отсутствуют обязательные переменные окружения:"
        logging.critical(
            f"{text} {', '.join(missing_tokens)}")
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f"✅ Сообщение отправлено: {message}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")
        return False


def get_api_answer(bot, timestamp):
    """Проверяет корректность ответа API."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()  # Проверка на ошибки
        logging.debug("✅ API ответ получен успешно")
        return response.json()
    except requests.RequestException as e:
        error_message = f"❌ Ошибка при запросе к API: {e}"
        logging.error(error_message)
        send_message(bot, error_message)  # Отправляем ошибку
        return None


def check_response(response):
    """Проверяет корректность ответа API."""
    if not response:
        logging.error("❌ Пустой ответ API")
        return None

    if 'homeworks' not in response:
        logging.error("❌ В ответе API отсутствует ключ 'homeworks'")
        return None

    homeworks = response.get('homeworks')
    if not homeworks:
        logging.debug("🔍 В ответе API нет новых статусов")
    return homeworks


def parse_status(bot, homework):
    """Проверяет корректность статуса."""
    status = homework.get('status')
    if homework.get('status') not in HOMEWORK_VERDICTS:
        error_message = f'❌ Неизвестный статус домашней работы: {status}'
        logging.error(error_message)
        send_message(bot, error_message)
        raise ValueError(
            f'Неожиданное принятое значение: {homework.get("status")}'
        )
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(status)
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logging.debug(
        f'🔍 Обнаружен новый статус: {status} для работы "{homework_name}"')
    return message


def main():
    """Основная логика работы бота."""
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_verdict = None

    while True:
        try:
            response = get_api_answer(bot, timestamp)
            homeworks = check_response(response)

            if homeworks:
                first_homework = homeworks[0]
                verdict = parse_status(bot, first_homework)
            else:
                verdict = 'Нет новых статусов.'

            if verdict != last_verdict:  # Если статус изменился
                if send_message(bot, verdict):  # Отправляем сообщение
                    last_verdict = verdict  # Запоминаем отправленный статус

            logging.debug(f"🔍 Нет изменений в статусе: {verdict}")

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            print(message)
            if last_verdict != message:
                send_message(bot, message)
                last_verdict = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    if not check_tokens():
        exit(
            "Программа завершена. Добавьте недостающие переменные окружения.")
    main()
