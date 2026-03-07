import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Wyckoff Master: The Unified GGU", layout="wide")
st.title("🏛️ Hệ Thống GGU: Bar Anatomy & Swing Dynamics")
st.markdown("Tổng hợp: Lọc Thanh khoản, Nhận diện SC/BC qua Swing, CHoB/CHoC, và Giải phẫu Bar (Phase C).")

# TÍCH HỢP ~400 MÃ THANH KHOẢN TỐT NHẤT THỊ TRƯỜNG VIỆT NAM
MARKET_TICKERS = [
    "VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB",
    "SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS",
    "HPG","HSG","NKG","VGS","SMC","TLH","HT1","BCC","KSB",
    "VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC",
    "KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","D2D",
    "FPT","MWG","PNJ","FRT","DGW","PET","CMG","ELC","VGI","CTR",
    "GAS","PVD","PVS","BSR","PLX","DGC","DCM","DPM","CSV","GVR",
    "GMD","HAH","VSC","PVT","VOS","PHP",
    "POW","REE","PC1","NT2","GEG","TV2","HDG",
    "VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR",
    "VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","CII",
    "TNG","VGT","GIL","MSH","BVH","BMI","MIG","DHG","BMP","NTP","VNM","MSN","SAB"
]

@st.cache_data(ttl=900)
def get_data(ticker, period="2y"): 
    try:
        df = yf.Ticker(ticker).history(period=period)
        if len(df) < 260: return None
        return df
    except:
        return None

@st.cache_data(ttl=900)
def get_index_data(period="2y"):
    try:
        df = yf.Ticker("^VNINDEX").history(period=period)
        if df is not None and len(df) > 260: return df
        return yf.Ticker("E1VFVN30.VN").history(period=period)
    except:
        return yf.Ticker("E1VFVN30.VN").history(period=period)

