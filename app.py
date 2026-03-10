import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import datetime

st.set_page_config(page_title="GGU Master V16: Smart Engine", layout="wide")
st.title("🏛️ Hệ Thống GGU: Tiền Thương Mại (V16)")
st.markdown("Tích hợp AI đánh giá Cấu trúc Đủ Nhịp, Động lượng SCTR Ngành và La bàn Chu kỳ.")

# TỪ ĐIỂN NGÀNH CHUẨN (VN220)
DEFAULT_SECTORS = {
    "Ngân hàng": ["VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB","NAB","BAB","KLB"],
    "Chứng khoán": ["SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS","VIG","APG","VFS","DSC"],
    "Bất động sản": ["VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC","DXS","KHG","HDG","SJS","NBB","ITC","QCG","VPI","TDC"],
    "BĐS Khu công nghiệp": ["KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","TIP","SNZ","SZL","ITA","LHG"],
    "Công nghệ & Viễn thông": ["FPT","VGI","CTR","CMG","ELC","FOX","TTN","VNZ","ITD","SGT"],
    "Bán lẻ": ["MWG","PNJ","FRT","DGW","PET","HAX"],
    "Thép & Sản phẩm thép": ["HPG","HSG","NKG","VGS","SMC","TLH"],
    "Vật liệu xây dựng": ["HT1","BCC","KSB","DHA","VLB","VCS","PLC","PTB","BMP","NTP","AAA"],
    "Dầu khí": ["GAS","PVD","PVS","BSR","PLX","OIL","PVC","PSH","PVB"],
    "Hóa chất & Phân bón": ["DGC","DCM","DPM","CSV","BFC","LAS","DDV","VTZ","PAT"],
    "Thực phẩm & Đồ uống": ["SAB","VNM","MSN","KDC","MCH","SBT","QNS"],
    "Thủy sản & Nông nghiệp": ["VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","ASM","CMX","MPC","HNG"],
    "Vận tải & Logistics": ["GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP","MVN","DXP","TCL","PDN","VTP"],
    "Điện, Thiết bị điện & Đa ngành": ["POW","REE","PC1","NT2","GEG","TV2","QTP","HND","BWE","TDM","GEX"],
    "Xây dựng & Đầu tư công": ["VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","CII","L14","EVG","VEC","TCD","CTI","HTN"],
    "Dệt may": ["TNG","VGT","GIL","MSH","STK","TCM"],
    "Cao su tự nhiên": ["GVR","DRC","DRI","DPR","TRC","CSM"],
    "Bảo hiểm": ["BVH","BMI","MIG","PVI","VNR"],
    "Y tế & Dược phẩm": ["DHG","IMP","DVN","TRA","DBD"]
}
TICKER_TO_SECTOR = {t: sector for sector, tickers in DEFAULT_SECTORS.items() for t in tickers}

# --- THUẬT TOÁN TÍNH SCTR GGU ---
def calculate_rsi(series, period=21):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ppo_hist(close_series):
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    ppo = (ema12 - ema26) / ema26 * 100
    ppo_signal = ppo.ewm(span=9, adjust=False).mean()
    return ppo - ppo_signal

def get_sctr_score(df):
    close = df['Close']
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    score_ema200 = (((close.iloc[-1] - ema200) / ema200) * 100) * 0.30
    roc252 = close.pct_change(periods=252).iloc[-1] * 100 if len(close) > 252 else 0
    score_roc252 = roc252 * 0.30
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    score_ema50 = (((close.iloc[-1] - ema50) / ema50) * 100) * 0.15
    roc63 = close.pct_change(periods=63).iloc[-1] * 100 if len(close) > 63 else 0
    score_roc63 = roc63 * 0.15
    rsi21 = calculate_rsi(close, 21).iloc[-1]
    score_rsi = rsi21 * 0.05 if not np.isnan(rsi21) else 0
    
    ppo_hist = calculate_ppo_hist(close)
    last_3_hist = ppo_hist.tail(3).values
    score_ppo = 0
    if len(last_3_hist) == 3 and not np.isnan(last_3_hist).any():
        slope = np.polyfit([0, 1, 2], last_3_hist, 1)[0]
        if slope > 1: score_ppo = 5.0
        elif slope < -1: score_ppo = 0.0
        else: score_ppo = 0.05 * ((slope + 1) * 50)
    
    return score_ema200 + score_roc252 + score_ema50 + score_roc63 + score_rsi + score_ppo

