import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred # 需在 requirements.txt 加入 fredapi

# --- 系統設定 ---
st.set_page_config(page_title="AI 副官 v1.6 - 台灣自動化版", layout="wide", page_icon="🇹🇼")

# --- 1. 自動數據抓取引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    try:
        # A. 透過 yfinance 抓取市場即時數據
        # 1. 台幣匯率 (USD/TWD)
        twd = yf.Ticker("TWD=X").history(period="1mo")['Close']
        results['twd_strong'] = twd.iloc[-1] < twd.iloc[0] # 匯率走強(數值變小)為利多
        
        # 2. 費半指數 (SOX) - 台灣科技股先導
        sox = yf.Ticker("^SOX").history(period="1mo")['Close']
        results['sox_up'] = sox.iloc[-1] > sox.iloc[0]
        
        # 3. 恐慌指數 (VIX)
        vix = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
        results['vix_low'] = vix < 20
        
        # B. 透過 FRED 抓取台灣專屬宏觀數據
        if fred_key:
            fred = Fred(api_key=fred_key)
            # 台灣 CPI (Consumer Price Index for Taiwan)
            try:
                cpi_tw = fred.get_series('TWNCPIALLMINMEI') 
                results['cpi_ok'] = cpi_tw.iloc[-1] <= cpi_tw.iloc[-12] # 通膨沒惡化
            except: results['cpi_ok'] = True
            
            # 台灣 GDP 趨勢 (或是領先指標代理)
            try:
                gdp_tw = fred.get_series('NGDPRSAXDCTW')
                results['gdp_up'] = gdp_tw.iloc[-1] > gdp_tw.iloc[-2]
            except: results['gdp_up'] = True
        else:
            # 若無 Key，預設為 True 避免熔斷
            results['cpi_ok'] = True
            results['gdp_up'] = True
            
        return results
    except Exception as e:
        st.warning(f"自動抓取部分失效，改為手動模式: {e}")
        return None

# --- 2. 核心分析邏輯 (保持 v1.6 穩健原則) ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    # (此處保留上一版本已驗證的雙週期共振與價位計算邏輯...)
    # [為了簡潔，此處省略重複的技術分析代碼，請延用上一版 logic]
    pass 

# --- 3. UI 介面 ---
with st.sidebar:
    st.title("🛡️ 台灣副官戰略中心")
    
    # API 設定
    user_fred_key = st.text_input("輸入 FRED API Key", type="password", help="請至 FRED 官網免費申請")
    
    st.markdown("---")
    st.subheader("🌍 宏觀自動掃描 (台灣核心)")
    
    if st.button("🔄 刷新自動數據"):
        auto_data = fetch_auto_macro(user_fred_key)
        if auto_data:
            st.session_state['auto_macro'] = auto_data
            st.success("數據已自動更新")

    # 顯示自動抓取的結果
    auto_m = st.session_state.get('auto_macro', {})
    
    # 16 項指標 (部分自動, 部分手動)
    st.write("指標狀態：")
    m1 = st.checkbox("🇹🇼 台幣匯率走強 (資金流入)", value=auto_m.get('twd_strong', True))
    m2 = st.checkbox("📈 費半指數上揚 (科技領先)", value=auto_m.get('sox_up', True))
    m3 = st.checkbox("🧘 VIX 恐慌低於 20", value=auto_m.get('vix_low', True))
    m4 = st.checkbox("📊 台灣 CPI 通膨穩定", value=auto_m.get('cpi_ok', True))
    m5 = st.checkbox("🏗️ 台灣 GDP/產出擴張", value=auto_m.get('gdp_up', True))
    # ... 其餘指標保留手動勾選，作為指揮官的最後判斷 ...
    m6 = st.checkbox("地緣政治風險低 (兩岸局勢)", value=True)
    # (其餘 10 項指標以此類推...)

    # 計算總分
    positives = sum([m1, m2, m3, m4, m5, m6]) # 這裡需加上全部 16 項
    total_score = int((positives / 16) * 100)
    st.metric("宏觀戰略總分", total_score)

# --- 後續代碼與上一版相同 (顯示分析結果) ---
