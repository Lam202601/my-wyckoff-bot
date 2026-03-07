import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Wyckoff Master: Auto Time-Window", layout="wide")
st.title("🏛️ Hệ Thống GGU: Quét Tín Hiệu Đa Khung Thời Gian")
st.markdown("Tự động quét ~400 mã. Tìm kiếm tín hiệu Wyckoff (Phase C/D/E) xuất hiện trong 2 tuần gần nhất.")

# DATABASE TÍCH HỢP SẴN: ~400 MÃ THANH KHOẢN TỐT NHẤT
MARKET_TICKERS = [
    "VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB","NAB","BAB","KLB",
    "SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS","VIG",
    "HPG","HSG","NKG","VGS","SMC","TLH","HT1","BCC","KSB","DHA","VLB",
    "VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","KHG","SCR","HQC","DXS",
    "KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","TIP",
    "FPT","MWG","PNJ","FRT","DGW","PET","CMG","ELC","VGI","CTR","SAB","VNM","MSN","KDC","MCH","SBT","QNS",
    "GAS","PVD","PVS","BSR","PLX","OIL","PVC","DGC","DCM","DPM","CSV","GVR","BFC","LAS",
    "GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP",
    "POW","REE","PC1","NT2","GEG","TV2","HDG","QTP","HND","BWE","TDM",
    "VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","ASM",
    "VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","CII",
    "TNG","VGT","GIL","MSH","STK","TCM","BVH","BMI","MIG","PVI","DHG","IMP","BMP","NTP","AAA","GEX"
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

def analyze_pure_wyckoff(df, index_df, ticker, min_volume, signal_lookback):
    df = df.copy()
    index_df = index_df.copy()
    
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 253: return None 

    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    # BƯỚC 0: LỌC THANH KHOẢN (Loại Penny)
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None 

    # BƯỚC 1: ĐO LƯỜNG TOP-DOWN
    stock_roc63 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-63]) / combined['Close_s'].iloc[-63] * 100
    idx_roc63 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-63]) / combined['Close_i'].iloc[-63] * 100
    rs_line = combined['Close_s'] / combined['Close_i']
    is_rs_uptrend = rs_line.iloc[-1] > rs_line.rolling(50).mean().iloc[-1]
    is_leader = (stock_roc63 > idx_roc63) and is_rs_uptrend

    # BƯỚC 2: TÌM SỰ KIỆN CLIMAX (PURE PRICE ACTION)
    lookback = df.tail(200)
    base_window = lookback.iloc[:-40] 
    if len(base_window) < 50: return None
    
    climax_date = base_window['Volume'].idxmax()
    c_high = float(df.loc[climax_date]['High'])
    c_low = float(df.loc[climax_date]['Low'])
    c_vol = float(df.loc[climax_date]['Volume'])

    pre_climax = df.loc[:climax_date].tail(30)
    if len(pre_climax) < 10: return None
    pre_highest = float(pre_climax['High'].max())
    pre_lowest = float(pre_climax['Low'].min())

    is_sc = c_low <= pre_lowest * 1.03 
    is_bc = c_high >= pre_highest * 0.97 

    if not (is_sc or is_bc): return None

    tr_high, tr_low, c_type = 0, 0, ""

    # BƯỚC 3: ĐỘNG LỰC HỌC SÓNG (CHoB / CHoC)
    after_climax = df.loc[climax_date:]
    if is_sc:
        c_type = "Tích Luỹ Đáy (SC)"
        ar_date = after_climax.head(30)['High'].idxmax()
        ar_high = float(after_climax.loc[ar_date]['High'])
        if (ar_high - c_low) / c_low < 0.05: return None
        
        after_ar = df.loc[ar_date:].head(25)
        if after_ar.empty: return None
        st_date = after_ar['Low'].idxmin()
        st_vol = float(df.loc[st_date]['Volume'])
        if st_vol >= c_vol * 0.8: return None 
        
        tr_low, tr_high = c_low, ar_high

    elif is_bc:
        c_type = "Tái Tích Luỹ (BC)"
        ar_date = after_climax.head(30)['Low'].idxmin()
        ar_low = float(after_climax.loc[ar_date]['Low'])
        if (c_high - ar_low) / c_high < 0.05: return None
        
        after_ar = df.loc[ar_date:].head(25)
        if after_ar.empty: return None
        st_date = after_ar['High'].idxmax()
        st_vol = float(df.loc[st_date]['Volume'])
        if st_vol >= c_vol * 0.8: return None
        
        tr_high, tr_low = c_high, ar_low

    if tr_low == 0 or tr_low >= tr_high or (tr_high - tr_low) / tr_low < 0.05: return None

    # BƯỚC 4: LỌC BẪY PHÂN PHỐI TRONG TR
    since_climax = df.loc[climax_date:]
    up_days = since_climax[since_climax['Close'] > since_climax['Open']]
    down_days = since_climax[since_climax['Close'] < since_climax['Open']]
    if (down_days['Volume'].sum() if not down_days.empty else 0) > (up_days['Volume'].sum() if not up_days.empty else 0): 
        return None 

    # =======================================================
    # BƯỚC 5: TÌM TÍN HIỆU TRONG CỬA SỔ THỜI GIAN (LOOKBACK)
    # =======================================================
    box_height = tr_high - tr_low
    bottom_zone = tr_low + (box_height * 0.3)
    middle_zone = tr_low + (box_height * 0.6)
    
    latest_phase = None
    latest_poe = ""
    latest_sl = ""
    signal_date = ""

    # Quét từ ngày `Hiện tại - Lookback` cho đến Hiện tại
    scan_start = max(0, len(df) - signal_lookback)
    
    for i in range(scan_start, len(df)):
        curr_close = float(df['Close'].iloc[i])
        curr_open = float(df['Open'].iloc[i])
        curr_high = float(df['High'].iloc[i])
        curr_low = float(df['Low'].iloc[i])
        curr_vol = float(df['Volume'].iloc[i])
        curr_vol_ma20 = float(df['Vol_MA20'].iloc[i])
        curr_date = df.index[i].strftime("%d/%m/%Y")
        
        phase = None
        vung_mua_poe = ""
        cat_lo = ""
        
        # Pha C (Spring - Rũ bỏ)
        if curr_low <= tr_low * 1.03 and curr_low >= tr_low * 0.90:
            spread = curr_high - curr_low
            if spread > 0:
                close_position = (curr_close - curr_low) / spread
                if close_position >= 0.4 and curr_vol > curr_vol_ma20 * 0.8:
                    phase = "Pha C (Spring/Test)"
                    vung_mua_poe = f"Mua tại {round(curr_close, 2)}"
                    cat_lo = f"Thủng {round(curr_low * 0.98, 2)}"
                
        # Pha D (SOS - Điểm nổ)
        elif curr_close > middle_zone and curr_close < tr_high * 0.98:
            if curr_vol > curr_vol_ma20 * 1.2 and curr_close > curr_open:
                if is_leader:
                    phase = "Pha D (SOS)"
                    vung_mua_poe = f"Chờ LPS về {round(middle_zone, 2)}"
                    cat_lo = f"Thủng {round(bottom_zone, 2)}"
                
        # Pha E (Breakout đỉnh hộp)
        elif curr_close >= tr_high:
            if curr_vol > curr_vol_ma20 * 1.5:
                if is_leader:
                    phase = "Pha E (Breakout)"
                    vung_mua_poe = f"Chờ BUEC {round(tr_high, 2)}"
                    cat_lo = f"Thủng {round(tr_high * 0.95, 2)}"

        # Ghi nhận tín hiệu nếu có (Sẽ ưu tiên ghi đè tín hiệu gần nhất)
        if phase:
            latest_phase = phase
            latest_poe = vung_mua_poe
            latest_sl = cat_lo
            signal_date = curr_date

    # Nếu tìm thấy tín hiệu trong X ngày qua, trả về kết quả
    if latest_phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Ngày Báo Tín Hiệu": signal_date, # Thêm cột ngày báo tín hiệu
            "Mẫu Hình": c_type,
            "Khung TR": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Giá Hiện Tại": round(float(df['Close'].iloc[-1]), 2), # Cập nhật giá mới nhất
            "Tín Hiệu (Gần đây)": latest_phase,
            "Top-Down": "⭐ Leader" if is_leader else "Tích luỹ",
            "POE": latest_poe,
            "SL": latest_sl
        }
    return None

