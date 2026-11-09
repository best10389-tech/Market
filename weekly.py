"""Weekly OHLC for the stock universe -> weekly.json, plus a Friday 7 PM Telegram digest."""
import json, os, datetime, urllib.request, urllib.parse
import yfinance as yf

INDICES = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK"}
TOKEN, CHAT_ID = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")

def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default

universe = [s.upper() for s in load("universe.json", [])]
mine = [s.split(".")[0].upper() for s in load("stocks.json", [])]
syms = sorted(set(universe + mine))

def fetch(pairs):
    """pairs: {display_name: yahoo_ticker} -> list of {sym, weeks:[{d,o,h,l,c,v}]}"""
    out, names = [], list(pairs)
    for i in range(0, len(names), 40):
        chunk = {n: pairs[n] for n in names[i:i + 40]}
        try:
            df = yf.download(list(chunk.values()), period="4mo", interval="1wk",
                             group_by="ticker", auto_adjust=False, progress=False, threads=True)
        except Exception as e:
            print("chunk failed", e)
            continue
        for n, t in chunk.items():
            try:
                d = (df[t] if len(chunk) > 1 else df).dropna(subset=["Close"]).tail(10)
                if len(d) < 2:
                    continue
                weeks = [{"d": str(ix.date()), "o": round(float(r.Open), 2), "h": round(float(r.High), 2),
                          "l": round(float(r.Low), 2), "c": round(float(r.Close), 2), "v": int(r.Volume or 0)}
                         for ix, r in d.iterrows()]
                out.append({"sym": n, "weeks": weeks})
            except Exception as e:
                print("skip", n, e)
    return out

stocks = fetch({s: s + ".NS" for s in syms})
for s in stocks:
    s["mine"] = s["sym"] in mine
indices = fetch(INDICES)

if stocks:
    json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "indices": indices, "stocks": stocks}, open("weekly.json", "w"))

def pct(r):
    w = r["weeks"]
    return (w[-1]["c"] - w[-2]["c"]) / w[-2]["c"] * 100

def line(r):
    return f"{r['sym']} {r['weeks'][-1]['c']:,.2f} ({pct(r):+.1f}%)"

if TOKEN and CHAT_ID and stocks and os.environ.get("DIGEST", "1") == "1":
    ranked = sorted(stocks, key=pct, reverse=True)
    repo = os.environ.get("GITHUB_REPOSITORY", "/").split("/")
    msg = ["📊 Weekly market wrap (Friday 7 PM)", ""]
    msg += [f"{r['sym']}: {pct(r):+.1f}% this week" for r in indices]
    msg += ["", "Top gainers: " + ", ".join(line(r) for r in ranked[:5]),
            "", "Top losers: " + ", ".join(line(r) for r in ranked[-5:][::-1])]
    mine_rows = [r for r in stocks if r["mine"]]
    if mine_rows:
        msg += ["", "My stocks:"] + ["• " + line(r) for r in mine_rows]
    msg += ["", f"Weekly dashboard: https://{repo[0]}.github.io/{repo[1]}/weekly.html",
            "Information only, not financial advice."]
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": "\n".join(msg)[:4000]}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data, timeout=20)
