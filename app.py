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
import textwrap

# --- 1. 系統初始化 ---
st.set_page_config(page_title="AI 雙週期共振決策系統 v1.92", layout="wide", page_icon="🛡️")

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

# --- 3. 資金控管邏輯 (v1.91 繼承：600元門檻) ---
def calculate_position_size(total_capital, risk_per_trade_pct, entry_price, stop_loss):
    if entry_price <= stop_loss: return 0, "0 張", 0
    
    # 1. 基礎運算
    risk_amount = total_capital * (risk_per_trade_pct / 100.0)
    risk_per_share = entry_price - stop_loss
    shares_by_risk = risk_amount / risk_per_share
    shares_by_cash = total_capital / entry_price
    
    raw_shares = int(min(shares_by_risk, shares_by_cash))
    
    # 2. 門檻分流邏輯
    ODD_LOT_THRESHOLD = 600.0
    
    if entry_price < ODD_LOT_THRESHOLD:
        sheets = math.floor(raw_shares / 1000)
        final_shares = sheets * 1000
        display_str = f"{sheets} 張"
        estimated_cost = final_shares * entry_price
    else:
        final_shares = raw_shares
        if final_shares >= 1000 and final_shares % 1000 == 0:
             display_str = f"{int(final_shares/1000)} 張"
        else:
             display_str = f"{final_shares} 股"
        estimated_cost = final_shares * entry_price
    
    return final_shares, display_str, estimated_cost

# --- 4. 彈出視窗功能 ---
@st.dialog("📋 雙週期共振戰略指南 v1.75")
def show_strategy_modal(score):
    st.markdown(f"### 當前宏觀評分: **{score} / 100**")
    
    if score >= 80:
        st.success("🌟 **當前狀態：極度利多 (Aggressive)**")
        st.write("建議採取「擴大戰果」策略，積極尋找高 Beta 標的。")
    elif score >= 60:
        st.info("✅ **當前狀態：穩健多頭 (Standard)**")
        st.write("建議採取「標準配置」策略，嚴守買黑不買紅。")
    elif score >= 40:
        st.warning("⚠️ **當前狀態：震盪觀望 (Defensive)**")
        st.write("建議採取「防禦駕駛」策略，減少曝險。")
    else:
        st.error("🛑 **當前狀態：極端風險 (Cash is King)**")
        st.write("建議「生存優先」，現金為王。")

    st.markdown("---")
    st.markdown("#### ⚔️ v1.75 戰術分類 (矛與盾)")
    st.info("""
    * **🗡️ 戰術矛 (Spear)**：高波動 (>2.5%) 或創高股。**停損嚴守 -3% 或 開盤低點**。
    * **🛡️ 防禦盾 (Shield)**：低波動穩健股。**停損採用 MA20 - 1.5 ATR** (結構性防守)。
    """)
    st.markdown("---")
    if st.button("🫡 收到，關閉指南"):
        st.rerun()

# --- 5. 自動化偵蒐引擎 ---
def fetch_auto_macro(fred_key):
    results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
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

# --- 6. 核心運算：加權 CDP ---
def calculate_weighted_cdp(df):
    try:
        last = df.iloc[-1]
        h = last['High']
        l = last['Low']
        c = last['Close']
        pt = (h + l + 2 * c) / 4
        ah = pt + (h - l)
        nh = 2 * pt - l
        nl = 2 * pt - h
        al = pt - (h - l)
        return {"PT": pt, "AH": ah, "NH": nh, "NL": nl, "AL": al}
    except:
        return {"PT": 0, "AH": 0, "NH": 0, "NL": 0, "AL": 0}

