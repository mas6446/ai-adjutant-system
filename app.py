import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 系統初始化設定 ---
st.set_page_config(page_title="AI 副官 v1.6 (戰術完整版)", layout="wide", page_icon="🛡️")

# --- 核心運算引擎 ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        stock = yf.Ticker(ticker.strip())
        df = stock.history(period="1y", timeout=20)
        
        if df.empty:
            return None, f"代號 '{ticker}' 無法獲取數據。"

        current_price = df['Close'].iloc[-1]
        
        # A. 週線趨勢 (MACD)
        df_weekly = df.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
        macd_w = df_weekly.ta.macd(fast=12, slow=26, signal=9)
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        
        # B. 日線指標 (KD + ATR)
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k = stoch.iloc[-2]['STOCHk_9_3_3']
        prev_d = stoch.iloc[-2]['STOCHd_9_3_3']
        atr_val = df.ta.atr(length=14).iloc[-1]

        # C. 戰術邏輯判定
        signal = "HOLD"
        status_color = "gray"
        instruction = "目前無明確訊號，保持觀望。"
        golden_cross = (prev_k < prev_d) and (k_val > d_val)
        
        # D. 價位計算 (核心操作點)
        # 狙擊價位 (Entry Zone): 設在現價附近的支撐或回檔區，此處以現價 - 0.5倍 ATR 為基準
        entry_low = current_price - (atr_val * 0.5)
        entry_high = current_price + (atr_val * 0.2)
        
        # 停損與停利 (依據宏觀權重調整)
        stop_loss = current_price - (atr_val * 2.0 * risk_adj)
        take_profit = current_price + (atr_val * 3.5 * risk_adj)
        
        if weekly_hist > 0: 
            if k_val < 30 and golden_cross:
                signal = "FIRE (立即狙擊)"
                status_color = "green"
                instruction = "雙週期共振！大趨勢向上且小週期回檔結束，建議立即佈局。"
            elif k_val < 35:
                signal = "PREPARE (準備)"
                status_color = "orange"
                instruction = "進入狙擊區，等待金叉板機觸發。"
            elif k_val > 80:
                signal = "EXIT (分批獲利)"
                status_color = "blue"
                instruction = "短線超漲，進入獲利了結區。"
            else:
                signal = "WAIT (觀察)"
                status_color = "gray"
                instruction = "趨勢穩定，無新進場訊號，持倉者續抱。"
        else:
            signal = "STAY AWAY (空方環境)"
            status_color = "red"
            instruction = "週線空頭，不符合波段操作原則，嚴禁入場。"

        return {
            "price": current_price,
            "change_pct": (current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100,
            "signal": signal,
            "color": status_color,
            "instruction": instruction,
            "entry_zone": f"${entry_low:.2f} - ${entry_high:.2f}",
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "k_val": k_val,
            "history": df['Close']
        }, None

    except Exception as e:
        return None, str(e)

# --- UI 渲染 ---
with st.sidebar:
    st.title("🛡️ AI 副官控制台")
    tickers_input = st.text_input("輸入 3 檔代號", value="NVDA, 2330.TW, TSM")
    macro_score = st.slider("宏觀評分 (v1.6)", 0, 100, 75)
    risk_factor = 0.8 if macro_score < 50 else 1.0
    st.markdown("---")
    run_btn = st.button("🚀
