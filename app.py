import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Master: The Unified GGU", layout="wide")
st.title("🏛️ Hệ Thống GGU: Bản Tổng Hợp Toàn Diện")
st.markdown("Tích hợp trọn vẹn: Đa Cấu Trúc (SC/BC), Sóng CHoB/CHoC, VSA Cung Cầu & Top-Down Leadership")

SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN", "STB.VN", "VPB.VN", "ACB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN", "MBS.VN", "FTS.VN"],
    "Thép": ["HPG.VN", "HSG.VN", "NKG.VN", "VGS.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "DXG.VN", "DIG.VN", "KBC.VN", "PDR.VN", "NLG.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN"]
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

def analyze_unified_wyckoff(df, index_df, ticker):
    df = df.copy()
    index_df = index_df.copy()
    
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 253: return None 
    
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()

    # =======================================================
    # BƯỚC 1: ĐO LƯỜNG TOP-DOWN VÀ ĐỘNG LƯỢNG (Giữ lại tính toán, chưa lọc)
    # =======================================================
    stock_roc63 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-63]) / combined['Close_s'].iloc[-63] * 100
    idx_roc63 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-63]) / combined['Close_i'].iloc[-63] * 100
    
    rs_line = combined['Close_s'] / combined['Close_i']
    is_rs_uptrend = rs_line.iloc[-1] > rs_line.rolling(50).mean().iloc[-1]
    
    # Leader = RS đang Uptrend và Động lượng 1 Quý thắng VNI
    is_leader = (stock_roc63 > idx_roc63) and is_rs_uptrend

    # =======================================================
    # BƯỚC 2: ĐỊNH VỊ CLIMAX (Tích Luỹ & Tái Tích Luỹ)
    # =======================================================
    lookback = df.tail(200)
    # TÌM CLIMAX TRONG QUÁ KHỨ: Bỏ qua 40 phiên gần nhất để TR có thời gian hình thành (Fix lỗi Backtest mù)
    base_window = lookback.iloc[:-40] 
    if base_window.empty: return None
    
    climax_date = base_window['Volume'].idxmax()
    c_close = float(df.loc[climax_date]['Close'])
    c_high = float(df.loc[climax_date]['High'])
    c_low = float(df.loc[climax_date]['Low'])
    c_vol = float(df.loc[climax_date]['Volume'])
    c_ma50 = float(df.loc[climax_date]['MA50'])

    is_sc = c_close < c_ma50 # Bị đạp thủng MA50 nổ Vol -> SC
    is_bc = c_close >= c_ma50 # Rướn vượt MA50 nổ Vol -> BC

    tr_high = 0
    tr_low = 0
    c_type = ""

    # =======================================================
    # BƯỚC 3: ĐỘNG LỰC HỌC SÓNG (CHoB / CHoC)
    # =======================================================
    after_climax = df.loc[climax_date:]
    
    if is_sc:
        c_type = "Tích Luỹ Đáy (SC)"
        # AR: Sóng hồi đầu tiên
        ar_date = after_climax.head(30)['High'].idxmax()
        ar_high = float(after_climax.loc[ar_date]['High'])
        
        # ST: Sóng test lại SC
        after_ar = df.loc[ar_date:].head(25)
        if after_ar.empty: return None
        st_date = after_ar['Low'].idxmin()
        st_vol = float(df.loc[st_date]['Volume'])
        
        # CHoC: Cú test ST phải có Volume thấp hơn SC (Sự cạn cung)
        if st_vol >= c_vol: return None 
        
        tr_low = c_low
        tr_high = ar_high

    elif is_bc:
        c_type = "Tái Tích Luỹ (BC)"
        # AR: Sóng điều chỉnh tự động
        ar_date = after_climax.head(30)['Low'].idxmin()
        ar_low = float(after_climax.loc[ar_date]['Low'])
        
        # ST: Sóng test lại đỉnh BC
        after_ar = df.loc[ar_date:].head(25)
        if after_ar.empty: return None
        st_date = after_ar['High'].idxmax()
        st_vol = float(df.loc[st_date]['Volume'])
        
        # CHoC: Kéo lên đỉnh test nhưng Vol thấp hơn BC (Sự cạn cầu hưng phấn)
        if st_vol >= c_vol: return None
        
        tr_high = c_high
        tr_low = ar_low

    if tr_low == 0 or tr_low >= tr_high or (tr_high - tr_low) / tr_low < 0.05: return None

    # =======================================================
    # BƯỚC 4: VSA - LỌC BẪY PHÂN PHỐI
    # =======================================================
    since_climax = df.loc[climax_date:]
    up_days = since_climax[since_climax['Close'] > since_climax['Open']]
    down_days = since_climax[since_climax['Close'] < since_climax['Open']]
    
    avg_up_vol = up_days['Volume'].mean() if not up_days.empty else 0
    avg_down_vol = down_days['Volume'].mean() if not down_days.empty else 0
    
    if avg_down_vol > avg_up_vol: return None # Xả > Gom -> Loại bỏ

    # =======================================================
    # BƯỚC 5: ĐỊNH VỊ PHA (POE) BẰNG BỐI CẢNH
    # =======================================================
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    bottom_zone = tr_low + ((tr_high - tr_low) * 0.3)
    
    phase = None
    vung_mua_poe = ""
    cat_lo = ""
    
    # Pha C (Rũ bỏ cạn cung - Spring/Test)
    if current_close <= tr_low * 1.05 and current_close >= tr_low * 0.95:
        if current_close > current_open and current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.8:
            phase = "Pha C (Spring/Test)"
            vung_mua_poe = f"Mua rũ bỏ tại {round(current_close, 2)}"
            cat_lo = f"Thủng {round(current_close * 0.95, 2)}"
            
    # Pha D (Dòng tiền kích hoạt - Cần Top-Down Leader để mua an toàn)
    elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high * 0.98:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2 and current_close > current_open:
            if is_leader:
                phase = "Pha D (SOS - Điểm Nổ)"
                vung_mua_poe = f"Chờ LPS về {round(float(df['MA50'].iloc[-1]), 2)}"
                cat_lo = f"Thủng MA50 ({round(float(df['MA50'].iloc[-1]) * 0.97, 2)})"
            
    # Pha E (Breakout - Bắt buộc phải là Leader)
    elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
            if is_leader:
                phase = "Pha E (Breakout)"
                vung_mua_poe = f"Chờ BUEC test {round(tr_high, 2)}"
                cat_lo = f"Thủng {round(tr_high * 0.96, 2)}"

    # Pha A/B (Đi ngang kiểm định)
    elif current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.75:
            phase = "Pha A/B (Kiểm định biên)"
            vung_mua_poe = f"Swing hỗ trợ {round(tr_low, 2)}"
            cat_lo = f"Thủng {round(tr_low * 0.96, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Mẫu Hình": c_type,
            "Ngày Bắt Đầu TR": climax_date.strftime("%d/%m/%Y"),
            "CHoB/CHoC": "✅ Sóng đạt chuẩn",
            "Top-Down": "⭐ Leader" if is_leader else "Đang gom",
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
tab1, tab2 = st.tabs(["🎯 Lọc Siêu Tổng Hợp (GGU Master)", "🧪 Backtest Chiến Dịch"])