def analyze_ticker_data(ticker_df, min_volume, vsa_lookback, spring_lookback, max_penetration):
    if ticker_df is None or len(ticker_df) < 270: # Cần >=270 nến để tính quá khứ
        return None
    
    df = ticker_df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None
    
    # Tính SCTR Hiện tại và 10 Phiên trước
    score_current = get_sctr_score(df)
    score_past = get_sctr_score(df.iloc[:-10])
    
    # VSA & SPRING ANATOMY
    df['Spread'] = df['High'] - df['Low']
    df['Avg_Spread'] = df['Spread'].rolling(20).mean()
    df['Close_Pos'] = np.where(df['Spread'] > 0, (df['Close'] - df['Low']) / df['Spread'], 0.5)
    df['Vol_High'] = df['Volume'] > (df['Vol_MA20'] * 1.2)
    df['Vol_Less_Than_Prev_2'] = (df['Volume'] < df['Volume'].shift(1)) & (df['Volume'] < df['Volume'].shift(2))
    df['Is_Down_Bar'] = df['Close'] < df['Open']
    df['Is_Up_Bar'] = df['Close'] > df['Open']
    
    # TÌM TÍN HIỆU CAO TRÀO BÁN TRONG 40 PHIÊN QUÁ KHỨ (Ghi nhớ thị trường)
    past_40_days = df.tail(40)
    has_stopping_volume_past = False
    for i in range(len(past_40_days) - vsa_lookback):
        bar = past_40_days.iloc[i]
        if bar['Is_Down_Bar'] and bar['Vol_High'] and bar['Close_Pos'] > 0.4:
            has_stopping_volume_past = True
            break

    scan_window = df.tail(vsa_lookback)
    latest_signal, signal_date, poe, sl, struct_eval = None, "", "", "", ""
    
    for i in range(len(scan_window)):
        idx = scan_window.index[i]
        bar = scan_window.iloc[i]
        current_loc = df.index.get_loc(idx)
        
        support_low = df['Low'].iloc[max(0, current_loc - spring_lookback) : current_loc].min() if current_loc > 0 else bar['Low']
        signal = None
        
        if bar['Is_Down_Bar'] and bar['Vol_High'] and bar['Close_Pos'] > 0.4:
            signal, poe, sl = "🔴 Stopping Vol", f"Quan sát {round(bar['Low'], 2)}", f"Thủng {round(bar['Low']*0.95, 2)}"
        elif bar['Is_Down_Bar'] and bar['Spread'] < bar['Avg_Spread'] and bar['Vol_Less_Than_Prev_2'] and bar['Close_Pos'] >= 0.4:
            signal, poe, sl = "🟢 No Supply", f"Mua vượt {round(bar['High'], 2)}", f"Thủng {round(bar['Low']*0.98, 2)}"
        elif bar['Low'] < support_low:
            penetration_pct = (support_low - bar['Low']) / support_low * 100
            if (penetration_pct <= max_penetration and bar['Close'] >= support_low and bar['Close_Pos'] >= 0.1 and bar['Volume'] > df['Vol_MA20'].iloc[current_loc]):
                signal, poe, sl = "🔥 Spring", f"Mua {round(bar['Close'], 2)}", f"Thủng {round(bar['Low'], 2)}"
        elif bar['Is_Up_Bar'] and bar['Spread'] > bar['Avg_Spread'] * 1.2 and bar['Vol_High'] and bar['Close_Pos'] >= 0.7:
            signal, poe, sl = "🚀 SOS", f"Chờ LPS {round(bar['Close'] - (bar['Spread']*0.3), 2)}", f"Thủng {round(bar['Low'], 2)}"

        if signal:
            latest_signal, signal_date, poe, sl = signal, idx.strftime("%d/%m/%Y"), poe, sl
            
            # MODULE 2: ĐÁNH GIÁ CẤU TRÚC ĐỦ NHỊP
            if signal in ["🟢 No Supply", "🔥 Spring"]:
                if has_stopping_volume_past:
                    struct_eval = "🌟 Mua Vàng (Đã rũ SC)"
                else:
                    struct_eval = "⏳ Sớm (Chưa có SC)"
            elif signal == "🔴 Stopping Vol":
                struct_eval = "👀 Watchlist (Đợi Test đáy)"
            elif signal == "🚀 SOS":
                struct_eval = "📈 Đánh Đẩy giá (Markup)"

    return {
        "Giá Hiện Tại": round(df['Close'].iloc[-1], 2),
        "Thanh Khoản (20đ)": f"{int(current_vol_ma20):,}",
        "Score_Current": score_current,
        "Score_Past": score_past,
        "VSA_Signal": latest_signal,
        "Đánh giá Cấu trúc": struct_eval,
        "Ngày Tín Hiệu": signal_date,
        "POE": poe,
        "SL": sl
    }

