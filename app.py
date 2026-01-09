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
st.set_page_config(page_title="AI 副官 v1.6g - 台股特化版", layout="wide", page_icon="🛡️")

# --- 2. 輔助功能：中文股名與智慧代號 ---

# 快取功能：查過的股名存起來，不用每次都爬
@st.cache_data(ttl=86400) # 24小時過期
def get_stock_name(code):
    """
    從 Yahoo 股市抓取台股中文名稱
    """
    try:
        # 去掉 .TW 或 .TWO 只留數字
        clean_code = code.split('.')[0]
        url = f"https://tw.stock.yahoo.com/quote/{clean_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 抓取網頁標題通常是 "台積電(2330) - 個股走勢..."
        title = soup.find('h1', {'class': 'C($c-link-text) Fw(b) Fz(24px) My(2px)'})
        if title:
            return title.text.strip()
        return code # 抓不到就回傳代號
    except:
        return code

def smart_get_data(ticker_input):
    """
    智慧判斷上市(.TW)或上櫃(.TWO)
    """
    ticker_input = ticker_input.strip().upper()
    
    # 如果使用者已經打了 .TW 或美股代號，直接用
    if "." in ticker_input or not ticker_input.isdigit():
        stock = yf.Ticker(ticker_input)
        df = stock.history(period="1y", timeout=10)
        return ticker_input, df
    
    # 如果只是數字 (如 2330)，先試 .TW
    try_tw = f"{ticker_input}.TW"
    stock = yf.Ticker(try_tw)
    df = stock.history(period="1y", timeout=10)
    
    if not df.empty:
        return try_tw, df
    
    # 如果 .TW 沒數據，改試 .TWO (上櫃)
    try_two = f"{ticker_input}.TWO"
    stock = yf.Ticker(try_two)
    df = stock.history(period="1y", timeout=10)
    
    if not df.empty:
        return try_two, df
        
    return ticker_input, pd.DataFrame() # 都失敗

# --- 3. 自動化偵蒐引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.twse.com.tw/zh/page/trading/fund/BFI82U.html',
    }
    
    # 爬蟲與 API 邏輯 (維持 v1.6f)
    try:
        timestamp = int(time.time() * 1000)
        url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?date=&response=json&_={timestamp}"
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        if data['stat'] == 'OK':
            foreign_data = next((item for item in data['data'] if item[0] == "外資及陸資(不含外資自營商)"), None)
            if foreign_data:
                results['foreign_net'] = round(float(foreign_data[3].replace(',', '')) / 100000000, 2)
        else: results['foreign_net'] = 0.0
    except: results['foreign_net'] = 0.0

    if fred_key:
        try:
            fred = Fred(api_key=fred_key)
            results['vix_val'] = fred.get_series('VIXCLS').iloc[-1]
            results['yield_val'] = fred.get_series('DGS10').iloc[-1]
            results['cpi_ok'] = fred.get_series('TWNCPIALLMINMEI').iloc[-1] <= fred.get_series('TWNCPIALLMINMEI').iloc[-2]
            results['rate_low'] = fred.get_series('INTDSRTWM193N').iloc[-1] <= fred.get_series('INTDSRTWM193N').iloc[-2]
        except: pass

    # 備用數據源
    try:
        if 'vix_val' not in results or pd.isna(results['vix_val']):
            results['vix_val'] = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
        if 'yield_val' not in results or pd.isna(results['yield_val']):
            results['yield_val'] = yf.Ticker("^TNX").history(period="5d")['Close'].iloc[-1]
            
        results['dxy_val'] = yf.Ticker("DX-Y.NYB").history(period="5d")['Close'].iloc[-1]
        twd = yf.Ticker("TWD=X").history(period="5d")
        results['twd_strong'] = twd['Close'].iloc[-1] < twd['Close'].iloc[0]
        sox = yf.Ticker("^SOX").history(period="5d")
        results['sox_up'] = sox['Close'].iloc[-1] > sox['Close'].iloc[0]
        sp500 = yf.Ticker("^GSPC").history(period="1mo")
        if not sp500.empty:
            results['sp500_bull'] = sp500['Close'].iloc[-1] > sp500['Close'].rolling(20).mean().iloc[-1]
        else: results['sp500_bull'] = False

        url_ndc = "https://www.ndc.gov.tw/nc_7_400"
        res_ndc = requests.get(url_ndc, headers=headers, timeout=5)
        soup = BeautifulSoup(res_ndc.text, 'html.parser')
        light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
        results['light_name'] = light_text
        results['light_pos'] = any(x in light_text for x in ['綠', '黃紅', '紅'])
    except: 
        results['light_name'] = "N/A"; results['light_pos'] = True
    
    return results