# --- 7. 戰術分析邏輯 (v1.92 核心升級：v1.75 矛與盾) ---
def get_tactical_analysis(df, current_price, macro_score, risk_adj):
    try:
        # 技術指標計算
        df_w = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last'})
        macd_w = df_w.ta.macd(fast=12, slow=26, signal=9)
        weekly_hist = macd_w.iloc[-1]['MACDh_12_26_9']
        stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
        k_val = stoch.iloc[-1]['STOCHk_9_3_3']
        d_val = stoch.iloc[-1]['STOCHd_9_3_3']
        prev_k, prev_d = stoch.iloc[-2]['STOCHk_9_3_3'], stoch.iloc[-2]['STOCHd_9_3_3']
        
        # ATR 與 MA20
        atr = df.ta.atr(length=14).iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        # v1.75 新增：角色判定 (Spear vs Shield)
        # 判定標準：ATR佔比 > 2.5% 或 創20日新高 -> 矛
        atr_pct = (atr / current_price) * 100
        recent_high = df['High'].rolling(20).max().iloc[-1]
        is_breakout = current_price >= recent_high * 0.99
        
        if atr_pct > 2.5 or is_breakout:
            role = "🗡️ 戰術矛 (Spear)"
            role_type = "spear"
            role_color = "#FF4500" # OrangeRed
        else:
            role = "🛡️ 防禦盾 (Shield)"
            role_type = "shield"
            role_color = "#1E90FF" # DodgerBlue

        # v1.75 新增：跳空判定 (Gap Check)
        prev_close = df['Close'].iloc[-2]
        today_open = df['Open'].iloc[-1]
        gap_pct = (today_open - prev_close) / prev_close
        is_big_gap = gap_pct > 0.03 # 3% 跳空

        # CDP 計算
        cdp = calculate_weighted_cdp(df)
        atr_low = current_price - (atr * 0.5)
        
        # 狙擊區間
        entry_target_min = min(atr_low, cdp['NL']) if cdp['NL'] > 0 else atr_low
        entry_target_max = max(atr_low, cdp['NL']) if cdp['NL'] > 0 else current_price
        entry_zone_str = f"${entry_target_min:.1f} ~ ${entry_target_max:.1f}"

        # v1.75 核心：動態停損邏輯
        if is_big_gap:
            # 規則 5.3: 跳空 > 3%，守開盤低點 (這裡取 Open 作為近似)
            stop_loss = today_open
            stop_reason = "Gap"
        elif role_type == "shield":
            # 規則: 盾守 MA20 - 1.5 ATR (結構性止損)
            stop_loss = ma20 - (atr * 1.5)
            stop_reason = "MA20-ATR"
        else:
            # 規則: 矛守 -3% 硬停損 (或 NH 回測，這裡用 -3% 最保險)
            stop_loss = current_price * 0.97
            stop_reason = "Hard-3%"

        # 停利計算
        tp1 = current_price + (atr * 1.5 * risk_adj)
        tp2 = current_price + (atr * 3.5 * risk_adj)
        golden_cross = (prev_k < prev_d) and (k_val > d_val)
        in_sniper_zone = (current_price <= entry_target_max * 1.005)

        # 訊號判定
        if macro_score < 40: 
            signal = "STAY AWAY | 禁止進場"
            color = "#FF4B4B"
            msg = "宏觀風險極高，建議空手。"
        elif weekly_hist > 0 and k_val < 30 and golden_cross: 
            signal = "FIRE | 全力進攻 (狙擊)"
            color = "#09AB3B"
            msg = "雙週期共振確認，建議佈局。"
        elif weekly_hist > 0 and in_sniper_zone: 
            signal = "AMBUSH | 埋伏接單"
            color = "#00CED1"
            msg = "價格已入狙擊區，執行左側掛單。"
        elif weekly_hist > 0 and k_val < 35: 
            signal = "PREPARE | 準備射擊"
            color = "#FFA500"
            msg = "價格進入甜蜜區，等待金叉。"
        elif k_val > 80: 
            signal = "TAKE PROFIT | 分批止盈"
            color = "#1E90FF"
            msg = "過熱，建議減碼。"
        else: 
            signal = "WAIT | 觀望續抱"
            color = "#808080"
            msg = "趨勢延續中。"
        
        plot_df = df['Close'].reset_index()
        plot_df.columns = ['Date', 'Price']
        
        return {
            "price": current_price, 
            "change": (current_price/df['Close'].iloc[-2]-1)*100,
            "signal": signal, "color": color, "msg": msg, 
            "entry_zone": entry_zone_str,
            "cdp_pt": cdp['PT'],
            "cdp_nl": cdp['NL'],
            "cdp_nh": cdp['NH'],
            "entry_price_avg": entry_target_max,
            "stop": stop_loss, "stop_reason": stop_reason,
            "tp1": tp1, "tp2": tp2, "atr": atr, 
            "role": role, "role_color": role_color, # 回傳角色資訊
            "k": k_val, "plot_data": plot_df
        }, None
    except Exception as e: return None, str(e)

