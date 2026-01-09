import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 系統初始化設定 ---
st.set_page_config(page_title="AI 副官 v1.6 (宏觀自動化版)", layout="wide", page_icon="🛡️")

# --- 核心運算引擎 ---
def get_tactical_analysis(ticker, macro_score, risk_adj):
    try:
        ticker = ticker.strip().upper()
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=20)
        
        if df.empty:
            return None, f"代號 '{ticker}' 無法獲獲數據。"

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

        # C. 價位計算
        entry_low = current_price - (atr_val * 0.5)
        entry_high = current_price + (atr_val * 0.2)
        stop_loss = current_price - (atr_val * 2.0 * risk_adj)
        take_profit = current_price + (atr_val * 3.5 * risk_adj)

        # D. 戰術邏輯 (納入宏觀熔斷)
        signal = "HOLD"
        status_color = "gray"
        instruction = "目前無明確訊號。"
        golden_cross = (prev_k < prev_d) and (k_val > d_val)

        if macro_score < 30: # 宏觀熔斷邏輯
            signal = "STAY AWAY (環境極差)"
            status_color = "red"
            instruction = "16項宏觀數據顯示環境風險過高，即使有技術面訊號也建議空手觀望。"
        elif weekly_hist > 0: 
            if k_val < 30 and golden_cross:
                signal = "FIRE (立即狙擊)"
                status_color = "green"
                instruction = "雙週期共振 + 宏觀支持！建議立即佈局。"
            elif k_val < 35:
                signal = "PREPARE (準備)"
                status_color = "orange"
                instruction = "進入狙擊區，等待日線金叉觸發。"
            elif k_val > 80:
                signal = "EXIT (分批獲利)"
                status_color = "blue"
                instruction = "短線過熱，進入獲利了結區。"
            else:
                signal = "WAIT (觀察)"
                status_color = "gray"
                instruction = "大趨勢向上，目前無新進場點。"
        else:
            signal = "STAY AWAY (週線空頭)"
            status_color = "red"
            instruction = "週線趨勢偏弱，不符合穩健波段原則。"

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

# --- 側邊欄：16 項宏觀數據面板 ---
with st.sidebar:
    st.title("🛡️ 副官戰略中心")
    
    with st.expander("🌍 v1.6 宏觀指標掃描 (16項)", expanded=True):
        st.caption("勾選目前屬「利多」或「擴張」的項")
        m1 = st.checkbox("GDP 成長加速", value=True)
        m2 = st.checkbox("CPI 通膨放緩", value=True)
        m3 = st.checkbox("利率維持/降息預期", value=True)
        m4 = st.checkbox("就業市場強勁")
        m5 = st.checkbox("美元指數回落", value=True)
        m6 = st.checkbox("殖利率曲線正常 (無倒掛)")
        m7 = st.checkbox("企業獲利展望上修", value=True)
        m8 = st.checkbox("製造業 PMI > 50")
        m9 = st.checkbox("消費者信心指數上升")
        m10 = st.checkbox("M2 貨幣供給增加")
        m11 = st.checkbox("地緣政治穩定", value=True)
        m12 = st.checkbox("原物料價格平穩")
        m13 = st.checkbox("VIX 恐慌指數低於 20", value=True)
        m14 = st.checkbox("外資持續流入")
        m15 = st.checkbox("技術領先優勢 (AI/半導體)")
        m16 = st.checkbox("政策面利多支援")

        # 計算總分 (每項約 6.25 分)
        positives = sum([m1,m2,m3,m4,m5,m6,m7,m8,m9,m10,m11,m12,m13,m14,m15,m16])
        final_macro_score = int((positives / 16) * 100)
        
        st.markdown(f"### 宏觀總分: **{final_macro_score}**")
        if final_macro_score < 30: st.error("🔥 警報：極端風險環境")
        elif final_macro_score > 70: st.success("🌟 提示：優質操作環境")

    st.markdown("---")
    tickers_input = st.text_input("輸入 3 檔代號", value="NVDA, 2330.TW, TSM")
    risk_factor = 0.8 if final_macro_score < 50 else 1.0
    run_btn = st.button("🚀 執行全方位掃描", use_container_width=True)

# --- 主畫面 ---
st.header("📊 戰術分析儀表板 v1.6")
if run_btn:
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    cols = st.columns(len(tickers))
    for i, ticker in enumerate(tickers):
        with cols[i]:
            data, error = get_tactical_analysis(ticker, final_macro_score, risk_factor)
            if error:
                st.error(f"{ticker}: {error}")
            else:
                st.metric(ticker, f"${data['price']:.2f}", f"{data['change_pct']:.2f}%")
                if data['color'] == 'green': st.success(f"### {data['signal']}")
                elif data['color'] == 'red': st.error(f"### {data['signal']}")
                elif data['color'] == 'orange': st.warning(f"### {data['signal']}")
                else: st.info(f"### {data['signal']}")
                
                st.write(f"💡 {data['instruction']}")
                st.markdown("#### 🎯 戰術水位線")
                st.table(pd.DataFrame({"戰術項目": ["狙擊區間", "停損防守", "獲利目標"], 
                                      "參考價位": [data['entry_zone'], f"${data['stop_loss']:.2f}", f"${data['take_profit']:.2f}"]}))
                st.line_chart(data['history'].tail(50))
else:
    st.info("👈 請檢查左側 16 項宏觀數據後，點擊按鈕啟動掃描。")
