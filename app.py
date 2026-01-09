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
        # 去除空格並轉大寫
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        # 抓取 1 年份數據
        df = stock.history(period="1y", timeout=20)
        
        if df.empty:
            return None, f"代號 '{ticker}' 無法獲取數據，請檢查格式。"

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
        entry_low = current_price - (atr_val * 0.5)
        entry_high = current_price + (atr_val * 0.2)
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
    tickers_input = st.text_input("輸入 3 檔代號 (逗號分隔)", value="NVDA, 2330.TW, TSM")
    macro_score = st.slider("宏觀評分 (v1.6)", 0, 100, 75)
    risk_factor = 0.8 if macro_score < 50 else 1.0
    st.markdown("---")
    # 確保按鈕代碼完整
    run_btn = st.button("🚀 執行全方位掃描", use_container_width=True)

st.header("📊 戰術分析儀表板")

if run_btn:
    # 處理代號列表
    raw_tickers = tickers_input.split(",")
    tickers = [t.strip().upper() for t in raw_tickers if t.strip()]
    
    # 建立對應數量的欄位
    cols = st.columns(len(tickers))
    
    for i, ticker in enumerate(tickers):
        with cols[i]:
            data, error = get_tactical_analysis(ticker, macro_score, risk_factor)
            if error:
                st.error(f"{ticker}: {error}")
            else:
                st.metric(ticker, f"${data['price']:.2f}", f"{data['change_pct']:.2f}%")
                
                if data['color'] == 'green': st.success(f"### 指令: {data['signal']}")
                elif data['color'] == 'red': st.error(f"### 指令: {data['signal']}")
                elif data['color'] == 'orange': st.warning(f"### 指令: {data['signal']}")
                else: st.info(f"### 指令: {data['signal']}")
                
                st.write(f"💡 {data['instruction']}")
                
                st.markdown("#### 🎯 戰術水位線")
                tactical_table = pd.DataFrame({
                    "戰術項目": ["狙擊區間", "停損防守", "獲利目標"],
                    "參考價位": [
                        data['entry_zone'], 
                        f"${data['stop_loss']:.2f}", 
                        f"${data['take_profit']:.2f}"
                    ]
                })
                st.table(tactical_table)
                st.line_chart(data['history'].tail(50))
                st.caption(f"日線 K 值: {data['k_val']:.1f}")
else:
    st.info("👈 請在左側輸入代號並按下按鈕啟動掃描。")
