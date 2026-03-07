import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="GGU Master: StockCharts SCTR & VSA", layout="wide")
st.title("🏛️ Hệ Thống GGU: SCTR Top-Down & VSA Bar-by-Bar")
st.markdown("Thuật toán SCTR chuẩn StockCharts & Dò tìm Điểm nổ VSA theo TradeGuider.")

# TỪ ĐIỂN PHÂN LOẠI NGÀNH (~400 MÃ CƠ BẢN)
DEFAULT_SECTORS = {
    "Ngân hàng": ["VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB"],
    "Chứng khoán": ["SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS"],
    "Thép & Vật liệu": ["HPG","HSG","NKG","VGS","SMC","TLH","HT1","BCC","KSB","DHA","VLB"],
    "Bất động sản": ["VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC"],
    "Khu công nghiệp": ["KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","TIP"],
    "Bán lẻ & Công nghệ": ["FPT","MWG","PNJ","FRT","DGW","PET","CMG","ELC","VGI","CTR","SAB","VNM","MSN","KDC","MCH","SBT","QNS"],
    "Dầu khí & Hóa chất": ["GAS","PVD","PVS","BSR","PLX","OIL","PVC","DGC","DCM","DPM","CSV","GVR","BFC","LAS"],
    "Cảng & Vận tải biển": ["GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP"],
    "Năng lượng & Tiện ích": ["POW","REE","PC1","NT2","GEG","TV2","HDG","QTP","HND","BWE","TDM"],
    "Nông nghiệp & Thủy sản": ["VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","ASM"],
    "Xây dựng & Đầu tư công": ["VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","CII"],
    "Dệt may & Khác": ["TNG","VGT","GIL","MSH","STK","TCM","BVH","BMI","MIG","PVI","DHG","IMP","BMP","NTP","AAA","GEX"]
}

TICKER_TO_SECTOR = {t: sector for sector, tickers in DEFAULT_SECTORS.items() for t in tickers}

@st.cache_data(ttl=3600)
def get_data(ticker, period="1y"): 
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df is None or len(df) < 200: return None
        return df
    except:
        return None

