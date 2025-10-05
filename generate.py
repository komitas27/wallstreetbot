# WallStreetBot — RU текст, EN метрики. Без ключей. Генерирует index.html
from datetime import datetime, timezone
import pandas as pd, numpy as np, requests, yfinance as yf, re
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
OUT = "index.html"

# ---------- Утилиты ----------
def pct(a, b):
    try:
        if b == 0 or pd.isna(a) or pd.isna(b):
            return None
        return (a / b - 1) * 100.0
    except:
        return None

def safe_get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

def parse_table(selector, url):
    html = safe_get(url)
    if not html:
        return pd.DataFrame()
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(selector) or soup.find("table")
    if not table:
        return pd.DataFrame()
    rows = []
    for tr in table.find_all("tr"):
        cols = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if cols:
            rows.append(cols)
    df = pd.DataFrame(rows)
    if len(df) > 1 and df.iloc[0].str.contains("Ticker|No.|Company|Sector|Type|Insider", case=False, regex=True).any():
        df.columns = df.iloc[0]
        df = df[1:]
    return df.reset_index(drop=True)

def color(p):
    try:
        v = float(str(p).replace("%",""))
        return "🟢" if v > 1 else ("🔴" if v < -1 else "⚫")
    except:
        return "⚫"

def html_table(rows, header):
    th = "".join([f"<th>{h}</th>" for h in header])
    tr = []
    for r in rows:
        tds = "".join([f"<td>{c}</td>" for c in r])
        tr.append(f"<tr>{tds}</tr>")
    return f"<table border='1' cellpadding='6'><tr>{th}</tr>{''.join(tr)}</table>"

