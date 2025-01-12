import logging
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from datetime import time
from pytz import timezone
from pyowm import OWM
from bs4 import BeautifulSoup
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Токены (лучше использовать переменные окружения)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7878119938:AAEH6XLQQuyjKK21hug2vMtunPUJOu3ocwo')
OWM_API_KEY = os.getenv('OWM_API_KEY', '6b4136828d19d7a18077ac1cc67f9f3e')

# Асинхронные функции для получения данных
async def get_news():
    try:
        url = 'https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), features='lxml-xml')  # Используем lxml для XML
                items = soup.find_all('item')[:5]
                news_list = [f"• {item.title.text}" for item in items]  # Добавляем маркеры для каждой новости
                return '\n'.join(news_list)  # Разделяем новости на строки
    except Exception as e:
        logging.error(f"Ошибка при получении новостей: {e}")
        return "Ошибка при получении новостей."

async def get_currency_rates():
    try:
        url = 'https://www.cbr-xml-daily.ru/daily_json.js'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)  # Игнорируем Content-Type
                rates = data['Valute']
                usd = rates['USD']['Value']
                eur = rates['EUR']['Value']
                cny = rates['CNY']['Value']
                return f"USD: {usd:.2f} RUB\nEUR: {eur:.2f} RUB\nCNY: {cny:.2f} RUB"
    except Exception as e:
        logging.error(f"Ошибка при получении курсов валют: {e}")
        return "Ошибка при получении курсов валют."

async def get_crypto_rates():
    try:
        # Используем Binance API для получения курса TON/USDT и CoinGecko для BTC и ETH
        url_ton = 'https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT'
        url_btc_eth = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin%2Cethereum&vs_currencies=usd'
        
        async with aiohttp.ClientSession() as session:
            # Получаем курс TON/USDT
            async with session.get(url_ton) as response:
                response.raise_for_status()
                ton_data = await response.json()
                ton_price = ton_data.get('price', 'N/A')

            # Получаем курсы BTC и ETH
            async with session.get(url_btc_eth) as response:
                response.raise_for_status()
                btc_eth_data = await response.json()
                btc_price = btc_eth_data.get('bitcoin', {}).get('usd', 'N/A')
                eth_price = btc_eth_data.get('ethereum', {}).get('usd', 'N/A')

            return f"BTC: ${btc_price}\nETH: ${eth_price}\nTON/USDT: {ton_price}"
    except Exception as e:
        logging.error(f"Ошибка при получении курсов криптовалют: {e}")
        return "Ошибка при получении курсов криптовалют."

async def get_weather():
    try:
        owm = OWM(OWM_API_KEY)
        mgr = owm.weather_manager()
        observation = mgr.weather_at_place('Krasnoyarsk,RU')
        weather = observation.weather

        # Словарь для перевода статусов погоды (Словарь)
        weather_status_translation = {
            "clear sky": "Ясно",
            "few clouds": "Небольшая облачность",
            "scattered clouds": "Рассеянные облака",
            "broken clouds": "Облачно с прояснениями",
            "overcast clouds": "Пасмурно",
            "light rain": "Небольшой дождь",
            "moderate rain": "Умеренный дождь",
            "heavy intensity rain": "Сильный дождь",
            "thunderstorm": "Гроза",
            "snow": "Снег",
            "mist": "Туман",
            "haze": "Дымка",
            "fog": "Туман",
        }

        # Получаем статус погоды и переводим его (СЛОВАРЬх2)
        status = weather.detailed_status
        status_ru = weather_status_translation.get(status, status)  # Если перевода нет, остается оригинал

        temp = weather.temperature('celsius')['temp']
        return f"Температура: {temp}°C\nСостояние: {status_ru}"
    except Exception as e:
        logging.error(f"Ошибка при получении погоды: {e}")
        return "Ошибка при получении погоды."

# Асинхронная функция для утреннего обновления (ХУЙНЯ)
async def morning_update(context: CallbackContext):
    chat_id = context.job.context
    news = await get_news()
    currency_rates = await get_currency_rates()
    crypto_rates = await get_crypto_rates()
    weather = await get_weather()

    message = (f"Доброе утро!\n\n"
               f"Главные новости:\n{news}\n\n"
               f"Курсы валют:\n{currency_rates}\n\n"
               f"Курсы криптовалют:\n{crypto_rates}\n\n"
               f"Погода в Красноярске:\n{weather}")

    await context.bot.send_message(chat_id=chat_id, text=message)

# Команда start для запуска бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    logging.info(f"Chat ID: {chat_id}")

    # Создаем клавиатуру с кнопкой
    keyboard = [[KeyboardButton("Получить данные сейчас")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(
        f'Ваш chat_id: {chat_id}\nТеперь вы сможете получать обновления.',
        reply_markup=reply_markup
    )

    # Создаем задачу для утренних обновлений
    krasnoyarsk_tz = timezone('Asia/Krasnoyarsk')
    context.job_queue.run_daily(morning_update, time=time(hour=8, minute=0, tzinfo=krasnoyarsk_tz), context=chat_id)

# Обработчик нажатия на кнопку
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.text == "Получить данные сейчас":
        # Получаем данные и отправляем их
        news = await get_news()
        currency_rates = await get_currency_rates()
        crypto_rates = await get_crypto_rates()
        weather = await get_weather()

        message = (f"Данные по запросу:\n\n"
                   f"Главные новости:\n{news}\n\n"
                   f"Курсы валют:\n{currency_rates}\n\n"
                   f"Курсы криптовалют:\n{crypto_rates}\n\n"
                   f"Погода в Красноярске:\n{weather}")

        await update.message.reply_text(text=message)

# Основная функция
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()