"""
📈 Global Stock Dashboard
A live stock tracker built with Streamlit + yfinance + Plotly.

Features
--------
• Search / pick from curated global tickers (US, India, Europe, Asia, Crypto)
• Live current price with day change (colour-coded)
• Key metrics: open, high, low, volume, market cap, 52-week range
• Interactive candlestick / area chart across multiple timeframes
• Fully deployable on share.streamlit.io

Author: Yakub
"""

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# --------------------------------------------------------------------------- #
# Page config
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Global Stock Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Styling (dark theme polish)
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
      /* tighten top padding */
      .block-container {padding-top: 2rem; padding-bottom: 2rem;}

      /* metric cards */
      div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 16px 18px;
      }
      div[data-testid="stMetric"] label p {
        font-size: 0.8rem;
        color: #9aa0a6;
        letter-spacing: 0.02em;
      }

      /* headline price */
      .big-price {
        font-size: 3.1rem;
        font-weight: 700;
        line-height: 1.1;
        margin: 0;
      }
      .price-change {
        font-size: 1.15rem;
        font-weight: 600;
        margin-top: 2px;
      }
      .up   {color: #16c784;}
      .down {color: #ea3943;}
      .ticker-name {color: #9aa0a6; font-size: 0.95rem; margin-bottom: -6px;}
      .company-title {font-size: 1.6rem; font-weight: 700; margin: 0;}

      /* segmented control look for the radio */
      div[role="radiogroup"] {gap: 6px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Curated suggestions
# --------------------------------------------------------------------------- #
SUGGESTIONS = {
    "🇺🇸 US Tech": {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Alphabet (Google)": "GOOGL",
        "Amazon": "AMZN",
        "Meta": "META",
        "Tesla": "TSLA",
    },
    "🇮🇳 India (NSE)": {
        "Reliance Industries": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "Tata Motors": "TATAMOTORS.NS",
    },
    "🌍 Europe / Asia": {
        "ASML (NL)": "ASML",
        "SAP (DE)": "SAP",
        "Toyota (JP)": "TM",
        "Nestlé (CH)": "NSRGY",
        "Samsung (KR)": "005930.KS",
        "Alibaba (CN)": "BABA",
    },
    "₿ Crypto & Index": {
        "Bitcoin USD": "BTC-USD",
        "Ethereum USD": "ETH-USD",
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Nifty 50": "^NSEI",
    },
}

# Flat lookup for the search box: "Apple (AAPL)" -> "AAPL"
FLAT_LOOKUP = {
    f"{name} ({sym})": sym
    for group in SUGGESTIONS.values()
    for name, sym in group.items()
}

# Period -> (yfinance period, interval, chart label)
PERIOD_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "MAX": ("max", "1mo"),
}


# --------------------------------------------------------------------------- #
# Data helpers (cached to avoid hammering Yahoo)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=60, show_spinner=False)
def load_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV history for a symbol."""
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_quote(symbol: str) -> dict:
    """Fetch a lightweight quote snapshot with graceful fallbacks."""
    tk = yf.Ticker(symbol)
    out = {}

    # fast_info is quick and reliable
    try:
        fi = tk.fast_info
        # fast_info behaves like a dict in newer yfinance
        get = fi.get if hasattr(fi, "get") else (lambda k, d=None: getattr(fi, k, d))
        out["last"] = get("lastPrice", get("last_price"))
        out["prev_close"] = get("previousClose", get("previous_close"))
        out["open"] = get("open")
        out["day_high"] = get("dayHigh", get("day_high"))
        out["day_low"] = get("dayLow", get("day_low"))
        out["volume"] = get("lastVolume", get("last_volume"))
        out["market_cap"] = get("marketCap", get("market_cap"))
        out["currency"] = get("currency") or "USD"
        out["year_high"] = get("yearHigh", get("year_high"))
        out["year_low"] = get("yearLow", get("year_low"))
    except Exception:
        pass

    # Try to grab a friendly name (slower, best-effort)
    try:
        info = tk.info
        out["name"] = info.get("longName") or info.get("shortName") or symbol
        out["currency"] = out.get("currency") or info.get("currency") or "USD"
        out["market_cap"] = out.get("market_cap") or info.get("marketCap")
    except Exception:
        out["name"] = symbol

    return out


def fmt_money(value, currency="USD") -> str:
    if value is None:
        return "—"
    symbols = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "JPY": "¥", "KRW": "₩"}
    prefix = symbols.get(currency, "")
    try:
        return f"{prefix}{value:,.2f}"
    except (TypeError, ValueError):
        return "—"


def fmt_big(value) -> str:
    if value is None:
        return "—"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    for unit, div in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(value) >= div:
            return f"{value / div:.2f}{unit}"
    return f"{value:,.0f}"


# --------------------------------------------------------------------------- #
# Sidebar — selection
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("## 📈 Stock Dashboard")
    st.caption("Live global market data via Yahoo Finance")

    st.markdown("#### Search a ticker")
    picked = st.selectbox(
        "Pick from popular names",
        options=list(FLAT_LOOKUP.keys()),
        index=0,
        label_visibility="collapsed",
    )
    default_symbol = FLAT_LOOKUP[picked]

    st.markdown("#### …or type any symbol")
    custom = st.text_input(
        "Any Yahoo symbol (e.g. AAPL, RELIANCE.NS, BTC-USD)",
        value="",
        placeholder="Leave blank to use the pick above",
        label_visibility="collapsed",
    ).strip().upper()

    symbol = custom if custom else default_symbol

    st.divider()
    st.markdown("#### 💡 Suggestions")
    for group, items in SUGGESTIONS.items():
        with st.expander(group, expanded=False):
            st.write(", ".join(f"`{s}`" for s in items.values()))

    st.divider()
    st.caption("Data may be delayed ~15 min. Not financial advice.")


# --------------------------------------------------------------------------- #
# Main — header
# --------------------------------------------------------------------------- #
chart_type = "Area"  # default; toggle set below

quote = load_quote(symbol)
name = quote.get("name", symbol)
currency = quote.get("currency", "USD")
last = quote.get("last")
prev = quote.get("prev_close")

# Compute change
change = pct = None
if last is not None and prev:
    change = last - prev
    pct = (change / prev) * 100 if prev else None

is_up = (change is not None) and (change >= 0)
color_class = "up" if is_up else "down"
arrow = "▲" if is_up else "▼"

head_left, head_right = st.columns([3, 2])

with head_left:
    st.markdown(f"<p class='ticker-name'>{symbol}</p>", unsafe_allow_html=True)
    st.markdown(f"<p class='company-title'>{name}</p>", unsafe_allow_html=True)
    st.markdown(
        f"<p class='big-price'>{fmt_money(last, currency)}</p>",
        unsafe_allow_html=True,
    )
    if change is not None:
        st.markdown(
            f"<p class='price-change {color_class}'>{arrow} "
            f"{fmt_money(abs(change), currency)} ({pct:+.2f}%) today</p>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Live change unavailable for this symbol.")

with head_right:
    st.markdown("<br>", unsafe_allow_html=True)
    chart_type = st.radio(
        "Chart style",
        ["Area", "Candlestick"],
        horizontal=True,
    )

st.divider()

# --------------------------------------------------------------------------- #
# Metrics row
# --------------------------------------------------------------------------- #
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Open", fmt_money(quote.get("open"), currency))
m2.metric("Day High", fmt_money(quote.get("day_high"), currency))
m3.metric("Day Low", fmt_money(quote.get("day_low"), currency))
m4.metric("Prev Close", fmt_money(prev, currency))
m5.metric("Volume", fmt_big(quote.get("volume")))
m6.metric("Market Cap", fmt_big(quote.get("market_cap")))

yr_low = quote.get("year_low")
yr_high = quote.get("year_high")
if yr_low and yr_high:
    st.caption(
        f"52-week range: {fmt_money(yr_low, currency)} — {fmt_money(yr_high, currency)}"
    )

# --------------------------------------------------------------------------- #
# Timeframe selector + chart
# --------------------------------------------------------------------------- #
st.markdown("### 📊 Price chart")
period_label = st.radio(
    "Timeframe",
    list(PERIOD_MAP.keys()),
    index=5,  # 1Y default
    horizontal=True,
    label_visibility="collapsed",
)
yf_period, yf_interval = PERIOD_MAP[period_label]

with st.spinner("Fetching chart data…"):
    try:
        hist = load_history(symbol, yf_period, yf_interval)
    except Exception as e:  # noqa: BLE001
        hist = pd.DataFrame()
        st.error(f"Could not fetch data for **{symbol}**: {e}")

if hist is None or hist.empty:
    st.warning(
        f"No price data returned for **{symbol}** on the {period_label} timeframe. "
        "Double-check the symbol (Yahoo format, e.g. `RELIANCE.NS`, `BTC-USD`)."
    )
else:
    line_color = "#16c784" if is_up else "#ea3943"
    fig = go.Figure()

    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=hist.index,
                open=hist["Open"],
                high=hist["High"],
                low=hist["Low"],
                close=hist["Close"],
                increasing_line_color="#16c784",
                decreasing_line_color="#ea3943",
                name=symbol,
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=hist.index,
                y=hist["Close"],
                mode="lines",
                line=dict(color=line_color, width=2),
                fill="tozeroy",
                fillcolor=(
                    "rgba(22,199,132,0.10)" if is_up else "rgba(234,57,67,0.10)"
                ),
                name="Close",
                hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        showlegend=False,
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")

    st.plotly_chart(fig, use_container_width=True)

    # Period performance summary
    try:
        first_close = float(hist["Close"].iloc[0])
        last_close = float(hist["Close"].iloc[-1])
        p_change = last_close - first_close
        p_pct = (p_change / first_close) * 100 if first_close else 0
        p_color = "up" if p_change >= 0 else "down"
        p_arrow = "▲" if p_change >= 0 else "▼"
        st.markdown(
            f"**{period_label} performance:** "
            f"<span class='{p_color}'>{p_arrow} {fmt_money(abs(p_change), currency)} "
            f"({p_pct:+.2f}%)</span>",
            unsafe_allow_html=True,
        )
    except (IndexError, ValueError):
        pass

    with st.expander("📄 Show raw data"):
        st.dataframe(hist.tail(200), use_container_width=True)

# --------------------------------------------------------------------------- #
# Footer
# --------------------------------------------------------------------------- #
st.divider()
st.caption(
    f"Last updated {dt.datetime.now():%Y-%m-%d %H:%M:%S} · "
    "Source: Yahoo Finance via yfinance · Educational use only, not financial advice."
)