# --- TAB 1: RADAR SĂN MÃ ---
with tab1:
    st.markdown("### 🦅 Quét Tín Hiệu: SC/BC, Động Lực Sóng & Top-Down")
    if st.button("🚀 KÍCH HOẠT RADAR"):
        results = []
        my_bar = st.progress(0, text="Khởi tạo thuật toán phân tích đa chiều...")
        index_df = get_index_data("2y")
        
        if index_df is not None:
            total_tickers = sum(len(tickers) for tickers in SECTORS.values())
            count = 0
            for sector, tickers in SECTORS.items():
                for t in tickers:
                    df = get_data(t, "2y")
                    if df is not None:
                        res = analyze_unified_wyckoff(df, index_df, t)
                        if res: 
                            res["Ngành"] = sector
                            results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang phân tích cấu trúc & giá trị nội tại: {t}...")
                    time.sleep(0.05)
            
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Có {len(results)} mã thỏa mãn mọi điều kiện khắt khe của Wyckoff.")
                df_res = pd.DataFrame(results)[["Ngành", "Mã", "Mẫu Hình", "Ngày Bắt Đầu TR", "Khung TR", "Giá HT", "Top-Down", "Giai đoạn", "POE", "SL"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning("Thị trường hiện tại không có thiết lập nào đạt chuẩn Tích Luỹ / Tái Tích Luỹ GGU.")
        else:
            st.error("Lỗi kết nối dữ liệu VN-Index.")

# --- TAB 2: BACKTEST CHIẾN DỊCH ---
with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch (Sửa lỗi Định vị TR)")
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.selectbox("Chọn mã muốn Backtest (2 năm qua):", 
                                  [t for tickers in SECTORS.values() for t in tickers])
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

            # Bắt đầu quét từ ngày 201 để đảm bảo window có đủ 200 ngày dữ liệu lịch sử
            for i in range(200, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-200 : i+1]
                    res = analyze_unified_wyckoff(window, index_bt, test_ticker)
                    
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
