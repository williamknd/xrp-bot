"""
XRP 5-Red Candle Reversal Bot - Bybit
Versão Railway (variáveis de ambiente)
"""

import os
import time
import logging
from pybit.unified_trading import HTTP

# ─────────────────────────────────────────────
#  ⚙️  CONFIGURAÇÕES (via variáveis de ambiente no Railway)
# ─────────────────────────────────────────────
API_KEY    = os.environ.get("API_KEY", "")
API_SECRET = os.environ.get("API_SECRET", "")
TESTNET    = os.environ.get("TESTNET", "true").lower() == "true"

SYMBOL         = os.environ.get("SYMBOL", "XRPUSDT")
CATEGORY       = "linear"
TIMEFRAME      = "5"
QTY            = os.environ.get("QTY", "10")
LEVERAGE       = int(os.environ.get("LEVERAGE", "1"))
STOP_LOSS_PCT  = float(os.environ.get("STOP_LOSS_PCT", "0.01"))
MAX_CANDLES    = int(os.environ.get("MAX_CANDLES", "120"))
STREAK_TRIGGER = int(os.environ.get("STREAK_TRIGGER", "5"))
LOOP_INTERVAL  = int(os.environ.get("LOOP_INTERVAL", "30"))

# ─────────────────────────────────────────────
#  📋  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("XRPBot")

if not API_KEY or not API_SECRET:
    log.error("❌ API_KEY e API_SECRET não configurados!")
    exit(1)

session = HTTP(testnet=TESTNET, api_key=API_KEY, api_secret=API_SECRET)

def count_streak(opens, closes):
    streak = [0] * len(closes)
    for i in range(1, len(closes)):
        if closes[i] < opens[i]:
            streak[i] = streak[i-1] - 1 if streak[i-1] < 0 else -1
        elif closes[i] > opens[i]:
            streak[i] = streak[i-1] + 1 if streak[i-1] > 0 else 1
    return streak

def get_signal(streak):
    last = streak[-1]
    if last <= -STREAK_TRIGGER: return 1
    if last >= STREAK_TRIGGER:  return -1
    return 0

def fetch_candles(limit=150):
    resp    = session.get_kline(category=CATEGORY, symbol=SYMBOL, interval=TIMEFRAME, limit=limit)
    candles = list(reversed(resp["result"]["list"]))
    return ([float(c[1]) for c in candles], [float(c[4]) for c in candles], [int(c[0]) for c in candles])

def get_last_price():
    return float(session.get_tickers(category=CATEGORY, symbol=SYMBOL)["result"]["list"][0]["lastPrice"])

def get_position():
    for p in session.get_positions(category=CATEGORY, symbol=SYMBOL)["result"]["list"]:
        if float(p["size"]) > 0: return p
    return None

def set_leverage():
    try:
        session.set_leverage(category=CATEGORY, symbol=SYMBOL, buyLeverage=str(LEVERAGE), sellLeverage=str(LEVERAGE))
        log.info(f"Alavancagem: {LEVERAGE}x")
    except Exception as e:
        log.warning(f"Alavancagem: {e}")

def open_position(side, price):
    sl = round(price * (1 - STOP_LOSS_PCT if side == "Buy" else 1 + STOP_LOSS_PCT), 4)
    try:
        resp = session.place_order(category=CATEGORY, symbol=SYMBOL, side=side,
                                   orderType="Market", qty=QTY, stopLoss=str(sl), timeInForce="GTC")
        log.info(f"✅ {side} | Qty: {QTY} | SL: {sl}")
        return True
    except Exception as e:
        log.error(f"❌ Erro: {e}")
        return False

def close_position(position):
    side = "Sell" if position["side"] == "Buy" else "Buy"
    try:
        session.place_order(category=CATEGORY, symbol=SYMBOL, side=side,
                            orderType="Market", qty=position["size"], reduceOnly=True)
        log.info("🔒 Posição fechada")
        return True
    except Exception as e:
        log.error(f"❌ Erro ao fechar: {e}")
        return False

def run():
    log.info(f"🚀 XRP Bot | {SYMBOL} | Testnet: {TESTNET} | Qty: {QTY} | SL: {STOP_LOSS_PCT*100}%")
    set_leverage()
    position_open_candle = None
    last_signal_candle   = None

    while True:
        try:
            opens, closes, timestamps = fetch_candles()
            streak = count_streak(opens, closes)
            signal = get_signal(streak)
            price  = get_last_price()
            now_ts = timestamps[-1]

            log.info(f"Preço: {price:.4f} | Streak: {streak[-1]:+d} | Sinal: {'LONG' if signal==1 else 'SHORT' if signal==-1 else 'NENHUM'}")

            position = get_position()
            if position:
                if position_open_candle:
                    candles_held = sum(1 for t in timestamps if t > position_open_candle)
                    log.info(f"📊 {position['side']} | Velas: {candles_held}/{MAX_CANDLES}")
                    if candles_held >= MAX_CANDLES:
                        if close_position(position): position_open_candle = None
            else:
                if signal != 0 and now_ts != last_signal_candle:
                    side = "Buy" if signal == 1 else "Sell"
                    log.info(f"🔔 {'LONG 📈' if signal==1 else 'SHORT 📉'}")
                    if open_position(side, price):
                        position_open_candle = now_ts
                        last_signal_candle   = now_ts
                else:
                    log.info("⏳ Aguardando sinal...")
        except Exception as e:
            log.error(f"Erro: {e}")
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    run()
