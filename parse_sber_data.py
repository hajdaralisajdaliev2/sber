import requests
import json
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Функция для получения дивидендов через ISS API
def parse_dividends():
    url = "https://iss.moex.com/iss/securities/SBER/dividends.json?from=2015-01-01"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе дивидендов: {e}")
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
                logging.info(f"Добавлено: дата {date}, дивиденд {amount}")
            except Exception as e:
                logging.warning(f"Ошибка обработки строки дивидендов: {e}")
                continue
    return dividends

# Функция для получения цен и расчета гэпа через ISS API
def calculate_gaps(dividends):
    for div in dividends:
        date = datetime.strptime(div['date'], '%Y-%m-%d')
        start_date = (date - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = (date + timedelta(days=2)).strftime('%Y-%m-%d')

        # Получение дневных свечей
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/SBER/candles.json?interval=24&from={start_date}&till={end_date}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при запросе свечей для {div['date']}: {e}")
            div['yield'] = 0
            div['gap'] = 0
            continue

        candles = data['candles']['data']
        if len(candles) < 2:
            logging.warning(f"Недостаточно свечей для {div['date']}")
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
            logging.info(f"Для {div['date']}: доходность {div['yield']}%, гэп {div['gap']}%")
        except Exception as e:
            logging.warning(f"Ошибка расчета гэпа для {div['date']}: {e}")
            div['yield'] = 0
            div['gap'] = 0
    return dividends

# Функция для анализа отчетов (заглушка)
def analyze_reports(dividends):
    report_data = {
        '2024-07-11': {'profit_change': 18.0, 'status': 'Положительный'},
        '2023-05-11': {'profit_change': 10.0, 'status': 'Положительный'},
        '2022-05-12': {'profit_change': -20.0, 'status': 'Отрицательный'},
        '2021-05-06': {'profit_change': 15.0, 'status': 'Положительный'},
        '2020-06-25': {'profit_change': -10.0, 'status': 'Отрицательный'}
    }
    for div in dividends:
        date = div['date']
        div['report'] = report_data.get(date, {'status': 'Неизвестно'})['status']
    return dividends

# Основная функция
def main():
    logging.info("Запуск парсинга данных...")
    # Парсинг дивидендов
    dividends = parse_dividends()
    if not dividends:
        logging.error("Не удалось получить дивиденды. Завершение.")
        return
    
    # Расчет гэпов
    dividends = calculate_gaps(dividends)
    
    # Анализ отчетов
    dividends = analyze_reports(dividends)
    
    # Экспорт в JSON
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(dividends, f, ensure_ascii=False, indent=2)
    
    logging.info("Данные сохранены в data.json")

if __name__ == "__main__":
    main()
