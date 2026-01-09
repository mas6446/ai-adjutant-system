import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 系統初始化設定 ---
st.set_page_config(page_title="AI 副官 - 戰術分析系統 v1.6", layout="wide", page_icon="🛡️")

# 自定義 CSS 以優化戰情室視覺體驗
st.markdown("""
<style>
    .metric-box {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .stAlert {
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 側邊欄：指揮官輸入區 ---
with st.sidebar:
    st.title("🛡️ 指揮官控制台")
    st.markdown("---")
    
    # 1. 狙擊目標
    st.subheader("🎯 狙擊目標 (Target Acquisition)")
    default_tickers = "NVDA, TSM, 2330.TW"
    tickers_input = st.text_input("輸入 3 檔代號 (逗號分隔)", value=default_tickers)
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    
    st.markdown("---")
    
    # 2. 宏觀數據輸入 (v1.6 核心)
    st.subheader("🌍 宏觀環境參數 (Macro Data)")
    st.info("請根據 16 項宏觀數據模型輸入綜合評分")
    macro_score = st.slider("當前宏觀評分 (0-100)", 0, 100, 75)
    
    # 根據評分調整風險係數
    risk_factor = 1.0
    if macro_score < 50:
        risk_factor = 0.8 # 環境差，收緊止損
        st.warning("⚠️ 宏觀環境不佳，系統已自動收緊風控參數。")
    elif macro_score > 80:
        risk_factor = 1.2 # 環境好，放寬波動容忍
        st.success("✅ 宏觀環境優良，允許較大波段操作。")

    st.markdown("---")
    run_btn = st.button("🚀 啟動戰術掃描", use_container_width=True)
    
    st.markdown("---")
    st.caption("System v1.6 | Powered by AI Adjutant")

# --- 核心運算引擎 ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        # 1. 獲取數據 (抓取 1 年份以計算週線)
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        
        if df.empty:
            return None, "無法獲取報價，請確認代號。"

        current_price = df['Close'].iloc[-1]
        
        # 2. 計算技術指標 (利用 pandas_ta)
        # A. 週線 MACD (趨勢判斷)
        # 將日線 Resample 成週線
        df_weekly = df.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
        # 計算 MACD (12, 26, 9)
        macd_w = df_weekly.ta.macd(fast=12, slow=26, signal=9)
        # 取得最後一週的柱狀圖數值 (Histogram)
        # 注意：pandas_ta 的欄位名稱通常是 MACDh_12_26_9
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        weekly_trend = "多頭 (Bullish)" if weekly_hist > 0 else "空頭/盤整 (Bearish)"
        
        # B. 日線 KD (進場時機)
        # 計算 KD (9, 3, 3)
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k = stoch.iloc[-2]['STOCHk_9_3_3']
        prev_d = stoch.iloc[-2]['STOCHd_9_3_3']
        
        # C. 日線 ATR (波動率風控)
        atr_val = df.ta.atr(length=14).iloc[-1]

        # 3. 戰術邏輯判定 (Tactical Logic)
        signal = "HOLD"
        status_color = "gray"
        instruction = "目前無明確訊號，保持觀望。"
        
        # 判斷是否為「黃金交叉」(K 向上突破 D)
        golden_cross = (prev_k < prev_d) and (k_val > d_val)
        
        if weekly_hist > 0: # 大趨勢多頭
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
        else: # 大趨勢空頭
            signal = "NO ACTION (禁航)"
            status_color = "red"
            instruction = "週線趨勢偏弱，逆勢操作風險極大，建議空手。"

        # 4. 計算關鍵價位 (Level Calculation)
        # 根據 ATR 與 風險係數 計算
        stop_loss = current_price - (atr_val * 2.0 * risk_adj) # 2倍 ATR 止損
        take_profit = current_price + (atr_val * 3.0 * risk_adj) # 3倍 ATR 停利 (盈虧比 1.5:1)
        
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
            "history": df['Close'] # 用於畫圖
        }, None

    except Exception as e:
        return None, str(e)

# --- 主畫面顯示 ---
st.header("📊 戰術分析儀表板 (Tactical Dashboard)")
st.caption(f"執行時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if run_btn:
    cols = st.columns(3) # 建立三欄佈局
    
    for i, ticker in enumerate(tickers):
        # 確保只有前 3 個輸入被處理
        if i >= 3: break
            
        with cols[i]:
            st.subheader(f"目標: {ticker}")
            
            with st.spinner('分析數據中...'):
                data, error = get_tactical_analysis(ticker, macro_score, risk_factor)
            
            if error:
                st.error(f"❌ {error}")
            else:
                # 顯示價格
                delta_color = "normal" if data['change_pct'] == 0 else ("inverse" if data['change_pct'] < 0 else "normal")
                st.metric(
                    label="現價", 
                    value=f"${data['price']:.2f}", 
                    delta=f"{data['change_pct']:.2f}%"
                )
                
                # 顯示戰術指令 (最重要!)
                if data['color'] == 'green':
                    st.success(f"### {data['signal']}")
                elif data['color'] == 'red':
                    st.error(f"### {data['signal']}")
                elif data['color'] == 'orange':
                    st.warning(f"### {data['signal']}")
                else:
                    st.info(f"### {data['signal']}")
                
                st.markdown(f"**📝 副官建議：** {data['instruction']}")
                
                # 關鍵數據表
                st.markdown("#### 關鍵數據")
                metrics_df = pd.DataFrame({
                    "指標": ["週線趨勢", "日線 K 值", "ATR 波動", "停損點 (Stop)", "目標價 (Target)"],
                    "數值": [
                        data['weekly_trend'],
                        f"{data['k_val']:.1f}",
                        f"{data['atr']:.2f}",
                        f"${data['stop_loss']:.2f}",
                        f"${data['take_profit']:.2f}"
                    ]
                })
                st.table(metrics_df)
                
                # 簡單走勢圖
                st.line_chart(data['history'].tail(60)) # 只顯示最近 60 天

else:
    st.info("👈 請在左側輸入代號並點擊「啟動戰術掃描」以開始任務。")