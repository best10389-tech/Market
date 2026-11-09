"""Fetches Indian index + stock prices, writes data.json, sends Telegram alerts on big moves."""
import json, os, datetime, urllib.request, urllib.parse
import yfinance as yf

INDICES = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
ALERT_PERCENT = float(os.environ.get("ALERT_PERCENT", "1.0"))
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def quote(sym, with_history=False):
    t = yf.Ticker(sym)
    fi = t.fast_info
    price, prev = float(fi["lastPrice"]), float(fi["previousClose"])
    row = {"price": round(price, 2), "prev": round(prev, 2)}
    if with_history:
        closes = [round(float(v), 2) for v in t.history(period="10d")["Close"].dropna().tail(5)]
        row["history"] = (closes[:-1] + [round(price, 2)]) if closes else [prev, price]
    return row

def send(msg):
    if TOKEN and CHAT_ID:
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data, timeout=15)

indices, stocks, alerts = [], [], {}
for name, sym in INDICES.items():
    try:
        q = quote(sym, True)
        indices.append({"name": name, **q})
        pct = (q["price"] - q["prev"]) / q["prev"] * 100
        if abs(pct) >= ALERT_PERCENT:
            alerts[f"{name}:{'up' if pct > 0 else 'down'}"] = f"{name} is {'UP' if pct > 0 else 'DOWN'} {abs(pct):.2f}% today ({q['price']:,.0f})"
    except Exception as e:
        print("skip", name, e)

try:
    for sym in json.load(open("stocks.json")):
        try:
            stocks.append({"name": sym.split(".")[0], **quote(sym)})
        except Exception as e:
            print("skip", sym, e)
except FileNotFoundError:
    pass

if indices:  # only overwrite when we got real data
    with open("data.json", "w") as f:
        json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "indices": indices, "stocks": stocks}, f)

today = datetime.date.today().isoformat()
try:
    seen = json.load(open("alerted.json"))
except Exception:
    seen = {}
if seen.get("date") != today:
    seen = {"date": today, "sent": []}
for key, text in alerts.items():
    if key not in seen["sent"]:
        send("📈 " + text)
        seen["sent"].append(key)
json.dump(seen, open("alerted.json", "w"))
