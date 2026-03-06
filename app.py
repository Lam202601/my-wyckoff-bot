import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Master: Pure Price Action", layout="wide")
st.title("🏛️ Hệ Thống GGU: Bộ Lọc Thanh Khoản & Động Lực Sóng")
st.markdown("Loại bỏ cổ phiếu rác. Xác định Cấu trúc hoàn toàn bằng Động lực Sóng (Swing Dynamics).")

# DANH SÁCH 150+ MÃ CỔ PHIẾU THANH KHOẢN TỐT NHẤT THỊ TRƯỜNG VIỆT NAM
DEFAULT_SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN", "STB.VN", "VPB.VN", "ACB.VN", "HDB.VN", "VIB.VN", "TPB.VN", "SHB.VN", "MSB.VN", "LPB.VN", "EIB.VN", "OCB.VN", "SSB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN", "MBS.VN", "FTS.VN", "BSI.VN", "CTS.VN", "AGR.VN", "VIX.VN", "ORS.VN", "VDS.VN", "BVS.VN"],
    "Thép & Vật liệu": ["HPG.VN", "HSG.VN", "NKG.VN", "VGS.VN", "SMC.VN", "TLH.VN", "HT1.VN", "BCC.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "VRE.VN", "DXG.VN", "DIG.VN", "PDR.VN", "NLG.VN", "NVL.VN", "CEO.VN", "HDC.VN", "KDH.VN", "NTL.VN", "TCH.VN", "IJC.VN"],
    "Khu công nghiệp": ["KBC.VN", "IDC.VN", "SZC.VN", "VGC.VN", "PHR.VN", "BCM.VN", "NTC.VN", "SIP.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN", "PET.VN", "CMG.VN"],
    "Dầu khí & Hóa chất": ["GAS.VN", "PVD.VN", "PVS.VN", "BSR.VN", "PLX.VN", "DGC.VN", "DCM.VN", "DPM.VN", "CSV.VN", "GVR.VN"],
    "Cảng & Vận tải biển": ["GMD.VN", "HAH.VN", "VSC.VN", "PVT.VN", "VOS.VN"],
    "Năng lượng & Điện": ["POW.VN", "REE.VN", "PC1.VN", "NT2.VN", "GEG.VN", "TV2.VN", "HDG.VN"],
    "Thủy sản & Nông nghiệp": ["VHC.VN", "ANV.VN", "IDI.VN", "FMC.VN", "DBC.VN", "HAG.VN", "BAF.VN", "PAN.VN", "TAR.VN"],
    "Xây dựng & ĐTC": ["VCG.VN", "HHV.VN", "LCG.VN", "C4G.VN", "HBC.VN", "CTD.VN", "FCN.VN", "HUT.VN"],
    "Dệt may & Khác": ["TNG.VN", "VGT.VN", "GIL.VN", "MSH.VN", "VNM.VN", "SAB.VN", "MSN.VN"]
}

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