def analyze_unified_wyckoff(df, index_df, ticker, min_volume):
    df = df.copy()
    index_df = index_df.copy()
    
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 253: return None 

    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    # =======================================================
    # 0. LIQUIDITY GATEKEEPER
    # =======================================================
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None 

    # =======================================================
    # 1. TOP-DOWN MACRO (RS & ROC)
    # =======================================================
    stock_roc63 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-63]) / combined['Close_s'].iloc[-63] * 100
    idx_roc63 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-63]) / combined['Close_i'].iloc[-63] * 100
    rs_line = combined['Close_s'] / combined['Close_i']
    is_rs_uptrend = rs_line.iloc[-1] > rs_line.rolling(50).mean().iloc[-1]
    is_leader = (stock_roc63 > idx_roc63) and is_rs_uptrend

    # =======================================================
    # 2. IDENTIFY CLIMAX BY CONTEXT (NO MA USED)
    # =======================================================
    # Look back 200 days, leaving the last 40 days for Phase C/D development
    lookback = df.tail(200)
    base_window = lookback.iloc[:-40] 
    if len(base_window) < 60: return None
    
    climax_date = base_window['Volume'].idxmax()
    c_high = float(df.loc[climax_date]['High'])
    c_low = float(df.loc[climax_date]['Low'])
    c_vol = float(df.loc[climax_date]['Volume'])

    # Analyze the 30-bar swing prior to the Climax to define Context
    pre_climax = df.loc[:climax_date].tail(30)
    if len(pre_climax) < 10: return None
    
    pre_highest = float(pre_climax['High'].max())
    pre_lowest = float(pre_climax['Low'].min())
    
    # Is it a drop into a Climax (SC) or a rally into a Climax (BC)?
    is_sc = c_low <= (pre_lowest * 1.03) # Near the bottom of the recent swing
    is_bc = c_high >= (pre_highest * 0.97) # Near the top of the recent swing

    if not (is_sc or is_bc): return None

    tr_high, tr_low, c_type = 0, 0, ""

    # =======================================================
    # 3. SWING DYNAMICS: CHoB & CHoC
    # =======================================================
    after_climax = df.loc[climax_date:]
    
    if is_sc:
        c_type = "Tích Luỹ Đáy (SC)"
        # AR: First major up-swing
        ar_window = after_climax.head(30)
        ar_date = ar_window['High'].idxmax()
        ar_high = float(ar_window.loc[ar_date]['High'])
        
        # CHoB: Must break the downward rhythm (e.g., > 6% bounce)
        if (ar_high - c_low) / c_low < 0.06: return None
        
        # ST: Next down-swing testing the SC
        st_window = df.loc[ar_date:].head(25)
        if st_window.empty: return None
        st_date = st_window['Low'].idxmin()
        st_vol = float(df.loc[st_date]['Volume'])
        
        # CHoC: Volume signature of ST must be exhausted compared to SC
        if st_vol >= c_vol * 0.8: return None 
        
        tr_low, tr_high = c_low, ar_high

    elif is_bc:
        c_type = "Tái Tích Luỹ (BC)"
        # AR: First major down-swing reaction
        ar_window = after_climax.head(30)
        ar_date = ar_window['Low'].idxmin()
        ar_low = float(ar_window.loc[ar_date]['Low'])
        
        # CHoB: Must break the upward FOMO rhythm
        if (c_high - ar_low) / c_high < 0.06: return None
        
        # ST: Next up-swing testing the BC
        st_window = df.loc[ar_date:].head(25)
        if st_window.empty: return None
        st_date = st_window['High'].idxmax()
        st_vol = float(df.loc[st_date]['Volume'])
        
        # CHoC: Volume on the re-test of the high must dry up
        if st_vol >= c_vol * 0.8: return None
        
        tr_high, tr_low = c_high, ar_low

    if tr_low == 0 or (tr_high - tr_low) / tr_low < 0.05: return None

    # =======================================================
    # 4. VSA: OVERALL EFFORT IN THE TRADING RANGE
    # =======================================================
    since_climax = df.loc[climax_date:]
    up_days = since_climax[since_climax['Close'] > since_climax['Open']]
    down_days = since_climax[since_climax['Close'] < since_climax['Open']]
    
    # Reject Distribution traps (Down volume > Up volume)
    if (down_days['Volume'].sum() if not down_days.empty else 0) > (up_days['Volume'].sum() if not up_days.empty else 0): 
        return None 

    # =======================================================
    # 5. BAR ANATOMY & POE (Phase Identification)
    # =======================================================
    current_close = float(df['Close'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    current_high = float(df['High'].iloc[-1])
    current_low = float(df['Low'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    
    box_height = tr_high - tr_low
    bottom_zone = tr_low + (box_height * 0.3)
    middle_zone = tr_low + (box_height * 0.6)
    
    phase, vung_mua_poe, cat_lo = None, "", ""
    
    # PHA C (SPRING): Bar Anatomy Logic from GGU Video
    # 1. Penetration & Proximity: Dips below/near support, but not a total breakdown (>8%)
    if current_low <= tr_low * 1.02 and current_low >= tr_low * 0.92:
        spread = current_high - current_low
        if spread > 0:
            close_position = (current_close - current_low) / spread
            # 2. Anatomy: Close must be off the lows (e.g., upper 50% of the bar) indicating stopping action
            if close_position >= 0.5 and current_vol > float(df['Vol_MA20'].iloc[-1]) * 0.8:
                phase = "Pha C (Spring/Test)"
                vung_mua_poe = f"Mua rũ bỏ (Close off lows) tại {round(current_close, 2)}"
                cat_lo = f"Thủng Low của Spring: {round(current_low * 0.98, 2)}"
            
    # PHA D (SOS / LPS) - Requires Leader Status
    elif current_close > middle_zone and current_close < tr_high * 0.98:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2 and current_close > current_open:
            if is_leader:
                phase = "Pha D (SOS - Điểm Nổ)"
                vung_mua_poe = f"Chờ LPS về {round(middle_zone, 2)}"
                cat_lo = f"Thủng {round(bottom_zone, 2)}"
            
    # PHA E (BREAKOUT) - Requires Leader Status
    elif current_close >= tr_high:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
            if is_leader:
                phase = "Pha E (Breakout)"
                vung_mua_poe = f"Chờ BUEC test {round(tr_high, 2)}"
                cat_lo = f"Thủng {round(tr_high * 0.95, 2)}"

    # PHA A/B (RANGE TRADING)
    elif current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < float(df['Vol_MA20'].iloc[-1]):
            phase = "Pha A/B (Swing TR)"
            vung_mua_poe = f"Swing hỗ trợ {round(tr_low, 2)}"
            cat_lo = f"Thủng cứng: {round(tr_low * 0.96, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Mẫu Hình": c_type,
            "Ngày Climax": climax_date.strftime("%d/%m/%Y"),
            "Động Lực": "✅ CHoB & CHoC",
            "Top-Down": "⭐ Leader" if is_leader else "Tích luỹ",
            "Khung TR": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Giá HT": round(current_close, 2), 
            "Giai đoạn": phase,
            "POE": vung_mua_poe,
            "SL": cat_lo
        }
    return None

# ==========================================
# GIAO DIỆN WEB (TABS)
# ==========================================
tab1, tab2 = st.tabs(["🎯 Auto Radar Toàn Thị Trường", "🧪 Backtest Chiến Dịch Lịch Sử"])

with tab1:
    st.markdown("### 🦅 Quét Tín Hiệu: Giải Phẫu Bar, Pivot & Top-Down (GGU Master)")
    
    min_vol_input = st.number_input(
        "BỘ LỌC THANH KHOẢN: Trung bình Khối lượng 20 phiên tối thiểu:", 
        min_value=50000, max_value=2000000, value=200000, step=50000,
        help="Lọc bỏ mã rác trước khi quét thuật toán."
    )
    
    uploaded_file = st.file_uploader("Tùy chọn: Tải CSV chứa danh sách mã riêng (cột 1 chứa mã)", type=["csv"])
    
    if st.button("🚀 KÍCH HOẠT RADAR TỰ ĐỘNG"):
        results = []
        my_bar = st.progress(0, text="Đang khởi tạo Radar...")
        index_df = get_index_data("2y")
        
        tickers_to_scan = []
        if uploaded_file is not None:
            try:
                df_user = pd.read_csv(uploaded_file, header=None)
                raw_tickers = df_user.iloc[:, 0].dropna().astype(str).tolist()
                tickers_to_scan = [t.strip().upper() + ".VN" if not t.endswith(".VN") else t.strip().upper() for t in raw_tickers]
            except Exception as e:
                st.error("Lỗi đọc file CSV.")
        else:
            tickers_to_scan = [t + ".VN" for t in MARKET_TICKERS]
        
        if index_df is not None and tickers_to_scan:
            total_tickers = len(tickers_to_scan)
            count = 0
            
            try:
                for t in tickers_to_scan:
                    df = get_data(t, "2y")
                    if df is not None:
                        res = analyze_unified_wyckoff(df, index_df, t, min_vol_input)
                        if res: 
                            results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang phân tích Anatomy & Pivot: {t}...")
                    time.sleep(0.01) 
            except Exception as e:
                st.warning("Yahoo Finance API Limit. Đang xuất kết quả tạm...")
                
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Có {len(results)} mã thỏa mãn cấu trúc Bar & Swing Dynamics.")
                df_res = pd.DataFrame(results)[["Mã", "Mẫu Hình", "Ngày Climax", "Động Lực", "Khung TR", "Giá HT", "Top-Down", "Giai đoạn", "POE", "SL"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning(f"Không có mã nào thỏa mãn cấu trúc GGU khắt khe hôm nay.")
        else:
            if index_df is None: st.error("Lỗi kết nối dữ liệu VN-Index.")

with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch Giao dịch")
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.selectbox("Chọn mã muốn Backtest:", [t + ".VN" for t in MARKET_TICKERS])
    with col2:
        st.write("")
        st.write("")
        run_bt = st.button("⚙️ Chạy Mô Phỏng Giao Dịch")

    if run_bt:
        df_bt = get_data(test_ticker, "2y")
        index_bt = get_index_data("2y")
        
        if df_bt is not None and index_bt is not None:
            df_bt.index = pd.to_datetime(df_bt.index).tz_localize(None)
            df_bt['MA50'] = df_bt['Close'].rolling(50).mean() # Dùng MA50 cho Trailing Stop loss lúc quản trị vốn
            
            trades = []
            in_position = False
            entry_price, stop_loss = 0, 0
            trade_type, entry_date = "", ""

            for i in range(200, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-200 : i+1]
                    res = analyze_unified_wyckoff(window, index_bt, test_ticker, 100000)
                    
                    if res:
                        in_position = True
                        entry_price = current_close
                        entry_date = current_date.strftime("%d/%m/%Y")
                        trade_type = res["Giai đoạn"]
                        
                        if "A/B" in trade_type or "Pha C" in trade_type:
                            tr_low = float(res["Khung TR"].split(" - ")[0])
                            stop_loss = tr_low * 0.95 
                        else:
                            stop_loss = float(df_bt['MA50'].iloc[i]) * 0.95

                else:
                    sell_reason, exit_price = "", 0
                    
                    if "A/B" not in trade_type and "Pha C" not in trade_type:
                        current_ma50 = float(df_bt['MA50'].iloc[i])
                        new_stop = current_ma50 * 0.95
                        if new_stop > stop_loss: stop_loss = new_stop 

                    if current_low <= stop_loss:
                        exit_price = stop_loss
                        sell_reason = "Chạm Trailing Stop / Cắt lỗ"

                    if exit_price > 0:
                        profit_pct = ((exit_price - entry_price) / entry_price) * 100
                        trades.append({
                            "Ngày Mua": entry_date,
                            "Vị Thế": trade_type,
                            "Giá Mua": round(entry_price, 2),
                            "Ngày Bán": current_date.strftime("%d/%m/%Y"),
                            "Giá Bán": round(exit_price, 2),
                            "Lý do Bán": sell_reason,
                            "Lợi nhuận (%)": round(profit_pct, 2)
                        })
                        in_position = False 
            
            if trades:
                df_trades = pd.DataFrame(trades)
                win_rate = (len(df_trades[df_trades["Lợi nhuận (%)"] > 0]) / len(df_trades)) * 100
                total_profit = df_trades["Lợi nhuận (%)"].sum()
                
                st.markdown("#### 📊 Báo Cáo Chiến Dịch Giao Dịch")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng lệnh", f"{len(df_trades)}")
                m2.metric("Tỷ lệ Thắng", f"{round(win_rate, 1)}%")
                m3.metric("LN Lũy kế", f"{round(total_profit, 2)}%")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Không có lệnh kích hoạt cho {test_ticker}.")
