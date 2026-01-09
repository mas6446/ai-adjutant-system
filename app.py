import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup
import datetime
import time

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 副官 v1.6f - 抗封鎖修正版", layout="wide", page_icon="🛡️")

# --- 2. 自動化偵蒐引擎 (強化版) ---
def fetch_auto_macro(fred_key):
    results = {}
    # 偽裝成一般瀏覽器的標頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://www.twse.com.tw/zh/page/trading/fund/BFI82U.html',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # A. 證交所 - 外資買賣超 (嘗試抓取)
    try:
        # 加上時間戳記避免被快取
        timestamp = int(time.time() * 1000)
        url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?date=&response=json&_={timestamp}"
        
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        
        if data['stat'] == 'OK':
            # 尋找 "外資及陸資(不含外資自營商)"
            foreign_data = next((item for item in data['data'] if item[0] == "外資及陸資(不含外資自營商)"), None)
            if foreign_data:
                # 移除逗號並轉換單位 (億)
                val_float = float(foreign_data[3].replace(',', ''))
                results['foreign_net'] = round(val_float / 100000000, 2)
            else:
                results['foreign_net'] = 0.0
        else:
            # 可能是假日或無數據
            results['foreign_net'] = 0.0
    except Exception as e:
        # 抓取失敗 (被擋或超時)，回傳 0 讓用戶手動填
        print(f"TWSE Fetch Error: {e}")
        results['foreign_net'] = 0.0

    # B. FRED / Yahoo Finance / 國發會 (維持原樣)
    if fred_key:
        try:
            fred = Fred(api_key=fred_key)
            vix_series = fred.get_series('VIXCLS')
            results['vix_val'] = vix_series.iloc[-1] if not vix_series.empty else 15.0
            
            yield_series = fred.get_series('DGS10')
            results['yield_val'] = yield_series.iloc[-1] if not yield_series.empty else 4.0
            
            results['cpi_ok'] = fred.get_series('TWNCPIALLMINMEI').iloc[-1] <= fred.get_series('TWNCPIALLMINMEI').iloc[-2]
            results['rate_low'] = fred.get_series('INTDSRTWM193N').iloc[-1] <= fred.get_series('INTDSRTWM193N').iloc[-2]
        except: pass

    try:
        # 備用數據源補位
        if 'vix_val' not in results or pd.isna(results['vix_val']):
            vix = yf.Ticker("^VIX").history(period="5d")
            results['vix_val'] = vix['Close'].iloc[-1] if not vix.empty else 15.0
            
        if 'yield_val' not in results or pd.isna(results['yield_val']):
            tnx = yf.Ticker("^TNX").history(period="5d")
            results['yield_val'] = tnx['Close'].iloc[-1] if not tnx.empty else 4.0
            
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d")
        results['dxy_val'] = dxy['Close'].iloc[-1] if not dxy.empty else 104.0
        
        twd = yf.Ticker("TWD=X").history(period="5d")
        results['twd_strong'] = twd['Close'].iloc[-1] < twd['Close'].iloc[0] if not twd.empty else False
        
        sox = yf.Ticker("^SOX").history(period="5d")
        results['sox_up'] = sox['Close'].iloc[-1] > sox['Close'].iloc[0] if not sox.empty else False
        
        sp500 = yf.Ticker("^GSPC").history(period="1mo")
        if not sp500.empty:
            ma20 = sp500['Close'].rolling(20).mean().iloc[-1]
            results['sp500_bull'] = sp500['Close'].iloc[-1] > ma20
        else: results['sp500_bull'] = False

        # 國發會燈號
        url_ndc = "https://www.ndc.gov.tw/nc_7_400"
        res_ndc = requests.get(url_ndc, headers=headers, timeout=10)
        soup = BeautifulSoup(res_ndc.text, 'html.parser')
        light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
        results['light_name'] = light_text
        results['light_pos'] = any(x in light_text for x in ['綠', '黃紅', '紅'])
    except: 
        results['light_name'] = "N/A"; results['light_pos'] = True
    
    return results

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

        if macro_score < 40: signal, color = "STAY AWAY", "red"
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
        with st.spinner('嘗試突破證交所防線並同步數據...'):
            st.session_state['auto_m'] = fetch_auto_macro(fred_key)
    
    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.6f 數據校正台", expanded=True):
        # 1. 自動項
        m1 = auto.get('twd_strong', True); st.checkbox(f"台幣匯率走強", value=m1, disabled=True)
        m2 = auto.get('sox_up', True); st.checkbox(f"費半指數上揚", value=m2, disabled=True)
        m3 = auto.get('light_pos', True); st.checkbox(f"景氣燈號: {auto.get('light_name','-')}", value=m3, disabled=True)
        m5 = auto.get('sp500_bull', True); st.checkbox(f"S&P500 多頭", value=m5, disabled=True)
        m6 = auto.get('cpi_ok', True); m7 = auto.get('rate_low', True)
        
        st.markdown("---")
        st.caption("👇 若自動抓取失敗或為0，請手動輸入")
        
        # 外資買賣超 (重點修正)
        val_foreign_raw = auto.get('foreign_net', 0.0)
        # 如果爬蟲抓到 0 (失敗或假日)，提示用戶輸入
        help_msg = "系統未抓到數據(可能為假日)，請手動輸入" if val_foreign_raw == 0 else "已自動抓取，可修正"
        val_foreign = st.number_input("外資買賣超 (億)", value=float(val_foreign_raw), help=help_msg)
        m4 = val_foreign > 0
        if val_foreign == 0:
            st.warning("⚠️ 請輸入外資數據以確保準確")

        # 10Y 美債
        val_yield_raw = auto.get('yield_val', 4.0)
        if pd.isna(val_yield_raw): val_yield_raw = 4.0
        val_yield = st.number_input("10Y 美債 (%)", value=float(val_yield_raw))
        m8 = val_yield < 4.5
        
        # 美元指數
        val_dxy_raw = auto.get('dxy_val', 104.0)
        if pd.isna(val_dxy_raw): val_dxy_raw = 104.0
        val_dxy = st.number_input("美元指數 DXY", value=float(val_dxy_raw))
        m9 = val_dxy < 105.0
        
        # VIX
        val_vix_raw = auto.get('vix_val', 15.0)
        if pd.isna(val_vix_raw): val_vix_raw = 15.0
        val_vix = st.number_input("VIX 恐慌指數", value=float(val_vix_raw))
        m10 = val_vix < 20.0

        st.markdown("---")
        v_pmi = st.number_input("製造業 PMI", value=50.0); m11 = v_pmi > 50.0
        v_export = st.number_input("出口訂單年增(%)", value=5.0); m12 = v_export > 0

    score = int((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]) / 12) * 100)
    
    st.markdown("---")
    st.subheader(f"戰略總分: {score}")
    if score >= 80: st.success("🌟 結論：極度利多")
    elif score >= 60: st.info("✅ 結論：穩健多頭")
    elif score >= 40: st.warning("⚠️ 結論：震盪觀望")
    else: st.error("🛑 結論：極端風險")

    risk_factor = 0.8 if score < 50 else 1.0
    targets = st.text_input("狙擊目標", value="2330.TW, 2317.TW, NVDA")
    run_btn = st.button("🚀 執行波段分析")

# --- 主畫面 ---
st.header("📊 戰術分析儀表板 v1.6f")
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