def analyze_pure_wyckoff(df, index_df, ticker, min_volume):
    df = df.copy()
    index_df = index_df.copy()
    
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 253: return None 

    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    # =======================================================
    # BƯỚC 0: MÀNG LỌC THANH KHOẢN (Loại bỏ Penny/Cổ phiếu rác)
    # =======================================================
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None # Thanh khoản quá thấp -> Bỏ qua ngay, không tốn tài nguyên phân tích

    # =======================================================
    # BƯỚC 1: XÁC ĐỊNH SỰ KIỆN CLIMAX (BẰNG ĐỘNG LỰC SÓNG)
    # =======================================================
    lookback = df.tail(200)
    base_window = lookback.iloc[:-40] 
    if base_window.empty: return None
    
    climax_date = base_window['Volume'].idxmax()
    c_close = float(df.loc[climax_date]['Close'])
    c_high = float(df.loc[climax_date]['High'])
    c_low = float(df.loc[climax_date]['Low'])
    c_vol = float(df.loc[climax_date]['Volume'])

    pre_climax = df.loc[:climax_date].tail(40)
    if len(pre_climax) < 10: return None
    
    highest_pre = float(pre_climax['High'].max())
    lowest_pre = float(pre_climax['Low'].min())

    # LOGIC PURE PRICE ACTION:
    is_sc = c_low <= lowest_pre * 1.02 
    is_bc = c_high >= highest_pre * 0.98 

    if not (is_sc or is_bc): return None

    tr_high = 0
    tr_low = 0
    c_type = ""

    # =======================================================
    # BƯỚC 2: CHANGE OF BEHAVIOR (CHoB) VÀ CHANGE OF CHARACTER (CHoC)
    # =======================================================
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
        
        if st_vol >= c_vol: return None 
        
        tr_low = c_low
        tr_high = ar_high

    elif is_bc:
        c_type = "Tái Tích Luỹ (BC)"
        ar_date = after_climax.head(30)['Low'].idxmin()
        ar_low = float(after_climax.loc[ar_date]['Low'])
        
        if (c_high - ar_low) / c_high < 0.05: return None
        
        after_ar = df.loc[ar_date:].head(25)
        if after_ar.empty: return None
        st_date = after_ar['High'].idxmax()
        st_vol = float(df.loc[st_date]['Volume'])
        
        if st_vol >= c_vol: return None
        
        tr_high = c_high
        tr_low = ar_low

    if tr_low == 0 or tr_low >= tr_high or (tr_high - tr_low) / tr_low < 0.05: return None

    # =======================================================
    # BƯỚC 3: VSA - EFFORT VS RESULT
    # =======================================================
    since_climax = df.loc[climax_date:]
    up_days = since_climax[since_climax['Close'] > since_climax['Open']]
    down_days = since_climax[since_climax['Close'] < since_climax['Open']]
    
    avg_up_vol = up_days['Volume'].mean() if not up_days.empty else 0
    avg_down_vol = down_days['Volume'].mean() if not down_days.empty else 0
    
    if avg_down_vol > avg_up_vol: return None 

    # =======================================================
    # BƯỚC 4: XÁC NHẬN TOP-DOWN LEADER
    # =======================================================
    stock_roc63 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-63]) / combined['Close_s'].iloc[-63] * 100
    idx_roc63 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-63]) / combined['Close_i'].iloc[-63] * 100
    
    rs_line = combined['Close_s'] / combined['Close_i']
    is_rs_uptrend = rs_line.iloc[-1] > rs_line.rolling(50).mean().iloc[-1]
    is_leader = (stock_roc63 > idx_roc63) and is_rs_uptrend

    # =======================================================
    # BƯỚC 5: ĐỊNH VỊ PHA (POE) THEO HÀNH ĐỘNG GIÁ
    # =======================================================
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    bottom_zone = tr_low + ((tr_high - tr_low) * 0.3)
    middle_zone = tr_low + ((tr_high - tr_low) * 0.6)
    
    phase = None
    vung_mua_poe = ""
    cat_lo = ""
    
    if current_close <= tr_low * 1.05 and current_close >= tr_low * 0.95:
        if current_close > current_open and current_vol < current_vol_ma20 * 0.8:
            phase = "Pha C (Spring/Test)"
            vung_mua_poe = f"Mua rũ bỏ tại {round(current_close, 2)}"
            cat_lo = f"Thủng {round(current_close * 0.95, 2)}"
            
    elif current_close > middle_zone and current_close < tr_high * 0.98:
        if current_vol > current_vol_ma20 * 1.2 and current_close > current_open:
            if is_leader:
                phase = "Pha D (SOS - Điểm Nổ)"
                vung_mua_poe = f"Chờ LPS về {round(middle_zone, 2)}"
                cat_lo = f"Thủng {round(bottom_zone, 2)}"
            
    elif current_close > tr_high:
        if current_vol > current_vol_ma20 * 1.5:
            if is_leader:
                phase = "Pha E (Breakout)"
                vung_mua_poe = f"Chờ BUEC test đỉnh {round(tr_high, 2)}"
                cat_lo = f"Thủng {round(tr_high * 0.96, 2)}"

    elif current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < current_vol_ma20 * 0.75:
            phase = "Pha A/B (Kiểm định biên)"
            vung_mua_poe = f"Swing hỗ trợ {round(tr_low, 2)}"
            cat_lo = f"Thủng {round(tr_low * 0.96, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Mẫu Hình": c_type,
            "Ngày Climax": climax_date.strftime("%d/%m/%Y"),
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
tab1, tab2 = st.tabs(["🎯 Radar Diện Rộng (150+ Mã Cơ Bản)", "🧪 Backtest Chiến Dịch"])