# --- BỘ TOÁN TỬ SCTR CHUẨN STOCKCHARTS ---
def calculate_rsi(series, period=14):
    """Tính RSI theo phương pháp Wilder's Smoothing chuẩn StockCharts"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Công thức trung bình hàm mũ (EMA) với alpha = 1/period chuẩn J. Welles Wilder
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ppo_hist(close_series):
    """Tính PPO Histogram chuẩn StockCharts"""
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    ppo = (ema12 - ema26) / ema26 * 100
    ppo_signal = ppo.ewm(span=9, adjust=False).mean()
    return ppo - ppo_signal

def process_ultimate_wyckoff(df, min_volume, vsa_lookback):
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    
    # 1. BỘ LỌC THANH KHOẢN (Loại bỏ nhiễu)
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None
        
    close = df['Close']
    
    # ==============================================================
    # 2. CHẤM ĐIỂM SCTR THEO CÔNG THỨC WYCKOFF ANALYTICS
    # ==============================================================
    
    # --- Long-Term (Trọng số 60%) ---
    ema200 = close.ewm(span=200, adjust=False).mean()
    score_ema200 = (((close.iloc[-1] - ema200.iloc[-1]) / ema200.iloc[-1]) * 100) * 0.30
    
    roc125 = close.pct_change(periods=125).iloc[-1] * 100 if len(close) > 125 else 0
    score_roc125 = roc125 * 0.30
    
    # --- Medium-Term (Trọng số 30%) ---
    ema50 = close.ewm(span=50, adjust=False).mean()
    score_ema50 = (((close.iloc[-1] - ema50.iloc[-1]) / ema50.iloc[-1]) * 100) * 0.15
    
    roc20 = close.pct_change(periods=20).iloc[-1] * 100 if len(close) > 20 else 0
    score_roc20 = roc20 * 0.15
    
    # --- Short-Term (Trọng số 10%) ---
    rsi14 = calculate_rsi(close, 14).iloc[-1]
    score_rsi = rsi14 * 0.05 if not np.isnan(rsi14) else 0
    
    ppo_hist = calculate_ppo_hist(close)
    last_3_hist = ppo_hist.tail(3).values
    score_ppo = 0
    if len(last_3_hist) == 3 and not np.isnan(last_3_hist).any():
        x = np.array([0, 1, 2])
        # Tính độ dốc (Slope) bằng Hồi quy tuyến tính qua 3 điểm
        slope = np.polyfit(x, last_3_hist, 1)[0]
        # Quy tắc đặc biệt của StockCharts cho PPO Slope
        if slope > 1: 
            score_ppo = 5.0
        elif slope < -1: 
            score_ppo = 0.0
        else: 
            score_ppo = 0.05 * ((slope + 1) * 50)
            
    # TỔNG ĐIỂM (RAW SCORE)
    total_score = score_ema200 + score_roc125 + score_ema50 + score_roc20 + score_rsi + score_ppo

    # ==============================================================
    # 3. NHẬN DIỆN TÍN HIỆU VSA THEO TRADEGUIDER
    # ==============================================================
    df['Spread'] = df['High'] - df['Low']
    df['Avg_Spread'] = df['Spread'].rolling(20).mean()
    df['Close_Pos'] = np.where(df['Spread'] > 0, (df['Close'] - df['Low']) / df['Spread'], 0.5)
    df['Vol_High'] = df['Volume'] > (df['Vol_MA20'] * 1.2)
    df['Vol_Less_Than_Prev_2'] = (df['Volume'] < df['Volume'].shift(1)) & (df['Volume'] < df['Volume'].shift(2))
    df['Is_Down_Bar'] = df['Close'] < df['Open']
    df['Is_Up_Bar'] = df['Close'] > df['Open']
    
    scan_window = df.tail(vsa_lookback)
    latest_signal, signal_date, poe, sl = None, "", "", ""
    
    for i in range(len(scan_window)):
        idx = scan_window.index[i]
        bar = scan_window.iloc[i]
        support_20d = df['Low'].loc[:idx].tail(21).head(20).min()
        signal = None
        
        # 1. Stopping Volume
        if bar['Is_Down_Bar'] and bar['Vol_High'] and bar['Close_Pos'] > 0.5:
            signal, poe, sl = "🔴 Stopping Vol", f"Quan sát quanh {round(bar['Low'], 2)}", f"Thủng {round(bar['Low']*0.95, 2)}"
        # 2. No Supply
        elif bar['Is_Down_Bar'] and bar['Spread'] < bar['Avg_Spread'] and bar['Vol_Less_Than_Prev_2'] and bar['Close_Pos'] >= 0.5:
            signal, poe, sl = "🟢 No Supply", f"Mua vượt {round(bar['High'], 2)}", f"Thủng {round(bar['Low']*0.98, 2)}"
        # 3. Spring
        elif bar['Low'] < support_20d and bar['Close_Pos'] >= 0.6 and bar['Vol_High']:
            signal, poe, sl = "🔥 Spring (Rũ Bỏ)", f"Mua quanh {round(bar['Close'], 2)}", f"Thủng {round(bar['Low']*0.97, 2)}"
        # 4. SOS
        elif bar['Is_Up_Bar'] and bar['Spread'] > bar['Avg_Spread'] * 1.2 and bar['Vol_High'] and bar['Close_Pos'] >= 0.7:
            signal, poe, sl = "🚀 SOS (Cầu Lớn)", f"Chờ LPS về {round(bar['Close'] - (bar['Spread']*0.3), 2)}", f"Thủng {round(bar['Low'], 2)}"

        if signal:
            latest_signal, signal_date, final_poe, final_sl = signal, idx.strftime("%d/%m/%Y"), poe, sl

    return {
        "Giá Hiện Tại": round(close.iloc[-1], 2),
        "Thanh Khoản (20đ)": f"{int(current_vol_ma20):,}",
        "Total_Score": total_score,
        "VSA_Signal": latest_signal,
        "Ngày Tín Hiệu": signal_date,
        "POE": final_poe if latest_signal else "",
        "SL": final_sl if latest_signal else ""
    }

# ==========================================
# GIAO DIỆN WEB
# ==========================================
st.markdown("### 🦅 Radar Hợp Nhất: Top-Down Sector & Điểm Nổ Smart Money")

col1, col2, col3 = st.columns(3)
with col1:
    min_vol_input = st.number_input("LỌC THANH KHOẢN TỐI THIỂU:", min_value=10000, value=150000, step=50000)
with col2:
    lookback_input = st.number_input("TÌM TÍN HIỆU VSA (Số phiên qua):", min_value=1, value=10, max_value=20)
with col3:
    uploaded_file = st.file_uploader("Nạp CSV Mã tùy chọn (Cột 1 chứa mã)", type=["csv"])

if st.button("🚀 KÍCH HOẠT HỆ THỐNG TOP-DOWN"):
    raw_results = []
    
    tickers_to_scan = []
    if uploaded_file is not None:
        try:
            df_user = pd.read_csv(uploaded_file, header=None)
            raw_tickers = df_user.iloc[:, 0].dropna().astype(str).tolist()
            tickers_to_scan = [t.strip().upper() + ".VN" if not t.endswith(".VN") else t.strip().upper() for t in raw_tickers]
        except:
            st.error("Lỗi đọc file CSV.")
    else:
        tickers_to_scan = [t + ".VN" for tickers in DEFAULT_SECTORS.values() for t in tickers]
    
    if tickers_to_scan:
        my_bar = st.progress(0, text="Đang dung hợp SCTR, Phân loại Ngành và VSA...")
        total_tickers = len(tickers_to_scan)
        
        for i, t in enumerate(tickers_to_scan):
            df = get_data(t, "1y")
            if df is not None:
                res = process_ultimate_wyckoff(df, min_vol_input, lookback_input)
                if res:
                    raw_ticker = t.replace(".VN", "")
                    res["Mã"] = raw_ticker
                    res["Ngành"] = TICKER_TO_SECTOR.get(raw_ticker, "Khác") 
                    raw_results.append(res)
            
            my_bar.progress((i + 1) / total_tickers, text=f"Đang phân tích: {t}...")
            time.sleep(0.01)
            
        my_bar.empty()
        
        if raw_results:
            df_results = pd.DataFrame(raw_results)
            
            # TÍNH TOÁN % XẾP HẠNG SCTR TỔNG THỂ
            # Tính trên chính tập hợp (Universe) các mã thỏa mãn thanh khoản
            df_results['SCTR Rank'] = df_results['Total_Score'].rank(pct=True) * 100
            df_results['SCTR Rank'] = df_results['SCTR Rank'].round(1)
            
            st.success(f"Quét thành công {len(df_results)} mã qua màng lọc thanh khoản.")
            
            # --- BƯỚC 1: BẢNG XẾP HẠNG NGÀNH ---
            st.markdown("#### 🥇 BƯỚC 1: XẾP HẠNG SỨC MẠNH NGÀNH (DÒNG TIỀN VĨ MÔ)")
            st.markdown("*Dòng tiền đang chảy vào đâu? Ưu tiên tìm cơ hội ở Top Ngành dẫn dắt.*")
            
            sector_stats = df_results.groupby('Ngành').agg(
                SCTR_Trung_Bình=('SCTR Rank', 'mean'),
                Số_Lượng_Mã=('Mã', 'count')
            ).reset_index()
            sector_stats = sector_stats.sort_values(by='SCTR_Trung_Bình', ascending=False).round(1)
            sector_stats.rename(columns={'SCTR_Trung_Bình': 'Điểm SCTR Trung Bình'}, inplace=True)
            
            st.dataframe(sector_stats, use_container_width=True)

            st.divider()

            # --- BƯỚC 2: TÍN HIỆU HÀNH ĐỘNG KẾT HỢP NGÀNH ---
            st.markdown("#### 🎯 BƯỚC 2: TÍN HIỆU HÀNH ĐỘNG (DẤU CHÂN SMART MONEY)")
            st.markdown("*Các mã vừa nổ điểm VSA. Hãy chú ý các mã có SCTR Rank cao (>70) và thuộc nhóm Ngành dẫn dắt ở Bảng 1.*")
            
            df_signals = df_results[df_results['VSA_Signal'].notnull()].copy()
            if not df_signals.empty:
                df_signals = df_signals.sort_values(by=["SCTR Rank"], ascending=False).reset_index(drop=True)
                cols_sig = ["Ngành", "Mã", "SCTR Rank", "VSA_Signal", "Ngày Tín Hiệu", "Giá Hiện Tại", "POE", "SL", "Thanh Khoản (20đ)"]
                st.dataframe(df_signals[cols_sig], use_container_width=True)
            else:
                st.info(f"Hiện tại không có mã nào phát tín hiệu VSA trong {lookback_input} ngày qua.")

            st.divider()

            # --- BƯỚC 3: XẾP HẠNG SCTR TOÀN THỊ TRƯỜNG ---
            st.markdown("#### 👑 BƯỚC 3: BẢNG XẾP HẠNG SCTR CHI TIẾT (TOP DOWN)")
            st.markdown("*Nhóm các mã mạnh nhất thị trường hiện tại. Click vào tên cột 'Ngành' để nhóm các cổ phiếu đối thủ lại với nhau.*")
            
            df_ranking = df_results.sort_values(by="SCTR Rank", ascending=False).reset_index(drop=True)
            cols_rank = ["Ngành", "Mã", "SCTR Rank", "Giá Hiện Tại", "Thanh Khoản (20đ)"]
            st.dataframe(df_ranking[cols_rank], use_container_width=True)
            
        else:
            st.warning("Không có cổ phiếu nào vượt qua màng lọc thanh khoản.")