# ==========================================
# MODULE 1: LA BÀN CHU KỲ (SEASONALITY COMPASS)
# ==========================================
current_month = datetime.datetime.now().month
if current_month in [11, 12, 1]:
    st.info("🌱 **GIAI ĐOẠN HIỆN TẠI: GOM HÀNG CHỜ KẾT QUẢ NĂM MỚI.** \n*Chiến lược:* Theo dõi dòng tiền gom (Stopping Vol). Tích lũy vị thế.")
elif current_month in [2, 3, 4]:
    st.success("🔥 **GIAI ĐOẠN HIỆN TẠI: SÓNG KỲ VỌNG (BCTC & ĐHCĐ).** \n*Chiến lược:* TẤN CÔNG. Mua mạnh khi có Spring/SOS tại nhóm SCTR > 75.")
elif current_month == 5:
    st.error("⚠️ **GIAI ĐOẠN HIỆN TẠI: VÙNG TẠO ĐỈNH (Sell in May).** \n*Chiến lược:* PHÒNG THỦ. Hạ tỷ trọng, cẩn thận Bulltrap. Chú ý SCTR Ngành gãy đổ.")
elif current_month in [6, 7]:
    st.info("📉 **GIAI ĐOẠN HIỆN TẠI: VÙNG TRŨNG THÔNG TIN.** \n*Chiến lược:* Kiên nhẫn chờ thị trường rơi đủ sóng (Đợi Phase C). Không vội bắt dao rơi.")
else:
    st.success("🌊 **GIAI ĐOẠN HIỆN TẠI: SÓNG KẾT QUẢ KINH DOANH Q3.** \n*Chiến lược:* Lọc các mã SCTR dẫn đầu, tìm điểm nổ No Supply/SOS.")

st.divider()

# ==========================================
# GIAO DIỆN WEB CÓ TÙY CHỈNH THAM SỐ
# ==========================================
col1, col2, col3 = st.columns(3)
with col1:
    min_vol_input = st.number_input("LỌC THANH KHOẢN TỐI THIỂU:", min_value=10000, value=150000, step=50000)
with col2:
    lookback_input = st.number_input("TÌM TÍN HIỆU VSA (Số phiên qua):", min_value=1, value=5, max_value=20)
with col3:
    uploaded_file = st.file_uploader("Nạp CSV Mã tùy chọn", type=["csv"])

with st.expander("⚙️ Tùy chỉnh Giải phẫu nến Spring (Wyckoff Anatomy)"):
    scol1, scol2 = st.columns(2)
    with scol1:
        spring_lookback_input = st.number_input("Chu kỳ dò Hỗ Trợ (Lookback):", value=15)
    with scol2:
        max_penetration_input = st.number_input("Độ rũ tối đa - Proximity (%):", value=8.0)

