import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup

# --- 系統設定 ---
st.set_page_config(page_title="AI 副官 v1.6 - 台灣戰略版", layout="wide", page_icon="🇹🇼")

# --- 1. 爬蟲引擎：抓取國發會景氣燈號 ---
def get_taiwan_recession_light():
    try:
        # 爬取國發會最新景氣指標
        url = "https://www.ndc.gov.tw/nc_7_400"
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 抓取燈號名稱 (例如: 綠燈、紅燈)
        light_text = soup.find('td', {'data-title': '景氣對策信號綜合分數'}).find_next('td').text.strip()
        # 判定是否利多 (綠燈、黃藍燈、黃紅燈、紅燈通常視為擴張期)
        is_positive = any(x in light_text for x in ['綠', '黃紅', '紅'])
        return light_text, is_positive
    except:
        return "無法取得", True

# --- 2. 自動宏觀掃描引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    try:
        # A. 市場即時數據
        # 台幣匯率 (USD/TWD) - 匯率走強為利多
        twd = yf.Ticker("TWD=X").history(period="1mo")['Close']
        results['twd_strong'] = twd.iloc[-1] < twd.iloc[0]
        
        # 費半指數 (SOX)
        sox = yf.Ticker("^SOX").history(period="1mo")['Close']
        results['sox_up'] = sox.iloc[-1] > sox.iloc[0]
        
        # B. 台灣景氣燈號
        light_name, light_pos = get_taiwan_recession_light()
        results['light_name'] = light_name
        results['light_pos'] = light_pos

        # C. FRED 台灣數據
        if fred_key:
            fred = Fred(api_key=fred_key)
            # 台灣 CPI
            cpi = fred.get_series('TWNCPIALLMINMEI')
            results['cpi_ok'] = cpi.iloc[-1] <= cpi.iloc[-2]
            # 台灣 貼現率 (反映利率環境)
            rate = fred.get_series('INTDSRTWM193N')
            results['rate_low'] = rate.iloc[-1] <= rate.iloc[-2]
        
        return results
    except Exception as e:
        st.error(f"自動抓取異常: {e}")
        return None

# --- 3. 核心技術分析 (v1.6 Logic) ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    # (此處為您之前已確認的 MACD + KD + ATR 邏輯，為節省篇幅，內容同前版本)
    # ... [略] ...
    pass 

# --- UI 渲染 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    # 自動填入您的 Key
    user_fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新台灣宏觀數據"):
        with st.spinner('掃描國發會與 FRED 數據中...'):
            st.session_state['auto_macro'] = fetch_auto_macro(user_fred_key)

    auto_m = st.session_state.get('auto_macro', {})
    
    with st.expander("🌍 v1.6 宏觀指標自動偵測", expanded=True):
        m1 = st.checkbox("🇹🇼 台幣匯率走強 (外資流入)", value=auto_m.get('twd_strong', True))
        m2 = st.checkbox("📈 費半指數上揚 (半導體利多)", value=auto_m.get('sox_up', True))
        m3 = st.checkbox(f"🚦 台灣景氣燈號: {auto_m.get('light_name', '掃描中')}", value=auto_m.get('light_pos', True))
        m4 = st.checkbox("📊 台灣通膨受控 (CPI)", value=auto_m.get('cpi_ok', True))
        m5 = st.checkbox("🏦 央行利率維持低位", value=auto_m.get('rate_low', True))
        # 其他手動判斷項...
        m6 = st.checkbox("地緣政治風險穩定", value=True)
        # (以此類推共 16 項)

    positives = sum([m1, m2, m3, m4, m5, m6]) 
    final_macro_score = int((positives / 16) * 100)
    st.metric("宏觀總評分", f"{final_macro_score} / 100")

    st.markdown("---")
    tickers_input = st.text_input("狙擊目標 (如 2330.TW, NVDA)", value="2330.TW, 2454.TW, NVDA")
    run_btn = st.button("🚀 執行戰術分析")

# --- 主畫面邏輯與之前相同 ---
# (此處會根據 final_macro_score 計算風險並顯示三欄式的分析結果)
