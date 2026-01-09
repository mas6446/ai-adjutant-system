import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
import requests
from bs4 import BeautifulSoup
import datetime
import time
import re
import altair as alt
import math

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 雙週期共振決策系統 v1.74", layout="wide", page_icon="🛡️")

# --- 2. 輔助功能 ---
@st.cache_data(ttl=86400)
def get_stock_name(code):
    try:
        clean_code = code.split('.')[0]
        url = f"https://tw.stock.yahoo.com/quote/{clean_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            title_text = soup.title.text
            match = re.search(r'(.+)\(', title_text)
            if match: return match.group(1).strip()
            if "-" in title_text: return title_text.split('-')[0].strip()
        return code
    except: return code

def smart_get_data(ticker_input):
    ticker_input = ticker_input.strip().upper()
    if "." in ticker_input or not ticker_input.isdigit():
        return ticker_input, yf.Ticker(ticker_input).history(period="1y", timeout=10)
    try_tw = f"{ticker_input}.TW"
    df = yf.Ticker(try_tw).history(period="1y", timeout=10)
    if not df.empty: return try_tw, df
    try_two = f"{ticker_input}.TWO"
    df = yf.Ticker(try_two).history(period="1y", timeout=10)
    if not df.empty: return try_two, df
    return ticker_input, pd.DataFrame()

# --- 3. 資金控管邏輯 ---
def calculate_position_size(total_capital, risk_per_trade_pct, entry_price, stop_loss):
    if entry_price <= stop_loss: return 0, 0, 0
    risk_amount = total_capital * (risk_per_trade_pct / 100.0)
    risk_per_share = entry_price - stop_loss
    max_shares = risk_amount / risk_per_share
    max_sheets = math.floor(max_shares / 1000)
    estimated_cost = max_sheets * 1000 * entry_price
    return max_sheets, estimated_cost, risk_amount

# --- 4. 彈出視窗功能 ---
@st.dialog("📋 雙週期共振戰略手諭")
def show_strategy_modal(score):
    st.caption(f"當前宏觀評分: {score} / 100")
    if score >= 80:
        st.success("🌟 結論：極度利多 (Aggressive)")
        st.markdown("""
        ### 🚀 行動準則
        * **資金水位**：`80% - 100%`
        * **心法**：**「順風滿帆」**。外資與基本面共振，回檔即買點。
        * **策略**：鎖定高 Beta 權值股或強勢龍頭。
        """)
    elif score >= 60:
        st.info("✅ 結論：穩健多頭 (Standard)")
        st.markdown("""
        ### 🛡️ 行動準則
        * **資金水位**：`50% - 70%`
        * **心法**：**「買黑不買紅」**。大趨勢向上但有雜訊，嚴守雙週期訊號。
        * **策略**：績優成長股，避開投機股。
        """)
    elif score >= 40:
        st.warning("⚠️ 結論：震盪觀望 (Defensive)")
        st.markdown("""
        ### 🚧 行動準則
        * **資金水位**：`30% 以下`
        * **心法**：**「打帶跑」**。有獲利快跑，嚴格執行停損。
        * **策略**：防禦型或現金停泊。
        """)
    else:
        st.error("🛑 結論：極端風險 (Cash is King)")
        st.markdown("""
        ### ⛔ 行動準則
        * **資金水位**：`0%` (空手)
        * **心法**：**「覆巢之下無完卵」**。勿抄底，等待 VIX 回落。
        """)
    st.markdown("---")
    if st.button("🫡 收到，關閉視窗"):
        st.rerun()

# --- 5. 自動化偵蒐引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.twse.com.tw/zh/page/trading/fund/BFI82U.html',
    }
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

# --- 6. 戰術分析邏輯 ---
def get_tactical_analysis(df, current_price, macro_score, risk_adj):
    try:
        df_w = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'})
        macd_w = df_w.ta.macd(fast=12, slow=26, signal=9)
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k, prev_d = stoch.iloc[-2]['STOCHk_9_3_3'], stoch.iloc[-2]['STOCHd_9_3_3']
        atr = df.ta.atr(length=14).iloc[-1]
        
        entry_low = current_price - (atr * 0.5)
        entry_high = current_price - (atr * 0.1)
        stop_loss = current_price - (atr * 2.0 * risk_adj)
        tp1 = current_price + (atr * 1.5 * risk_adj)
        tp2 = current_price + (atr * 3.5 * risk_adj)
        golden_cross = (prev_k < prev_d) and (k_val > d_val)

        if macro_score < 40: 
            signal = "STAY AWAY | 禁止進場"
            color = "#FF4B4B" 
            msg = "宏觀環境險惡，現金為王。"
        elif weekly_hist > 0 and k_val < 30 and golden_cross: 
            signal = "FIRE | 全力進攻 (狙擊)"
            color = "#09AB3B" 
            msg = "雙週期共振確認，請參考「狙擊區間」佈局。"
        elif weekly_hist > 0 and k_val < 35: 
            signal = "PREPARE | 準備射擊"
            color = "#FFA500" 
            msg = "價格進入甜蜜區，等待金叉訊號。"
        elif k_val > 80: 
            signal = "TAKE PROFIT | 分批止盈"
            color = "#1E90FF" 
            msg = "短線過熱，建議在 TP1 附近減碼。"
        else: 
            signal = "WAIT | 觀望續抱"
            color = "#808080" 
            msg = "趨勢延續中，持股者續抱。"
        
        plot_df = df['Close'].reset_index()
        plot_df.columns = ['Date', 'Price']
        
        return {
            "price": current_price, 
            "change": (current_price/df['Close'].iloc[-2]-1)*100,
            "signal": signal, "color": color, "msg": msg, 
            "entry_zone": f"${entry_low:.1f} ~ ${entry_high:.1f}", 
            "entry_price_avg": entry_high,
            "stop": stop_loss, "tp1": tp1, "tp2": tp2, "atr": atr, 
            "k": k_val, "plot_data": plot_df
        }, None
    except Exception as e: return None, str(e)