# ---------- Блок 0. Снэпшот рынка (Yahoo) ----------
def get_hist(tickers, period="10d", interval="1d"):
    try:
        df = yf.download(tickers=tickers, period=period, interval=interval, progress=False, threads=True)["Adj Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame()
        return df
    except:
        return pd.DataFrame()

def fetch_snapshot():
    syms = [
        "^GSPC","^NDX","^DJI","^RUT","^VIX",
        "CL=F","BZ=F","NG=F","GC=F","SI=F",
        "DX-Y.NYB","DX=F",
        "BTC-USD","ETH-USD","SOL-USD",
        "^TNX","US2Y","^UST2Y","^IRX"
    ]
    df = get_hist(syms, "10d", "1d")
    out = []

    if df.empty:
        labels = [
            ("SPX (^GSPC)","U.S. large-cap benchmark"),
            ("NDX (^NDX)","Tech-heavy index"),
            ("DJI (^DJI)","Blue chips"),
            ("RUT (^RUT)","Small caps"),
            ("US 2Y","2-year yield"),
            ("US 10Y (^TNX)","10-year yield (÷10 if bps)"),
            ("2s10s Spread","10Y − 2Y (bps)"),
            ("VIX (^VIX)","Volatility index"),
            ("CL=F","WTI crude"),
            ("BZ=F","Brent crude"),
            ("NG=F","Henry Hub gas"),
            ("GC=F","Gold futures"),
            ("SI=F","Silver futures"),
            ("DXY","Dollar index"),
            ("BTC-USD","Bitcoin"),
            ("ETH-USD","Ethereum"),
            ("SOL-USD","Solana"),
        ]
        for n, note in labels:
            out.append((n, "N/A", "N/A", "N/A", note))
        return out

    last = df.tail(1).T
    prev = df.tail(2).head(1).T
    wk   = df.tail(5).head(1).T

    def row(sym, note):
        if sym not in df.columns:
            return (sym, "N/A", "N/A", "N/A", note)
        L = float(last.loc[sym].values[0])
        P = float(prev.loc[sym].values[0]) if sym in prev.index else np.nan
        W = float(wk.loc[sym].values[0]) if sym in wk.index else np.nan
        d1 = pct(L, P)
        w1 = pct(L, W)
        return (sym, f"{d1:.2f}%" if d1 is not None else "N/A",
                     f"{w1:.2f}%" if w1 is not None else "N/A",
                     f"{L:.2f}", note)

    for sym in ["^GSPC","^NDX","^DJI","^RUT","^VIX","CL=F","BZ=F","NG=F","GC=F","SI=F","BTC-USD","ETH-USD","SOL-USD"]:
        note = "Crypto" if "USD" in sym else ("Index/Vol" if sym in ["^GSPC","^NDX","^DJI","^RUT","^VIX"] else "Futures/Index")
        out.append(row(sym, note))

    # DXY
    dxy = ("DXY","N/A","N/A","N/A","Dollar index")
    for s in ["DX-Y.NYB","DX=F"]:
        if s in df.columns:
            L = float(last.loc[s].values[0]); P = float(prev.loc[s].values[0]); W = float(wk.loc[s].values[0])
            dxy = (s, f"{pct(L,P):.2f}%", f"{pct(L,W):.2f}%", f"{L:.2f}", "Dollar index"); break
    out.append(dxy)

    # 10Y
    if "^TNX" in df.columns:
        L = float(last.loc["^TNX"].values[0]) / 10.0
        P = float(prev.loc["^TNX"].values[0]) / 10.0
        W = float(wk.loc["^TNX"].values[0]) / 10.0
        out.append(("US 10Y (^TNX)", f"{pct(L,P):.2f}%", f"{pct(L,W):.2f}%", f"{L:.2f}%", "10-year yield (÷10 if bps)"))
    else:
        out.append(("US 10Y (^TNX)","N/A","N/A","N/A","10-year yield (÷10 if bps)"))

    # 2Y approx
    two = None
    for s in ["US2Y","^UST2Y","^IRX"]:
        if s in df.columns:
            v = float(last.loc[s].values[0])
            if s == "^IRX": v /= 100.0   # приблизительно
            two = v; break
    out.append(("US 2Y","N/A","N/A", f"{two:.2f}%" if two else "N/A", "2-year yield (approx)"))

    # 2s10s
    try:
        ten = float([x[3] for x in out if x[0].startswith("US 10Y")][0].rstrip("%"))
        spr = (ten - (two if two else np.nan)) * 100.0
        out.append(("2s10s Spread","N/A","N/A", f"{spr:.0f} bps" if pd.notna(spr) else "N/A", "10Y − 2Y (bps)"))
    except:
        out.append(("2s10s Spread","N/A","N/A","N/A","10Y − 2Y (bps)"))

    return out

# ---------- Блок 1–7: Finviz / CBOE / CNN / AAII / News ----------
def fetch_finviz_sectors():
    return parse_table("table","https://finviz.com/groups.ashx?g=sector&v=210&o=-perf1")

def fetch_movers():
    g = parse_table("table","https://finviz.com/screener.ashx?v=111&s=ta_topgainers").head(10)
    l = parse_table("table","https://finviz.com/screener.ashx?v=111&s=ta_toplosers").head(10)
    return g, l

def fetch_earnings():
    return parse_table("table","https://finviz.com/screener.ashx?v=111&f=earningsdate_today")

def fetch_insiders_big():
    df = parse_table("table","https://finviz.com/insidertrading.ashx")
    if df.empty:
        return df
    valcol = [c for c in df.columns if "Value" in c]
    valcol = valcol[0] if valcol else df.columns[-1]
    def usd(x):
        try: return float(str(x).replace("$","").replace(",",""))
        except: return 0.0
    df["_v"] = df[valcol].map(usd)
    df = df[df["_v"] >= 1_000_000].drop(columns=["_v"])
    return df.head(20)

def fetch_pcr_fg_aaii():
    html = safe_get("https://www.cboe.com/data/put-call-ratios")
    pcr_idx=pcr_eq=pcr_vix=None
    if html:
        m=re.findall(r"Index Put\/Call Ratio.*?(\d\.\d{2})",html,re.S); pcr_idx=m[0] if m else None
        m=re.findall(r"Total Put\/Call Ratio.*?(\d\.\d{2})",html,re.S); pcr_eq=m[0] if m else None
        m=re.findall(r"VIX Put\/Call Ratio.*?(\d\.\d{2})",html,re.S); pcr_vix=m[0] if m else None
    fg=None
    cnn=safe_get("https://edition.cnn.com/markets/fear-and-greed")
    if cnn:
        x=re.search(r"Fear & Greed Index.*?(\d{1,3})",cnn,re.S)
        if x: fg=x.group(1)
    aaii=None
    ahtml=safe_get("https://www.aaii.com/sentimentsurvey")
    if ahtml:
        x=re.search(r"Bullish.*?(\d{1,2}\.?\d*)\%",ahtml,re.S)
        if x: aaii=x.group(1)
    return pcr_idx,pcr_eq,pcr_vix,fg,aaii

def fetch_upgrades():
    return parse_table("table","https://finviz.com/upgrade.ashx").head(30)

def fetch_news():
    html=safe_get("https://finance.yahoo.com/topic/stock-market-news/")
    items=[]
    if html:
        soup=BeautifulSoup(html,"lxml")
        for a in soup.select("h3 a")[:30]:
            t=a.get_text(strip=True); u=a.get("href","")
            if u and not u.startswith("http"): u="https://finance.yahoo.com"+u
            items.append((t,u))
    return items[:20]

# ---------- Генерация HTML ----------
def build_html():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    snap = fetch_snapshot()
    sectors = fetch_finviz_sectors()
    gain, lose = fetch_movers()
    earn = fetch_earnings()
    ins = fetch_insiders_big()
    pcr_idx, pcr_eq, pcr_vix, fg, aaii = fetch_pcr_fg_aaii()
    upg = fetch_upgrades()
    news = fetch_news()

    html = []
    html.append("<meta charset='utf-8'>")
    html.append(f"<p>🔁 Language: RUS | Metrics: EN-only | Scope: US-only<br>As of {now}</p>")
    html.append("<hr/>")

    # 0) Snapshot
    html.append("<h3>🧭 0️⃣ US Market Snapshot</h3>")
    rows = [(n, f"{d1} {color(d1)}", f"{w1} {color(w1)}", lvl, note) for n,d1,w1,lvl,note in snap]
    html.append(html_table(rows, ["Index / Asset","% Change (1D)","% Change (1W)","Level","Note"]))
    html.append("<p>💬 10Y↓ поддерживает growth; Gold ATH=защита; DXY↑ давит на сырьё/экспорт; VIX↑=страх.</p>")
    html.append("<hr/>")

    # 1) Sectors
    html.append("<h3>🗺️ 1️⃣ Sectors & Market Breadth (Finviz/Yahoo)</h3>")
    html.append(sectors.to_html(index=False,border=1) if not sectors.empty else "<p>N/A</p>")
    html.append("<p>💬 Ротация секторов предвосхищает индекс; breadth показывает «ширину» тренда.</p>")

    # 2) Movers
    html.append("<h3>🚀 2️⃣ Market Movers — Top Gainers / Losers (Prev Day)</h3>")
    html.append("<b>Gainers</b>")
    html.append(gain.to_html(index=False,border=1) if not gain.empty else "<p>N/A</p>")
    html.append("<b>Losers</b>")
    html.append(lose.to_html(index=False,border=1) if not lose.empty else "<p>N/A</p>")
    html.append("<p>💬 Экстремальные движения часто связаны с отчётами/новостями/ротацией.</p>")
    html.append("<hr/>")

    # 3) Earnings
    html.append("<h3>🧾 3️⃣ Earnings — Today (Full / Max Available)</h3>")
    html.append(earn.to_html(index=False,border=1) if not earn.empty else "<p>N/A</p>")
    html.append("<p>💬 Сюрпризы и guidance двигают цену; важно смотреть маржинальность и backlog.</p>")
    html.append("<hr/>")

    # 4) Insiders
    html.append("<h3>🔎 4️⃣ Insiders — Deals &gt; $1,000,000</h3>")
    html.append(ins.to_html(index=False,border=1) if not ins.empty else "<p>N/A</p>")
    html.append("<p>💬 Крупные покупки = уверенность; серийные продажи требуют контекста (vesting, планы).</p>")
    html.append("<hr/>")

    # 5) Options & Sentiment
    html.append("<h3>🧨 5️⃣ Options & Sentiment (SPX/VIX)</h3>")
    rows = [
        ("Put/Call Ratio (Index)",   pcr_idx or "N/A", "PCR>1 = защита"),
        ("Put/Call Ratio (Equity)",  pcr_eq or "N/A", "Высокий PCR = риск-оф"),
        ("Put/Call Ratio (VIX)",     pcr_vix or "N/A", "Смещённость ожиданий по волатильности"),
        ("Fear & Greed",             fg or "N/A",     "Экстремумы часто контртренд"),
        ("AAII Sentiment (Bullish)", (aaii+'%') if aaii else "N/A", "Розничный сентимент"),
    ]
    html.append(html_table(rows, ["Metric","Value","Comment"]))
    html.append("<hr/>")

    # 6) News
    html.append("<h3>📰 6️⃣ News — Most Important (up to 20)</h3>")
    if news:
        html.append("<ul>")
        for t,u in news:
            html.append(f"<li><a target='_blank' href='{u}'>{t}</a></li>")
        html.append("</ul>")
    else:
        html.append("<p>N/A</p>")
    html.append("<p>💬 Сопоставляй новости с движением индексов/секторов; важно время публикации.</p>")
    html.append("<hr/>")

    # 7) Upgrades/Downgrades
    html.append("<h3>📈 7️⃣ Analyst Rating Changes (Upgrades/Downgrades)</h3>")
    html.append(upg.to_html(index=False,border=1) if not upg.empty else "<p>N/A</p>")
    html.append("<p>💬 Рейтинги усиливают тренд; особенно у крупных IB/ресёрч-хаусов.</p>")

    # Sources
    html.append("<hr/><h3>📚 Sources</h3><ul>")
    for s in ["Yahoo Finance","Finviz","CBOE (PCR)","CNN Fear & Greed","AAII"]:
        html.append(f"<li>{s}</li>")
    html.append("</ul>")

    return "\n".join(html)

def main():
    html = build_html()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK: index.html generated")

if __name__ == "__main__":
    main()
