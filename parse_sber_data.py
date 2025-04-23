import requests
import json
from datetime import datetime, timedelta
import logging
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Функция для получения дивидендов через ISS API
def parse_dividends_iss(ticker):
    url = f"https://iss.moex.com/iss/securities/{ticker}/dividends.json?from=2015-01-01"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе дивидендов через ISS для {ticker}: {e}")
        return []

    dividends = []
    for row in data['dividends']['data']:
        date = row[2]  # Дата отсечки (registryclosedate)
        amount = row[4]  # Размер дивиденда (value)
        if date and amount:
            try:
                date = datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d')
                amount = float(amount)
                dividends.append({'date': date, 'dividend': amount})
                logging.info(f"Добавлено: дата {date}, дивиденд {amount} для {ticker}")
            except Exception as e:
                logging.warning(f"Ошибка обработки строки дивидендов для {ticker}: {e}")
                continue
    return dividends

# Резервная функция для получения дивидендов через Finam
def parse_dividends_finam(ticker):
    url = f"https://www.finam.ru/profile/moex-akcii/{ticker}/dividends/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе дивидендов через Finam для {ticker}: {e}")
        return []

    dividends = []
    table = soup.find('table', class_='table')
    if table:
        rows = table.find_all('tr')[1:]  # Пропускаем заголовок
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                date = cols[0].text.strip()  # Дата отсечки
                amount = cols[1].text.strip().replace(',', '.')  # Дивиденд
                try:
                    date = datetime.strptime(date, '%d.%m.%Y').strftime('%Y-%m-%d')
                    amount = float(amount)
                    dividends.append({'date': date, 'dividend': amount})
                    logging.info(f"Finam: Добавлено: дата {date}, дивиденд {amount} для {ticker}")
                except Exception as e:
                    logging.warning(f"Ошибка обработки строки дивидендов (Finam) для {ticker}: {e}")
                    continue
    return dividends

# Функция для получения дивидендов (попробует ISS, затем Finam)
def parse_dividends(ticker):
    dividends = parse_dividends_iss(ticker)
    if dividends:
        return dividends
    logging.warning(f"ISS API недоступен для {ticker}, пробуем Finam...")
    return parse_dividends_finam(ticker)

# Функция для получения цен и расчета гэпа через ISS API
def calculate_gaps(ticker, dividends):
    for div in dividends:
        date = datetime.strptime(div['date'], '%Y-%m-%d')
        start_date = (date - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = (date + timedelta(days=2)).strftime('%Y-%m-%d')

        # Получение дневных свечей
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}/candles.json?interval=24&from={start_date}&till={end_date}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при запросе свечей для {div['date']} ({ticker}): {e}")
            div['yield'] = 0
            div['gap'] = 0
            continue

        candles = data['candles']['data']
        if len(candles) < 2:
            logging.warning(f"Недостаточно свечей для {div['date']} ({ticker})")
            div['yield'] = 0
            div['gap'] = 0
            continue

        # Находим цены до и после отсечки
        price_pre = None
        price_post = None
        for i, candle in enumerate(candles):
            candle_date = candle[0].split(' ')[0]  # Дата свечи
            if candle_date < div['date']:
                price_pre = candle[4]  # Close до отсечки
            elif candle_date >= div['date']:
                price_post = candle[1]  # Open после отсечки
                break

        # Расчет доходности и гэпа
        try:
            div['yield'] = (div['dividend'] / price_pre) * 100
            div['gap'] = ((price_pre - price_post) / price_pre) * 100
            logging.info(f"Для {div['date']} ({ticker}): доходность {div['yield']}%, гэп {div['gap']}%")
        except Exception as e:
            logging.warning(f"Ошибка расчета гэпа для {div['date']} ({ticker}): {e}")
            div['yield'] = 0
            div['gap'] = 0
    return dividends

# Функция для анализа отчетов (заглушка, можно расширить)
def analyze_reports(dividends):
    report_data = {
        'SBER': {
            '2024-07-11': {'profit_change': 18.0, 'status': 'Положительный'},
            '2023-05-11': {'profit_change': 10.0, 'status': 'Положительный'},
            '2022-05-12': {'profit_change': -20.0, 'status': 'Отрицательный'},
            '2021-05-06': {'profit_change': 15.0, 'status': 'Положительный'},
            '2020-06-25': {'profit_change': -10.0, 'status': 'Отрицательный'}
        },
        'LKOH': {
            '2024-06-14': {'profit_change': 12.0, 'status': 'Положительный'},
            '2023-07-07': {'profit_change': 8.0, 'status': 'Положительный'}
        }
    }

    for div in dividends:
        date = div['date']
        ticker = div.get('ticker', 'SBER')
        div['report'] = report_data.get(ticker, {}).get(date, {'status': 'Неизвестно'})['status']
    return dividends

# Основная функция
def main(ticker="SBER"):
    logging.info(f"Запуск парсинга данных для {ticker}...")
    # Парсинг дивидендов
    dividends = parse_dividends(ticker)
    if not dividends:
        logging.error(f"Не удалось получить дивиденды ни через ISS, ни через Finam для {ticker}. Завершение.")
        return
    
    # Добавляем тикер в данные
    for div in dividends:
        div['ticker'] = ticker
    
    # Расчет гэпов
    dividends = calculate_gaps(ticker, dividends)
    
    # Анализ отчетов
    dividends = analyze_reports(dividends)
    
    # Экспорт в JSON
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(dividends, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Данные для {ticker} сохранены в data.json")

if __name__ == "__main__":
    ticker = input("Введите тикер акции (например, SBER, LKOH): ").strip().upper()
    if not ticker:
        ticker = "SBER"
    main(ticker)
