import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Master: Auto Radar", layout="wide")
st.title("🏛️ Hệ Thống GGU: Tự Động Quét Toàn Thị Trường")
st.markdown("Cơ sở dữ liệu tích hợp ~400 mã thanh khoản cao nhất. Phân tích Bar-by-Bar (Pure Price Action).")

# DATABASE TÍCH HỢP SẴN: ~400 MÃ THANH KHOẢN TỐT NHẤT THỊ TRƯỜNG VIỆT NAM (HOSE, HNX, UPCOM)
# Bao phủ toàn bộ VN30, VNMidcap, HNX30 và các cổ phiếu có dòng tiền lớn
MARKET_TICKERS = [
    # Ngân hàng
    "VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB","NAB","BAB","KLB","BVB","SGB",
    # Chứng khoán
    "SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS","VIG","APS","HBS","SBS",
    # Thép & Vật liệu xây dựng
    "HPG","HSG","NKG","VGS","SMC","TLH","HT1","BCC","KSB","DHA","VLB","TIS","POM",
    # Bất động sản (Thương mại & Dân cư)
    "VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","KHG","SCR","HQC","DXS","QCG","NBB","ITC","SJS",
    # Khu công nghiệp
    "KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","SZB","TIP",
    # Bán lẻ, Tiêu dùng & Công nghệ
    "FPT","MWG","PNJ","FRT","DGW","PET","CMG","ELC","VGI","CTR","ITD","SAB","VNM","MSN","KDC","MCH","SBT","QNS","LSS","SLS",
    # Dầu khí & Hóa chất / Phân bón
    "GAS","PVD","PVS","BSR","PLX","OIL","PVC","PVB","DGC","DCM","DPM","CSV","GVR","BFC","LAS","DDV",
    # Cảng, Vận tải biển & Logistics
    "GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP","TCL","MVN","ILB",
    # Năng lượng, Điện & Nước
    "POW","REE","PC1","NT2","GEG","TV2","HDG","QTP","HND","BWE","TDM","VSH","CHP","SBA",
    # Thủy sản, Nông nghiệp & Thực phẩm
    "VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","MPC","ASM","BFX","HNG",
    # Xây dựng & Đầu tư công
    "VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","PC1","THD","ROS","CII",
    # Dệt may, Bảo hiểm, Y tế, Nhựa & Khác
    "TNG","VGT","GIL","MSH","STK","TCM","BVH","BMI","MIG","PVI","BIC","DHG","IMP","DBD","DCL","BMP","NTP","AAA","APH","HAP","GEX"
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
        return None # Thanh khoản thấp -> Bỏ qua ngay lập tức

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
    # BƯỚC 5: ĐỊNH VỊ PHA (POE)
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
                vung_mua_poe = f"Chờ BUEC test {round(tr_high, 2)}"
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
tab1, tab2 = st.tabs(["🎯 Auto Radar (Toàn Thị Trường)", "🧪 Backtest Chiến Dịch"])

with tab1:
    st.markdown("### 🦅 Hệ Thống Quét Tự Động Toàn Bộ Các Mã Có Dòng Tiền Lớn")
    
    # GIAO DIỆN TÙY CHỈNH THANH KHOẢN
    min_vol_input = st.number_input(
        "BỘ LỌC THANH KHOẢN: Trung bình Khối lượng 20 phiên tối thiểu (Cổ phiếu/Phiên):", 
        min_value=50000, max_value=2000000, value=200000, step=50000,
        help="Khuyến nghị > 200,000 để bám theo dấu chân Smart Money. Tăng mức này lên 500k hoặc 1 triệu để chỉ tìm siêu Bluechips."
    )
    
    if st.button("🚀 KÍCH HOẠT RADAR TỰ ĐỘNG"):
        results = []
        my_bar = st.progress(0, text="Khởi tạo kết nối dữ liệu Vĩ mô...")
        index_df = get_index_data("2y")
        
        # Thêm đuôi .VN tự động cho Yahoo Finance
        tickers_to_scan = [t + ".VN" for t in MARKET_TICKERS]
        
        if index_df is not None:
            total_tickers = len(tickers_to_scan)
            count = 0
            
            try:
                for t in tickers_to_scan:
                    df = get_data(t, "2y")
                    if df is not None:
                        res = analyze_pure_wyckoff(df, index_df, t, min_vol_input)
                        if res: 
                            results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang kiểm định Bar-by-Bar: {t}...")
                    # Delay cực nhỏ để tránh Yahoo chặn IP khi quét lượng lớn
                    time.sleep(0.02) 
            except Exception as e:
                st.warning("Đã hoàn tất quét một phần danh mục. Đang hiển thị kết quả...")
                
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Tìm thấy {len(results)} siêu cổ phiếu vượt qua màng lọc thanh khoản và cấu trúc GGU.")
                df_res = pd.DataFrame(results)[["Mã", "Mẫu Hình", "Ngày Climax", "Khung TR", "Giá HT", "Top-Down", "Giai đoạn", "POE", "SL"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning(f"Không có mã nào thỏa mãn cấu trúc GGU với mức thanh khoản > {int(min_vol_input):,} /phiên.")
        else:
            st.error("Lỗi kết nối dữ liệu VN-Index.")

with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch Giao dịch Lịch sử")
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.selectbox("Chọn mã muốn Backtest (2 năm qua):", [t + ".VN" for t in MARKET_TICKERS])
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