# --- 4. 戰術分析邏輯 ---
def get_tactical_analysis(df, current_price, macro_score, risk_adj):
    # 因為 df 已經在 smart_get_data 獲取，這裡直接計算
    try:
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

# --- 5. UI 渲染 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新全自動情報"):
        with st.spinner('同步全球數據中...'):
            st.session_state['auto_m'] = fetch_auto_macro(fred_key)
    
    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.6g 數據校正台", expanded=True):
        m1 = auto.get('twd_strong', True); st.checkbox(f"台幣匯率走強", value=m1, disabled=True)
        m2 = auto.get('sox_up', True); st.checkbox(f"費半指數上揚", value=m2, disabled=True)
        m3 = auto.get('light_pos', True); st.checkbox(f"景氣燈號: {auto.get('light_name','-')}", value=m3, disabled=True)
        m5 = auto.get('sp500_bull', True); st.checkbox(f"S&P500 多頭", value=m5, disabled=True)
        m6 = auto.get('cpi_ok', True); m7 = auto.get('rate_low', True)
        
        st.markdown("---")
        val_foreign_raw = auto.get('foreign_net', 0.0)
        val_foreign = st.number_input("外資買賣超 (億)", value=float(val_foreign_raw))
        m4 = val_foreign > 0

        val_yield_raw = auto.get('yield_val', 4.0)
        if pd.isna(val_yield_raw): val_yield_raw = 4.0
        val_yield = st.number_input("10Y 美債 (%)", value=float(val_yield_raw)); m8 = val_yield < 4.5
        
        val_dxy_raw = auto.get('dxy_val', 104.0)
        if pd.isna(val_dxy_raw): val_dxy_raw = 104.0
        val_dxy = st.number_input("美元指數 DXY", value=float(val_dxy_raw)); m9 = val_dxy < 105.0
        
        val_vix_raw = auto.get('vix_val', 15.0)
        if pd.isna(val_vix_raw): val_vix_raw = 15.0
        val_vix = st.number_input("VIX 恐慌指數", value=float(val_vix_raw)); m10 = val_vix < 20.0

        st.markdown("---")
        v_pmi = st.number_input("製造業 PMI", value=50.0); m11 = v_pmi > 50.0
        v_export = st.number_input("出口訂單年增(%)", value=5.0); m12 = v_export > 0

    score = int((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]) / 12) * 100)
    
    st.markdown("---")
    st.subheader(f"戰略總分: {score}")
    if score >= 80: st.success("🌟 結論：極度利多"); st.caption("水位: 8-10成")
    elif score >= 60: st.info("✅ 結論：穩健多頭"); st.caption("水位: 5-7成")
    elif score >= 40: st.warning("⚠️ 結論：震盪觀望"); st.caption("水位: 3成下")
    else: st.error("🛑 結論：極端風險"); st.caption("水位: 空手")

    risk_factor = 0.8 if score < 50 else 1.0
    # 這裡的預設值改成純數字，方便測試
    targets_input = st.text_input("狙擊目標 (輸入數字即可)", value="2330, 2317, 3231, NVDA")
    run_btn = st.button("🚀 執行波段分析")

# --- 主畫面 ---
st.header("📊 戰術分析儀表板 v1.6g")
if run_btn:
    raw_tickers = [t.strip() for t in targets_input.split(",") if t.strip()]
    cols = st.columns(len(raw_tickers))
    
    for i, raw_t in enumerate(raw_tickers):
        with cols[i]:
            # 1. 智慧獲取數據 (自動判斷 .TW/.TWO)
            final_ticker, df = smart_get_data(raw_t)
            
            if df.empty:
                st.error(f"{raw_t}: 無法獲取數據")
            else:
                # 2. 抓取中文名稱
                stock_name = get_stock_name(final_ticker)
                
                # 3. 執行分析
                current_price = df['Close'].iloc[-1]
                res, err = get_tactical_analysis(df, current_price, score, risk_factor)
                
                if err: st.error(err)
                else:
                    # 標題顯示：中文名稱 + 代號
                    st.subheader(f"{stock_name}")
                    
                    st.metric("現價", f"${res['price']:.2f}", f"{res['change']:.2f}%")
                    
                    if res['color'] == 'green': st.success(f"### {res['signal']}")
                    elif res['color'] == 'red': st.error(f"### {res['signal']}")
                    elif res['color'] == 'blue': st.info(f"### {res['signal']}")
                    else: st.warning(f"### {res['signal']}")
                    
                    st.table(pd.DataFrame({"戰術": ["停損防守", "獲利目標"], "水位": [f"${res['stop']:.2f}", f"${res['target']:.2f}"]}))
                    st.line_chart(res['history'].tail(50))
                    st.caption(f"K值: {res['k']:.1f}")