with tab1:
    st.markdown("### 🦅 Quét Tín Hiệu: Lọc Thanh Khoản & Động Lực Sóng Price Action")
    
    # GIAO DIỆN TÙY CHỈNH THANH KHOẢN
    min_vol_input = st.number_input(
        "BỘ LỌC THANH KHOẢN: Trung bình Khối lượng 20 phiên tối thiểu (Cổ phiếu/Phiên):", 
        min_value=10000, max_value=2000000, value=200000, step=50000,
        help="Khuyến nghị > 200,000 để bám theo dấu chân Smart Money, tránh mã bo cung thao túng."
    )
    
    st.markdown("Tải lên File CSV nếu bạn có danh sách mã riêng (Nếu không, hệ thống quét 150+ mã cơ bản).")
    uploaded_file = st.file_uploader("Tải file danh_sach_ma.csv", type=["csv"])
    
    if st.button("🚀 KÍCH HOẠT RADAR"):
        results = []
        my_bar = st.progress(0, text="Khởi tạo Radar diện rộng...")
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
            for tickers in DEFAULT_SECTORS.values():
                tickers_to_scan.extend(tickers)
        
        if index_df is not None and tickers_to_scan:
            total_tickers = len(tickers_to_scan)
            count = 0
            
            try:
                for t in tickers_to_scan:
                    df = get_data(t, "2y")
                    if df is not None:
                        # Truyền tham số min_vol_input vào hàm phân tích
                        res = analyze_pure_wyckoff(df, index_df, t, min_vol_input)
                        if res: 
                            results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang phân tích Bar-by-Bar: {t}...")
                    time.sleep(0.05 if total_tickers < 100 else 0.1) 
            except Exception as e:
                st.warning("Yahoo Finance có thể đã giới hạn lượt truy cập. Đang xuất kết quả đã quét được...")
                
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Tìm thấy {len(results)} siêu cổ phiếu vượt qua màng lọc thanh khoản và cấu trúc Wyckoff.")
                df_res = pd.DataFrame(results)[["Mã", "Mẫu Hình", "Ngày Climax", "Khung TR", "Giá HT", "Top-Down", "Giai đoạn", "POE", "SL"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning(f"Không có mã nào thỏa mãn cấu trúc GGU với thanh khoản > {int(min_vol_input):,} cổ phiếu/phiên.")
        else:
            if index_df is None: st.error("Lỗi kết nối dữ liệu VN-Index.")

with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch Giao dịch Lịch sử")
    col1, col2 = st.columns([1, 2])
    with col1:
        all_default_tickers = [t for tickers in DEFAULT_SECTORS.values() for t in tickers]
        test_ticker = st.selectbox("Chọn mã muốn Backtest (2 năm qua):", all_default_tickers)
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
            entry_price = 0
            stop_loss = 0
            trade_type = ""
            entry_date = ""

            for i in range(200, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-200 : i+1]
                    # Backtest mặc định dùng thanh khoản 100k để quét lịch sử cho mượt
                    res = analyze_pure_wyckoff(window, index_bt, test_ticker, 100000)
                    
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
                    sell_reason = ""
                    exit_price = 0
                    
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
                win_trades = df_trades[df_trades["Lợi nhuận (%)"] > 0]
                win_rate = (len(win_trades) / len(df_trades)) * 100
                total_profit = df_trades["Lợi nhuận (%)"].sum()
                
                st.markdown("#### 📊 Báo Cáo Chiến Dịch Giao Dịch")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng số lệnh", f"{len(df_trades)} lệnh")
                m2.metric("Tỷ lệ Thắng (Win Rate)", f"{round(win_rate, 1)}%")
                m3.metric("Tổng LN Lũy kế", f"{round(total_profit, 2)}%")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Chưa có tín hiệu mua nào được kích hoạt an toàn cho {test_ticker} trong chu kỳ này.")