# --- 8. UI 渲染 ---
with st.sidebar:
    st.title("🛡️ AI 雙週期共振決策系統")
    st.caption("v1.92 矛與盾實戰版")
    fred_key = st.text_input("FRED API Key", type="password", value="f080910b1d9500925bceb6870cdf9b7c")
    
    if st.button("🔄 刷新全自動情報"):
        with st.spinner('同步全球數據中...'):
            st.session_state['auto_m'] = fetch_auto_macro(fred_key)
            st.toast("✅ 數據同步完成！")
    
    with st.expander("💰 資金指揮部", expanded=True):
        total_capital = st.number_input("戰備資金 (TWD)", value=1000000, step=100000)
        risk_pct = st.slider("風險容忍 (%)", 1.0, 5.0, 2.0)
        st.caption(f"最大虧損限制: **${int(total_capital * risk_pct / 100):,}**")

    # 宏觀數據計算
    auto = st.session_state.get('auto_m', {})
    m1 = auto.get('twd_strong', True); m2 = auto.get('sox_up', True)
    m3 = auto.get('light_pos', True); m4 = auto.get('foreign_net', 0) > 0
    m5 = auto.get('sp500_bull', True); m6 = auto.get('cpi_ok', True); m7 = auto.get('rate_low', True)
    val_yield = auto.get('yield_val', 4.0); m8 = val_yield < 4.5
    val_dxy = auto.get('dxy_val', 104.0); m9 = val_dxy < 105.0
    val_vix = auto.get('vix_val', 15.0); m10 = val_vix < 20.0
    m11 = True; m12 = True 

    score = int((sum([m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]) / 12) * 100)
    
    st.markdown("---")
    st.subheader(f"戰略總分: {score}")
    
    if st.button("📜 閱讀戰略指南", use_container_width=True):
        show_strategy_modal(score)

    risk_factor = 0.8 if score < 50 else 1.0
    
    targets_input = st.text_input("狙擊目標 (輸入代號)", value="", placeholder="例如: 2330, 2317, 2449")
    
    run_analysis = st.button("🚀 執行波段分析", type="primary")

# --- 主畫面 ---
st.header("📊 AI 雙週期共振決策系統")

if run_analysis:
    if not targets_input:
        st.info("請在左側輸入股票代號以開始分析。")
    else:
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
                        st.markdown(f"### {stock_name}")
                        st.metric("現價", f"${res['price']:.2f}", f"{res['change']:.2f}%", delta_color="inverse")
                        
                        # 顯示戰術角色 (v1.92)
                        st.markdown(f"<span style='background-color:{res['role_color']}; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;'>{res['role']}</span>", unsafe_allow_html=True)
                        
                        st.markdown(f"<p style='color: {res['color']}; font-weight: bold; font-size: 16px; margin: 10px 0;'>{res['signal']}</p>", unsafe_allow_html=True)
                        st.caption(f"{res['msg']}")

                        raw_shares, display_str, cost = calculate_position_size(total_capital, risk_pct, res['entry_price_avg'], res['stop'])
                        
                        breakout_price = res['cdp_nh']
                        aggressive_price = res['cdp_pt']
                        sniper_price = res['cdp_nl']
                        stop_reason = res['stop_reason'] # v1.92
                        
                        # 顯示完整成本金額
                        if "張" in display_str:
                            cost_str = f"&#36;{int(cost/1000)}k"
                        else:
                            cost_str = f"&#36;{int(cost):,}"

                        html_content = textwrap.dedent(f"""
                        <div style="background-color: #262730; padding: 10px; border-radius: 5px; font-size: 13px; line-height: 1.4; border: 1px solid #444; margin-bottom: 10px;">
                            <div style="margin-bottom: 4px; padding-bottom: 4px; border-bottom: 1px solid #444;"><strong style="color: #ddd;">💰 資金:</strong> {display_str} <span style="color:#aaa; font-size:11px;">({cost_str})</span></div>
                            <div style="margin-bottom: 2px;"><strong style="color: #ddd;">⚡ 突破:</strong> <span style="color:#FF4500; font-weight:bold;">&#36;{breakout_price:.2f}</span> <span style="color:#888; font-size:11px;">(NH)</span></div>
                            <div style="margin-bottom: 2px;"><strong style="color: #ddd;">🔫 積極:</strong> <span style="color:#FFD700; font-weight:bold;">&#36;{aggressive_price:.2f}</span> <span style="color:#888; font-size:11px;">(PT)</span></div>
                            <div style="margin-bottom: 2px;"><strong style="color: #ddd;">🎯 狙擊:</strong> <span style="color:#90ee90; font-weight:bold;">&#36;{sniper_price:.2f}</span> <span style="color:#888; font-size:11px;">(NL)</span></div>
                            <div style="margin-top: 4px; margin-bottom: 2px;"><strong style="color: #ddd;">🛡️ 停損:</strong> <span style="color:#ff8a8a;">&#36;{res['stop']:.2f}</span> <span style="color:#666; font-size:10px;">({stop_reason})</span></div>
                            <div style="margin-top: 6px; padding-top: 4px; border-top: 1px dashed #555;"><strong style="color: #ddd;">💵 停利:</strong> <span style="color:#87cefa;">&#36;{res['tp1']:.2f}</span> ➜ <span style="color:#87cefa;">&#36;{res['tp2']:.2f}</span></div>
                        </div>
                        """)
                        st.markdown(html_content, unsafe_allow_html=True)

                        chart = alt.Chart(res['plot_data'].tail(60)).mark_line(color='#00AAFF').encode(
                            x=alt.X('Date', axis=alt.Axis(format='%m/%d', title=None)),
                            y=alt.Y('Price', scale=alt.Scale(zero=False), axis=alt.Axis(title=None)),
                            tooltip=['Date', 'Price']
                        ).properties(height=180)
                        st.altair_chart(chart, use_container_width=True)
