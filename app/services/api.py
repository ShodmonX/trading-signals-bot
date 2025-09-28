import aiohttp
import asyncio
import logging

async def get_klines(symbol, interval='1h', limit=15, retries=3, delay=2):
    """
    Binance API'dan klines (OHLCV) ma'lumotlarini asinxron tarzda oladi.
    
    Args:
        symbol (str): Savdo juftligi (masalan, 'BTCUSDT').
        interval (str): Vaqt oralig'i (masalan, '1h', '1d'). Sukut bo'yicha '1h'.
        limit (int): Olinadigan klines soni (maksimum 1000). Sukut bo'yicha 15.
        retries (int): Qayta urinishlar soni. Sukut bo'yicha 3.
        delay (int): Qayta urinishlar orasidagi kutish vaqti (soniyalarda). Sukut bo'yicha 2.
        session (aiohttp.ClientSession, optional): HTTP sessiyasi. Agar berilmasa, yangi yaratiladi.
    
    Returns:
        tuple: (klines, error)
            - klines: Klines ma'lumotlari ro'yxati yoki None (xato bo'lsa).
            - error: Xato xabari (str) yoki None (muvaffaqiyatli bo'lsa).
    """
    valid_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
    if interval not in valid_intervals:
        return None, f"Invalid interval: {interval}. Must be one of {valid_intervals}"
    
    if limit > 1000:
        logging.warning(f"Limit {limit} exceeds Binance API maximum, setting to 1000")
        limit = 1000
    
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit+1}"
    session = aiohttp.ClientSession()
    
    try:
        for attempt in range(retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        klines = await response.json()
                        logging.debug(f"{symbol} - Received {len(klines)} klines")
                        if not isinstance(klines, list) or len(klines) == 0:
                            return None, "Empty or invalid klines data"
                        if not all(len(kline) == 12 for kline in klines):
                            return None, "Invalid kline format"
                        return klines[:-1], None
                    elif response.status == 429:
                        logging.warning(f"{symbol} - Rate limit exceeded, retrying after 10s")
                        await asyncio.sleep(10)
                        continue
                    else:
                        logging.debug(f"{symbol} - HTTP Error {response.status}: {await response.text()}")
                        return None, f"HTTP Error {response.status}: {await response.text()}"
            except Exception as e:
                logging.debug(f"{symbol} - Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                continue
        return None, f"Failed to fetch klines for {symbol} with interval {interval}: Max retries reached"
    finally:
        await session.close()

