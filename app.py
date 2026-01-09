import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup
import datetime

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 副官 v1.6 - 台灣戰略版", layout="wide", page_icon="🇹🇼")

# --- 2. 自動化數據引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    try:
        # A. 台幣匯率 (USD/TWD)
        twd_data = yf.Ticker("TWD=X").history(period="1mo")
        if not twd_data.empty:
            results['twd_strong'] = twd_data['Close'].iloc[-1] < twd_data['Close'].iloc[0]
        
        # B. 費半指數 (SOX)
        sox_data = yf.Ticker("^SOX").history(period="1mo")
        if not sox_data.empty:
            results['sox_up'] = sox_data['Close'].iloc[-1] > sox_data['Close'].iloc[0]

        # C. 國發會景氣燈號
        try:
            url = "https://www.ndc.gov.tw/nc_7_400"
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
            results['light_name'] = light_text
            results['light_pos'] = any(x in light_text for x in ['綠', '黃紅', '紅'])
        except:
            results['light_name'] = "掃描失敗"; results['light_pos'] = True

        # D. FRED 數據 (台灣 CPI 與 利率)
        if fred_key:
            fred = Fred(api_key=fred_key)
            results['cpi_ok'] = fred.get_series('TWNCPIALLMINMEI').iloc[-1] <= fred.get_series('TWNCPIALLMINMEI').iloc[-2]
            results['rate_low'] = fred.get_series('INTDSRTWM193N').iloc[-1] <= fred.get_series('INTDSRTWM193N').iloc[-2]
        
        return results
    except Exception as e:
        return None

# --- 3. 戰術分析邏輯 ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        stock = yf.Ticker(ticker.strip().upper())
        df = stock.history(period="1y", timeout=20)
        if df.empty: return None, "無法獲取數據"

        current_price = df['Close'].iloc[-1]
        df_w = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'})
        macd_w = df_w.ta.macd(fast=12, slow=26, signal=9)
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val, d_val = stoch.iloc[-1]['STOCHk_9_3_3'], stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k, prev_d = stoch.iloc[-2]['STOCHk_9_3_3'], stoch.iloc[-2]['STOCHd_9_3_3']
        atr = df.ta.atr(length=14).iloc[-1]

        stop_loss = current_price - (atr * 2.0 * risk_adj)
        take_profit = current_price + (atr * 3.5 * risk_adj)
        golden_cross = (prev_k < prev_d) and (k_val > d_val)

        if macro_score < 30:
            signal, color, msg = "STAY AWAY", "red", "環境極端風險，禁止操作。"
        elif weekly_hist > 0 and k_val < 30 and golden_cross:
            signal, color, msg = "FIRE (狙擊)", "green", "雙週期共振，最佳建倉點。"
        elif weekly_hist > 0 and k_val < 35:
            signal, color, msg = "PREPARE", "orange", "等待板機 (日線金叉)。"
        elif k_val > 80:
            signal, color, msg = "TAKE PROFIT", "blue", "短線過熱，考慮分批獲利。"
        else:
            signal, color, msg = "WAIT", "gray", "趨勢觀察中。"

        return {
            "price": current_price, "change": (current_price/df['Close'].iloc[-2]-1)*100,
            "signal": signal, "color": color, "instruction": msg,
            "stop": stop_loss, "target": take_profit, "k": k_val, "history": df['Close']
        }, None
    except Exception as e: return None, str(e)

# --- 4. 介面渲染 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新台灣宏觀數據"):
        st.session_state['auto_m'] = fetch_auto_macro(fred_key)

    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.6 宏觀戰略指標 (16項)", expanded=True):
        st.caption("自動監控項")
        m1 = st.checkbox("🇹🇼 台幣匯率走強 (資金流)", value=auto.get('twd_strong', True))
        m2 = st.checkbox("📈 費半指數利多 (先行指標)", value=auto.get('sox_up', True))
        m3 = st.checkbox(f"🚦 景氣燈號: {auto.get('light_name','-')}", value=auto.get('light_pos', True))
        m4 = st.checkbox("📊 台灣 CPI 穩定", value=auto.get('cpi_ok', True))
        m5 = st.checkbox("🏦 利率環境友善", value=auto.get('rate_low', True))
        
        st.caption("戰略判定項 (手動)")
        m6 = st.checkbox("外資籌碼持續回流", value=True)
        m7 = st.checkbox("台灣出口訂單成長", value=True)
        m8 = st.checkbox("美債殖利率回落/平穩", value=True)
        m9 = st.checkbox("美元指數 (DXY) 走弱", value=True)
        m10 = st.checkbox("PMI 製造業擴張 (>50)", value=True)
        m11 = st.checkbox("融資餘額無過度膨脹", value=True)
        m12 = st.checkbox("VIX 恐慌指數 < 20", value=True)
        m13 = st.checkbox("台股領先指標上揚", value=True)
        m14 = st.checkbox("S&P 500 維持多頭", value=True)
        m15 = st.checkbox("地緣政治局勢穩定", value=True)
        m16 = st.checkbox("半導體/AI 產業政策支援", value=True)

    score = int(((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16])) / 16) * 100)
    st.metric("宏觀戰略評分", f"{score}/100")
    
    st.markdown("---")
    targets = st.text_input("狙擊目標 (如 2330.TW, NVDA)", value="2330.TW, 2454.TW, NVDA")
    risk_factor = 0.8 if score < 50 else 1.0
    run_btn = st.button("🚀 執行波段分析", use_container_width=True)

# --- 主畫面顯示 ---
st.header("📊 戰術分析儀表板 v1.6")
if run_btn:
    tickers = [t.strip().upper() for t in targets.split(",") if t.strip()]
    cols = st.columns(len(tickers))
    for i, t in enumerate(tickers):
        with cols[i]:
            res, err = get_tactical_analysis(t, score, risk_factor)
            if err: st.error(f"{t}: {err}")
            else:
                st.metric(t, f"${res['price']:.2f}", f"{res['change']:.2f}%")
                if res['color'] == 'green': st.success(f"### {res['signal']}")
                elif res['color'] == 'red': st.error(f"### {res['signal']}")
                else: st.info(f"### {res['signal']}")
                st.write(f"💡 {res['instruction']}")
                st.markdown("#### 🎯 戰術水位線")
                st.table(pd.DataFrame({"戰術項目": ["停損防守", "獲利目標"], "水位": [f"${res['stop']:.2f}", f"${res['target']:.2f}"]}))
                st.line_chart(res['history'].tail(50))
                st.caption(f"日線 K 值: {res['k']:.1f}")
