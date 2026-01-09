import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 副官 v1.6b - 規則判斷版", layout="wide", page_icon="🛡️")

# --- 2. 自動化偵蒐引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    try:
        twd_data = yf.Ticker("TWD=X").history(period="1mo")
        results['twd_strong'] = twd_data['Close'].iloc[-1] < twd_data['Close'].iloc[0]
        sox_data = yf.Ticker("^SOX").history(period="1mo")
        results['sox_up'] = sox_data['Close'].iloc[-1] > sox_data['Close'].iloc[0]
        try:
            url = "https://www.ndc.gov.tw/nc_7_400"
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
            results['light_name'] = light_text
            results['light_pos'] = any(x in light_text for x in ['綠', '黃紅', '紅'])
        except:
            results['light_name'] = "掃描失敗"; results['light_pos'] = True
        if fred_key:
            fred = Fred(api_key=fred_key)
            results['cpi_ok'] = fred.get_series('TWNCPIALLMINMEI').iloc[-1] <= fred.get_series('TWNCPIALLMINMEI').iloc[-2]
            results['rate_low'] = fred.get_series('INTDSRTWM193N').iloc[-1] <= fred.get_series('INTDSRTWM193N').iloc[-2]
        return results
    except: return None

# --- 3. 核心技術分析 ---
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
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k, prev_d = stoch.iloc[-2]['STOCHk_9_3_3'], stoch.iloc[-2]['STOCHd_9_3_3']
        atr = df.ta.atr(length=14).iloc[-1]
        stop_loss = current_price - (atr * 2.0 * risk_adj)
        take_profit = current_price + (atr * 3.5 * risk_adj)
        golden_cross = (prev_k < prev_d) and (k_val > d_val)

        if macro_score < 30: signal, color = "STAY AWAY", "red"
        elif weekly_hist > 0 and k_val < 30 and golden_cross: signal, color = "FIRE", "green"
        elif weekly_hist > 0 and k_val < 35: signal, color = "PREPARE", "orange"
        else: signal, color = "WAIT", "gray"
        
        return {"price": current_price, "change": (current_price/df['Close'].iloc[-2]-1)*100,
                "signal": signal, "color": color, "stop": stop_loss, "target": take_profit, 
                "k": k_val, "history": df['Close']}, None
    except Exception as e: return None, str(e)

# --- 4. UI 渲染 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新自動數據"):
        st.session_state['auto_m'] = fetch_auto_macro(fred_key)
    
    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.6b 宏觀定量判斷 (16項)", expanded=True):
        st.caption("自動監控 (指標 1-5)")
        m1 = auto.get('twd_strong', True)
        m2 = auto.get('sox_up', True)
        m3 = auto.get('light_pos', True)
        m4 = auto.get('cpi_ok', True)
        m5 = auto.get('rate_low', True)
        st.write(f"匯率:{m1}, 費半:{m2}, 燈號:{m3}, CPI:{m4}, 利率:{m5}")
        
        st.markdown("---")
        st.caption("數值判定 (指標 6-16)")
        # 您只需要填入數值，系統自動判定 True/False
        v_foreign = st.number_input("外資買賣超 (億)", value=50)
        m6 = v_foreign > 0
        v_yield = st.number_input("10Y美債殖利率 (%)", value=4.2)
        m7 = v_yield < 4.5
        v_dxy = st.number_input("美元指數 DXY", value=103.5)
        m8 = v_dxy < 105.0
        v_vix = st.number_input("VIX 恐慌指數", value=15.0)
        m9 = v_vix < 20.0
        v_pmi = st.number_input("製造業 PMI", value=52.0)
        m10 = v_pmi > 50.0
        v_export = st.number_input("出口訂單年增 (%)", value=5.0)
        m11 = v_export > 0
        
        # 剩餘 5 項保留為指揮官的定性觀察 (如地緣政治)
        m12 = st.checkbox("融資餘額穩定", value=True)
        m13 = st.checkbox("台股領先指標上揚", value=True)
        m14 = st.checkbox("S&P 500 多頭排列", value=True)
        m15 = st.checkbox("地緣政治穩定", value=True)
        m16 = st.checkbox("產業政策利多支援", value=True)

    # 權重計算
    score = int((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16]) / 16) * 100)
    st.metric("宏觀戰略總分", f"{score}/100")
    
    targets = st.text_input("狙擊目標", value="2330.TW, TSM, NVDA")
    risk_factor = 0.8 if score < 50 else 1.0
    run_btn = st.button("🚀 執行波段分析")

# --- 主畫面顯示 ---
st.header("📊 戰術分析儀表板 v1.6b")
if run_btn:
    tickers = [t.strip().upper() for t in targets.split(",") if t.strip()]
    cols = st.columns(len(tickers))
    for i, t in enumerate(tickers):
        with cols[i]:
            res, err = get_tactical_analysis(t, score, risk_factor)
            if err: st.error(err)
            else:
                st.metric(t, f"${res['price']:.2f}", f"{res['change']:.2f}%")
                # 顯示訊號
                if res['color'] == 'green': st.success(f"### {res['signal']}")
                elif res['color'] == 'red': st.error(f"### {res['signal']}")
                else: st.info(f"### {res['signal']}")
                
                # 關鍵價位
                st.markdown("#### 🎯 戰術水位線")
                st.table(pd.DataFrame({"戰術項目": ["停損防守", "獲利目標"], 
                                      "參考價位": [f"${res['stop']:.2f}", f"${res['target']:.2f}"]}))
                st.line_chart(res['history'].tail(50))
