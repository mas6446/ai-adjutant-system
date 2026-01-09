import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup
import datetime

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 副官 v1.6d - 戰略結論版", layout="wide", page_icon="🛡️")

# --- 2. 自動化偵蒐引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 1. 證交所 - 外資買賣超
        try:
            url = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json"
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()
            if data['stat'] == 'OK':
                foreign_data = next((item for item in data['data'] if item[0] == "外資及陸資(不含外資自營商)"), None)
                if foreign_data:
                    val_float = float(foreign_data[3].replace(',', ''))
                    results['foreign_net'] = val_float / 100000000 
            else: results['foreign_net'] = 0
        except: results['foreign_net'] = 0

        # 2. 國發會 - 景氣燈號
        try:
            url_ndc = "https://www.ndc.gov.tw/nc_7_400"
            res_ndc = requests.get(url_ndc, headers=headers, timeout=10)
            soup = BeautifulSoup(res_ndc.text, 'html.parser')
            light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
            results['light_name'] = light_text
            results['light_pos'] = any(x in light_text for x in ['綠', '黃紅', '紅'])
        except: results['light_name'] = "N/A"; results['light_pos'] = True

        # 3. 全球關鍵數值
        twd = yf.Ticker("TWD=X").history(period="5d")
        results['twd_strong'] = twd['Close'].iloc[-1] < twd['Close'].iloc[0] if not twd.empty else False
        sox = yf.Ticker("^SOX").history(period="5d")
        results['sox_up'] = sox['Close'].iloc[-1] > sox['Close'].iloc[0] if not sox.empty else False
        sp500 = yf.Ticker("^GSPC").history(period="1mo")
        if not sp500.empty:
            ma20 = sp500['Close'].rolling(20).mean().iloc[-1]
            results['sp500_bull'] = sp500['Close'].iloc[-1] > ma20
        else: results['sp500_bull'] = False
        tnx = yf.Ticker("^TNX").history(period="5d")
        results['yield_val'] = tnx['Close'].iloc[-1] if not tnx.empty else 4.0
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d")
        results['dxy_val'] = dxy['Close'].iloc[-1] if not dxy.empty else 104.0
        vix = yf.Ticker("^VIX").history(period="5d")
        results['vix_val'] = vix['Close'].iloc[-1] if not vix.empty else 15.0

        # 4. FRED 數據
        if fred_key:
            fred = Fred(api_key=fred_key)
            try:
                results['cpi_ok'] = fred.get_series('TWNCPIALLMINMEI').iloc[-1] <= fred.get_series('TWNCPIALLMINMEI').iloc[-2]
                results['rate_low'] = fred.get_series('INTDSRTWM193N').iloc[-1] <= fred.get_series('INTDSRTWM193N').iloc[-2]
            except: results['cpi_ok'] = True; results['rate_low'] = True
        return results
    except: return None

# --- 3. 戰術分析邏輯 ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        stock = yf.Ticker(ticker.strip().upper())
        df = stock.history(period="1y", timeout=20)
        if df.empty: return None, "無數據"
        
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

        if macro_score < 40: signal, color = "STAY AWAY", "red" # 分數低於40直接禁航
        elif weekly_hist > 0 and k_val < 30 and golden_cross: signal, color = "FIRE", "green"
        elif weekly_hist > 0 and k_val < 35: signal, color = "PREPARE", "orange"
        elif k_val > 80: signal, color = "TAKE PROFIT", "blue"
        else: signal, color = "WAIT", "gray"
        
        return {"price": current_price, "change": (current_price/df['Close'].iloc[-2]-1)*100,
                "signal": signal, "color": color, "stop": stop_loss, "target": take_profit, 
                "k": k_val, "history": df['Close']}, None
    except Exception as e: return None, str(e)

