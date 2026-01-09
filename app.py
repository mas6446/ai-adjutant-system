import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 系統初始化設定 ---
st.set_page_config(page_title="AI 副官 v1.6 (穩定版)", layout="wide", page_icon="🛡️")

# --- 核心運算引擎 (增強版) ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        # 1. 數據獲取 - 使用更穩定的方式
        stock = yf.Ticker(ticker.strip())
        
        # 抓取 1 年份數據，增加 retry 機制
        df = stock.history(period="1y", timeout=20)
        
        # 偵錯訊息：如果 df 是空的，看看原因
        if df.empty:
            # 嘗試抓取最新一天的價格作為最後檢查
            fast_info = stock.fast_info
            if not fast_info or 'last_price' not in fast_info:
                return None, f"找不到代號 '{ticker}' 的數據。請確認格式 (美股如 NVDA, 台股如 2330.TW)"
            return None, "數據庫暫無歷史資料，請稍後再試。"

        current_price = df['Close'].iloc[-1]
        
        # 2. 計算技術指標 (利用 pandas_ta)
        # 週線 MACD
        df_weekly = df.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
        macd_w = df_weekly.ta.macd(fast=12, slow=26, signal=9)
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        weekly_trend = "多頭 (Bullish)" if weekly_hist > 0 else "空頭/盤整 (Bearish)"
        
        # 日線 KD
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k = stoch.iloc[-2]['STOCHk_9_3_3']
        prev_d = stoch.iloc[-2]['STOCHd_9_3_3']
        
        # 日線 ATR
        atr_val = df.ta.atr(length=14).iloc[-1]

        # 3. 戰術邏輯判定
        signal = "HOLD"
        status_color = "gray"
        instruction = "目前無明確訊號，保持觀望。"
        golden_cross = (prev_k < prev_d) and (k_val > d_val)
        
        if weekly_hist > 0: 
            if k_val < 30 and golden_cross:
                signal = "FIRE (買進)"
                status_color = "green"
                instruction = "雙週期共振確認！週線多頭且日線低檔金叉，建議建倉。"
            elif k_val < 30:
                signal = "PREPARE (準備)"
                status_color = "orange"
                instruction = "價格進入低檔區，密切關注金叉訊號。"
            elif k_val > 80:
                signal = "TAKE PROFIT (注意)"
                status_color = "blue"
                instruction = "日線過熱，不宜追高，考慮分批獲利。"
            else:
                signal = "WAIT (續抱/觀望)"
                status_color = "gray"
                instruction = "趨勢行進中，若有持倉請續抱，空手者勿追。"
        else:
            signal = "NO ACTION (禁航)"
            status_color = "red"
            instruction = "週線趨勢偏弱，逆勢操作風險極大，建議空手。"

        # 4. 計算關鍵價位
        stop_loss = current_price - (atr_val * 2.0 * risk_adj)
        take_profit = current_price + (atr_val * 3.0 * risk_adj)
        
        return {
            "price": current_price,
            "change_pct": (current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100,
            "weekly_trend": weekly_trend,
            "k_val": k_val,
            "signal": signal,
            "color": status_color,
            "instruction": instruction,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "atr": atr_val,
            "history": df['Close']
        }, None

    except Exception as e:
        return None, f"系統異常: {str(e)}"

# --- 側邊欄與介面 ---
with st.sidebar:
    st.title("🛡️ 指揮官控制台")
    tickers_input = st.text_input("輸入代號 (如: NVDA, 2330.TW)", value="NVDA, TSM, 2330.TW")
    macro_score = st.slider("宏觀評分", 0, 100, 75)
    risk_factor = 0.8 if macro_score < 50 else 1.0
    run_btn = st.button("🚀 啟動掃描")

st.header("📊 戰術儀表板")

if run_btn:
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    cols = st.columns(len(tickers))
    
    for i, ticker in enumerate(tickers):
        with cols[i]:
            data, error = get_tactical_analysis(ticker, macro_score, risk_factor)
            if error:
                st.error(f"**{ticker} 錯誤**\n{error}")
            else:
                st.metric(ticker, f"${data['price']:.2f}", f"{data['change_pct']:.2f}%")
                st.markdown(f"**指令: {data['signal']}**")
                st.info(data['instruction'])
                st.line_chart(data['history'].tail(40))