# --- 7. UI 渲染 ---
with st.sidebar:
    st.title("🛡️ AI 雙週期共振決策系統")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新全自動情報"):
        with st.spinner('同步全球數據中...'):
            st.session_state['auto_m'] = fetch_auto_macro(fred_key)
            st.toast("✅ 數據同步完成！")
    
    with st.expander("💰 資金指揮部 (Position Sizing)", expanded=True):
        total_capital = st.number_input("總戰備資金 (TWD)", value=1000000, step=100000)
        risk_pct = st.slider("單筆風險容忍 (%)", 1.0, 5.0, 2.0)
        st.caption(f"🛡️ 單筆最大虧損限制: **${int(total_capital * risk_pct / 100):,}**")

    auto = st.session_state.get('auto_m', {})
    
    with st.expander("🌍 v1.74 數據校正台", expanded=True):
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
    if st.button("📜 閱讀戰略手諭", use_container_width=True):
        show_strategy_modal(score)

    risk_factor = 0.8 if score < 50 else 1.0
    targets_input = st.text_input("狙擊目標 (輸入代號)", value="2330, 2317, 3231, NVDA")
    run_btn = st.button("🚀 執行波段分析")

# --- 主畫面 ---
st.header("📊 AI 雙週期共振決策系統")
if run_btn:
    st.toast("🚀 正在掃描目標...", icon="🔍")
    raw_tickers = [t.strip() for t in targets_input.split(",") if t.strip()]
    cols = st.columns(len(raw_tickers))
    
    for i, raw_t in enumerate(raw_tickers):
        with cols[i]:
            final_ticker, df = smart_get_data(raw_t)
            
            if df.empty:
                st.error(f"{raw_t}: 無法獲取數據")
            else:
                stock_name = get_stock_name(final_ticker)
                current_price = df['Close'].iloc[-1]
                res, err = get_tactical_analysis(df, current_price, score, risk_factor)
                
                if err: st.error(err)
                else:
                    st.subheader(f"{stock_name}")
                    st.metric("現價", f"${res['price']:.2f}", f"{res['change']:.2f}%", delta_color="inverse")
                    
                    st.markdown(f"<h4 style='color: {res['color']}'>{res['signal']}</h4>", unsafe_allow_html=True)
                    st.caption(f"{res['msg']}")

                    sheets, cost, risk_amt = calculate_position_size(total_capital, risk_pct, res['entry_price_avg'], res['stop'])
                    
                    # --- 1. 資金儀表板 (Native Metrics) ---
                    st.markdown("##### 💰 資金配置建議")
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("建議張數", f"{sheets} 張")
                    with c2: st.metric("預估成本", f"${int(cost):,}")
                    with c3: st.metric("潛在虧損", f"-${int(risk_amt):,}", help="若觸發停損的預估虧損金額")
                    
                    st.markdown("---")
                    
                    # --- 2. 戰術表格 (Pandas Styler - 保證無亂碼) ---
                    st.markdown("##### ⚔️ 戰術關鍵價位")
                    
                    # 建立數據
                    tactical_data = [
                        {"戰術性質": "🚀 第二目標", "關鍵價位": f"${res['tp2']:.2f}", "說明": "波段滿足點 (3.5x ATR)"},
                        {"戰術性質": "💰 第一目標", "關鍵價位": f"${res['tp1']:.2f}", "說明": "減碼保本 (1.5x ATR)"},
                        {"戰術性質": "🎯 狙擊區間", "關鍵價位": f"{res['entry_zone']}", "說明": "分批掛單區 (勿追高)"},
                        {"戰術性質": "🛡️ 停損防守", "關鍵價位": f"${res['stop']:.2f}", "說明": "跌破務必撤退"}
                    ]
                    df_tact = pd.DataFrame(tactical_data)
                    
                    # 定義上色邏輯 (Pandas Style)
                    def highlight_rows(row):
                        if "狙擊" in row["戰術性質"]:
                            return ['background-color: #0d2e18; color: #90ee90; font-weight: bold'] * len(row)
                        elif "停損" in row["戰術性質"]:
                            return ['background-color: #381212; color: #ff8a8a'] * len(row)
                        return [''] * len(row)
                    
                    # 渲染表格 (使用 st.table)
                    st.table(df_tact.style.apply(highlight_rows, axis=1))

                    # 3. 圖表
                    chart = alt.Chart(res['plot_data'].tail(60)).mark_line(color='#00AAFF').encode(
                        x=alt.X('Date', axis=alt.Axis(format='%m/%d', title=None)),
                        y=alt.Y('Price', scale=alt.Scale(zero=False), axis=alt.Axis(title=None)),
                        tooltip=['Date', 'Price']
                    ).properties(height=200)
                    st.altair_chart(chart, use_container_width=True)