# ==========================================
# GIAO DIỆN WEB (TABS)
# ==========================================
tab1, tab2 = st.tabs(["🎯 Auto Radar (Tín Hiệu Đa Phiên)", "🧪 Backtest Lịch Sử"])

with tab1:
    st.markdown("### 🦅 Quét Tín Hiệu: Bắt Sóng Wyckoff Trong Cửa Sổ Thời Gian")
    
    colA, colB = st.columns(2)
    with colA:
        min_vol_input = st.number_input(
            "BỘ LỌC THANH KHOẢN (Cổ phiếu/Phiên):", 
            min_value=50000, max_value=2000000, value=200000, step=50000
        )
    with colB:
        signal_lookback_input = st.number_input(
            "SỐ PHIÊN QUÉT TÍN HIỆU (Lookback):", 
            min_value=1, max_value=20, value=10, step=1,
            help="10 = Tìm các tín hiệu xuất hiện trong vòng 2 tuần qua (10 phiên)."
        )
    
    if st.button("🚀 KÍCH HOẠT RADAR"):
        results = []
        my_bar = st.progress(0, text="Khởi tạo Radar tự động hoàn toàn...")
        index_df = get_index_data("2y")
        
        tickers_to_scan = [t + ".VN" for t in MARKET_TICKERS]
        
        if index_df is not None:
            total_tickers = len(tickers_to_scan)
            count = 0
            
            for t in tickers_to_scan:
                df = get_data(t, "2y")
                if df is not None:
                    res = analyze_pure_wyckoff(df, index_df, t, min_vol_input, signal_lookback_input)
                    if res: 
                        results.append(res)
                count += 1
                my_bar.progress(count / total_tickers, text=f"Đang dò tìm tín hiệu {signal_lookback_input} ngày qua: {t}...")
                time.sleep(0.01) 
                
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Có {len(results)} mã phát tín hiệu Wyckoff trong {signal_lookback_input} phiên gần nhất.")
                # Sắp xếp hiển thị
                df_res = pd.DataFrame(results)[["Mã", "Ngày Báo Tín Hiệu", "Mẫu Hình", "Tín Hiệu (Gần đây)", "Khung TR", "Giá Hiện Tại", "Top-Down", "POE", "SL"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning(f"Thị trường ảm đạm: Không có mã nào phát tín hiệu GGU trong {signal_lookback_input} phiên qua.")
        else:
            st.error("Lỗi kết nối dữ liệu VN-Index.")

with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch Giao dịch Lịch sử")
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
            df_bt['MA50'] = df_bt['Close'].rolling(50).mean()
            
            trades = []
            in_position = False
            entry_price, stop_loss = 0, 0
            trade_type, entry_date = "", ""

            # Backtest quét từng phiên
            for i in range(200, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-200 : i+1]
                    # Trong lúc backtest, lookback tín hiệu là 1 (chỉ xét ngày đang test)
                    res = analyze_pure_wyckoff(window, index_bt, test_ticker, 100000, 1)
                    
                    if res:
                        in_position = True
                        entry_price = current_close
                        entry_date = current_date.strftime("%d/%m/%Y")
                        trade_type = res["Tín Hiệu (Gần đây)"]
                        
                        if "Pha C" in trade_type:
                            tr_low = float(res["Khung TR"].split(" - ")[0])
                            stop_loss = tr_low * 0.95 
                        else:
                            stop_loss = float(df_bt['MA50'].iloc[i]) * 0.95

                else:
                    sell_reason, exit_price = "", 0
                    
                    if "Pha C" not in trade_type:
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