# --- 4. UI 渲染 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新全自動情報"):
        with st.spinner('正在彙整全球戰情...'):
            st.session_state['auto_m'] = fetch_auto_macro(fred_key)
    
    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.6c 全量化指標", expanded=True):
        m1 = auto.get('twd_strong', True); st.checkbox(f"台幣匯率走強", value=m1, disabled=True)
        m2 = auto.get('sox_up', True); st.checkbox(f"費半指數上揚", value=m2, disabled=True)
        m3 = auto.get('light_pos', True); st.checkbox(f"景氣燈號: {auto.get('light_name','-')}", value=m3, disabled=True)
        val_foreign = auto.get('foreign_net', 0); m4 = val_foreign > 0; st.checkbox(f"外資買賣超: {val_foreign:.1f}億", value=m4, disabled=True)
        m5 = auto.get('sp500_bull', True); st.checkbox(f"S&P500 多頭排列", value=m5, disabled=True)
        m6 = auto.get('cpi_ok', True); m7 = auto.get('rate_low', True)
        
        st.markdown("---")
        val_yield = auto.get('yield_val', 4.0); m8 = val_yield < 4.5
        st.write(f"10Y 美債: **{val_yield:.2f}%** {'✅' if m8 else '❌ (>4.5)'}")
        val_dxy = auto.get('dxy_val', 104.0); m9 = val_dxy < 105.0
        st.write(f"美元指數: **{val_dxy:.2f}** {'✅' if m9 else '❌ (>105)'}")
        val_vix = auto.get('vix_val', 15.0); m10 = val_vix < 20.0
        st.write(f"VIX 恐慌: **{val_vix:.2f}** {'✅' if m10 else '❌ (>20)'}")

        st.markdown("---")
        v_pmi = st.number_input("製造業 PMI", value=50.0, step=0.1); m11 = v_pmi > 50.0
        v_export = st.number_input("出口訂單年增(%)", value=5.0, step=0.1); m12 = v_export > 0

    score = int((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]) / 12) * 100)
    
    # --- 新增：戰略結論模組 ---
    st.markdown("---")
    st.subheader(f"戰略總分: {score}")
    
    if score >= 80:
        st.success("🌟 結論：極度利多 (Aggressive)")
        st.caption("建議水位：80% - 100% | 積極操作")
    elif score >= 60:
        st.info("✅ 結論：穩健多頭 (Standard)")
        st.caption("建議水位：50% - 70% | 買黑不買紅")
    elif score >= 40:
        st.warning("⚠️ 結論：震盪觀望 (Defensive)")
        st.caption("建議水位：30% 以下 | 嚴設停損")
    else:
        st.error("🛑 結論：極端風險 (Cash is King)")
        st.caption("建議水位：0% (空手) | 禁止進場")

    risk_factor = 0.8 if score < 50 else 1.0
    
    st.markdown("---")
    targets = st.text_input("狙擊目標", value="2330.TW, 2317.TW, NVDA")
    run_btn = st.button("🚀 執行波段分析")

# --- 主畫面顯示 ---
st.header("📊 戰術分析儀表板 v1.6d")
if run_btn:
    tickers = [t.strip().upper() for t in targets.split(",") if t.strip()]
    cols = st.columns(len(tickers))
    for i, t in enumerate(tickers):
        with cols[i]:
            res, err = get_tactical_analysis(t, score, risk_factor)
            if err: st.error(err)
            else:
                st.metric(t, f"${res['price']:.2f}", f"{res['change']:.2f}%")
                if res['color'] == 'green': st.success(f"### {res['signal']}")
                elif res['color'] == 'red': st.error(f"### {res['signal']}")
                elif res['color'] == 'blue': st.info(f"### {res['signal']}")
                else: st.warning(f"### {res['signal']}")
                
                st.table(pd.DataFrame({"戰術": ["停損防守", "獲利目標"], "水位": [f"${res['stop']:.2f}", f"${res['target']:.2f}"]}))
                st.line_chart(res['history'].tail(50))
                st.caption(f"K值: {res['k']:.1f}")