if st.button("🚀 KÍCH HOẠT RADAR SIÊU TỐC"):
    tickers_to_scan = []
    if uploaded_file is not None:
        try:
            df_user = pd.read_csv(uploaded_file, header=None)
            raw_tickers = df_user.iloc[:, 0].dropna().astype(str).tolist()
            tickers_to_scan = [t.strip().upper() + ".VN" if not t.endswith(".VN") else t.strip().upper() for t in raw_tickers]
        except: st.error("Lỗi file CSV.")
    else:
        tickers_to_scan = [t + ".VN" for tickers in DEFAULT_SECTORS.values() for t in tickers]

    if tickers_to_scan:
        start_time = time.time()
        with st.spinner(f"Đang tải siêu tốc kho dữ liệu 2 năm cho {len(tickers_to_scan)} mã..."):
            full_data = yf.download(tickers_to_scan, period="2y", group_by='ticker', threads=True, progress=False)
        
        raw_results = []
        my_bar = st.progress(0, text="AI đang phân tích Dấu chân Smart Money...")
        
        for i, t in enumerate(tickers_to_scan):
            try:
                ticker_df = full_data[t].dropna(how='all')
                if not ticker_df.empty:
                    res = analyze_ticker_data(ticker_df, min_vol_input, lookback_input, spring_lookback_input, max_penetration_input)
                    if res:
                        res["Mã"], res["Ngành"] = t.replace(".VN", ""), TICKER_TO_SECTOR.get(t.replace(".VN", ""), "Khác")
                        raw_results.append(res)
            except: continue
            my_bar.progress((i + 1) / len(tickers_to_scan))
            
        my_bar.empty()
        
        if raw_results:
            df_results = pd.DataFrame(raw_results)
            
            # XẾP HẠNG SCTR HIỆN TẠI VÀ QUÁ KHỨ (10 PHIÊN TRƯỚC)
            df_results['SCTR_Rank_Current'] = df_results['Score_Current'].rank(pct=True) * 100
            df_results['SCTR_Rank_Past'] = df_results['Score_Past'].rank(pct=True) * 100
            df_results['SCTR_Rank_Current'] = df_results['SCTR_Rank_Current'].round(1)
            
            # --- MODULE 3: BẢNG XẾP HẠNG & ĐỘNG LƯỢNG NGÀNH ---
            st.markdown("#### 🥇 BƯỚC 1: XẾP HẠNG VÀ ĐỘNG LƯỢNG NGÀNH (DÒNG TIỀN VĨ MÔ)")
            st.markdown("*So sánh sức mạnh ngành hiện tại so với 2 tuần trước để xem dòng tiền đang luân chuyển đi đâu.*")
            
            sector_stats = df_results.groupby('Ngành').agg(
                SCTR_Nay=('SCTR_Rank_Current', 'mean'),
                SCTR_Cu=('SCTR_Rank_Past', 'mean'),
                So_Ma=('Mã', 'count')
            ).reset_index()
            
            sector_stats['SCTR_Nay'] = sector_stats['SCTR_Nay'].round(1)
            sector_stats['SCTR_Cu'] = sector_stats['SCTR_Cu'].round(1)
            
            # Tạo cột Xu Hướng
            def get_trend(row):
                diff = row['SCTR_Nay'] - row['SCTR_Cu']
                if diff > 3: return f"🚀 Tăng (+{diff:.1f})"
                elif diff < -3: return f"📉 Giảm ({diff:.1f})"
                else: return "➖ Đi ngang"
                
            sector_stats['Xu Hướng (vs 2 tuần trước)'] = sector_stats.apply(get_trend, axis=1)
            sector_stats = sector_stats.sort_values(by='SCTR_Nay', ascending=False).drop(columns=['SCTR_Cu'])
            sector_stats.rename(columns={'SCTR_Nay': 'Điểm SCTR', 'So_Ma': 'Số lượng mã'}, inplace=True)
            
            st.dataframe(sector_stats, use_container_width=True)

            st.divider()

            # --- BƯỚC 2: TÍN HIỆU HÀNH ĐỘNG KẾT HỢP NGÀNH ---
            st.markdown("#### 🎯 BƯỚC 2: TÍN HIỆU VSA & ĐÁNH GIÁ CẤU TRÚC")
            st.markdown("*Bot tự động nhìn lại 40 phiên trước để đánh giá độ an toàn của điểm mua (Đã rơi đủ sóng hay chưa).*")
            
            df_signals = df_results[df_results['VSA_Signal'].notnull()].copy()
            if not df_signals.empty:
                df_signals = df_signals.sort_values(by=["SCTR_Rank_Current"], ascending=False).reset_index(drop=True)
                df_signals.rename(columns={'SCTR_Rank_Current': 'SCTR'}, inplace=True)
                cols_sig = ["Ngành", "Mã", "SCTR", "VSA_Signal", "Đánh giá Cấu trúc", "Ngày Tín Hiệu", "Giá Hiện Tại", "POE", "SL", "Thanh Khoản (20đ)"]
                
                # Highlight màu cho Bảng Tín hiệu
                def highlight_eval(val):
                    if "Vàng" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
                    elif "Sớm" in str(val): return 'background-color: #fff3cd; color: #856404'
                    elif "Markup" in str(val): return 'background-color: #cce5ff; color: #004085'
                    return ''
                
                st.dataframe(df_signals[cols_sig].style.map(highlight_eval, subset=['Đánh giá Cấu trúc']), use_container_width=True)
            else:
                st.info(f"Hiện tại không có mã nào phát tín hiệu VSA trong {lookback_input} ngày qua.")

            st.divider()

            # --- BƯỚC 3: XẾP HẠNG SCTR TOÀN THỊ TRƯỜNG ---
            st.markdown("#### 👑 BƯỚC 3: BẢNG XẾP HẠNG SCTR CHI TIẾT (VN220)")
            df_ranking = df_results.sort_values(by="SCTR_Rank_Current", ascending=False).reset_index(drop=True)
            df_ranking.rename(columns={'SCTR_Rank_Current': 'SCTR'}, inplace=True)
            cols_rank = ["Ngành", "Mã", "SCTR", "Giá Hiện Tại", "Thanh Khoản (20đ)"]
            st.dataframe(df_ranking[cols_rank], use_container_width=True)
            
        else:
            st.warning("Không có cổ phiếu nào vượt qua màng lọc thanh khoản.")
