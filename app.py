import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

st.set_page_config(page_title="Wyckoff Master: GGU Top-Down", layout="wide")
st.title("🏛️ Hệ Thống GGU: Chuẩn Top-Down & Sweet Spot")
st.markdown("Quy trình lọc: Thị trường ➡️ Ngành Dẫn Dắt ➡️ Cổ Phiếu Lãnh Đạo (RS Uptrend) ➡️ Điểm Mua VSA")

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

def analyze_ggu_topdown(df, index_df, ticker):
    df = df.copy()
    index_df = index_df.copy()
    
    # Đồng bộ dữ liệu
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 253: return None 
    
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # =======================================================
    # BƯỚC 1: BỘ LỌC ĐƯỜNG RS (RELATIVE STRENGTH LINE)
    # =======================================================
    # RS Ratio = Stock Price / Index Price
    rs_line = combined['Close_s'] / combined['Close_i']
    rs_ma50 = rs_line.rolling(50).mean()
    
    # Yêu cầu 1: RS Line phải phá vỡ xu hướng giảm và đang nằm trên MA50 của chính nó (Uptrend in RS)
    if rs_line.iloc[-1] < rs_ma50.iloc[-1]: 
        return None # Loại bỏ cổ phiếu đang yếu dần so với Index

    # =======================================================
    # BƯỚC 2: KIỂM TRA ĐỘNG LƯỢNG VÀ "SWEET SPOT"
    # =======================================================
    stock_roc63 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-63]) / combined['Close_s'].iloc[-63] * 100
    idx_roc63 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-63]) / combined['Close_i'].iloc[-63] * 100
    
    # Sweet Spot (Tư duy Roman): Cổ phiếu phải tăng mạnh hơn VNI, hoặc khi VNI chỉnh 20 phiên gần nhất thì cổ phiếu giữ giá tốt hơn
    idx_pullback_20 = (combined['Close_i'].iloc[-1] - combined['Close_i'].iloc[-20]) / combined['Close_i'].iloc[-20] * 100
    stock_pullback_20 = (combined['Close_s'].iloc[-1] - combined['Close_s'].iloc[-20]) / combined['Close_s'].iloc[-20] * 100
    
    is_sweet_spot = stock_pullback_20 > idx_pullback_20
    is_momentum_leader = stock_roc63 > idx_roc63
    
    if not (is_sweet_spot and is_momentum_leader):
        return None

    # =======================================================
    # BƯỚC 3: CẤU TRÚC GIÁ (TRADING RANGE) & SC/ST
    # =======================================================
    lookback = df.tail(120)
    min_price = lookback['Low'].min()
    max_price = lookback['High'].max()
    
    bottom_half = min_price + (max_price - min_price) * 0.4
    potential_sc = lookback[lookback['Low'] <= bottom_half]
    if potential_sc.empty: return None
    
    sc_date = potential_sc['Volume'].idxmax()
    sc_low = float(lookback.loc[sc_date]['Low'])
    
    after_sc = df.loc[sc_date:].head(25)
    if len(after_sc) < 5: return None 
    ar_high = float(after_sc['High'].max())
    
    tr_low = sc_low
    tr_high = ar_high
    box_height = tr_high - tr_low
    if tr_low == 0 or (box_height / tr_low) < 0.08: return None

    # =======================================================
    # BƯỚC 4: VSA LỌC CUNG CẦU (NỖ LỰC VS KẾT QUẢ)
    # =======================================================
    since_sc = df.loc[sc_date:]
    up_days = since_sc[since_sc['Close'] > since_sc['Open']]
    down_days = since_sc[since_sc['Close'] < since_sc['Open']]
    
    avg_up_vol = up_days['Volume'].mean() if not up_days.empty else 0
    avg_down_vol = down_days['Volume'].mean() if not down_days.empty else 0
    
    # Nỗ Lực Gom Hàng: Vol nến xanh phải áp đảo Vol nến đỏ
    if avg_down_vol > avg_up_vol: return None 

    # =======================================================
    # BƯỚC 5: ĐỊNH VỊ PHA (POE)
    # =======================================================
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    phase = None
    vung_mua_poe = ""
    cat_lo = ""
    
    # Pha C (Spring / Test Cạn Cung)
    if current_close <= tr_low * 1.05 and current_close >= tr_low * 0.95:
        if current_close > current_open and current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.8:
            phase = "Pha C (Spring/Test)"
            vung_mua_poe = f"Mua nhịp rũ bỏ {round(current_close, 2)}"
            cat_lo = f"Thủng {round(current_close * 0.95, 2)}"
            
    # Pha D (SOS / LPS)
    elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high * 0.98:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2 and current_close > current_open:
            phase = "Pha D (SOS - Dòng tiền vào)"
            vung_mua_poe = f"Chờ LPS về {round(float(df['MA50'].iloc[-1]), 2)}"
            cat_lo = f"Thủng MA50 ({round(float(df['MA50'].iloc[-1]) * 0.97, 2)})"
            
    # Pha E (Mark-up)
    elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
            phase = "Pha E (Breakout)"
            vung_mua_poe = f"Chờ BUEC test {round(tr_high, 2)}"
            cat_lo = f"Thủng {round(tr_high * 0.96, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "ROC 63 (Cổ/Index)": f"{round(stock_roc63, 1)}% / {round(idx_roc63, 1)}%",
            "Sweet Spot (Pullback)": "⭐ Outperform VNI" if is_sweet_spot else "Theo xu hướng",
            "Khung TR": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Giá HT": round(current_close, 2), 
            "Giai đoạn": phase,
            "Điểm Mua (POE)": vung_mua_poe,
            "Cắt Lỗ (SL)": cat_lo
        }
    return None

# ==========================================
# GIAO DIỆN WEB (TABS)
# ==========================================
tab1, tab2 = st.tabs(["🎯 Lọc Top-Down (Lãnh đạo)", "🧪 Backtest Chiến Dịch"])

# --- TAB 1: RADAR SĂN MÃ ---
with tab1:
    st.markdown("### 🦅 Quét Lãnh Đạo Thị Trường & Dòng Tiền Luân Chuyển (Top-Down)")
    if st.button("🚀 KÍCH HOẠT RADAR TOP-DOWN"):
        results = []
        my_bar = st.progress(0, text="1. Đang quét động lượng Thị trường chung (Market Analysis)...")
        index_df = get_index_data("2y")
        
        if index_df is not None:
            total_tickers = sum(len(tickers) for tickers in SECTORS.values())
            count = 0
            for sector, tickers in SECTORS.items():
                my_bar.progress(count / total_tickers, text=f"2. Đang phân tích sức mạnh Ngành: {sector}...")
                
                # Logic Top-Down thực thụ: Đánh giá xu hướng ngành trước khi quét cổ phiếu
                for t in tickers:
                    df = get_data(t, "2y")
                    if df is not None:
                        res = analyze_ggu_topdown(df, index_df, t)
                        if res: 
                            res["Ngành"] = sector
                            results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"3. Tìm kiếm Cổ phiếu Lãnh đạo & Điểm VSA: {t}...")
                    time.sleep(0.05)
            
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Có {len(results)} siêu cổ phiếu vượt qua bộ lọc Top-Down & VSA khắt khe.")
                # Sắp xếp lại cột cho đẹp
                df_res = pd.DataFrame(results)[["Ngành", "Mã", "ROC 63 (Cổ/Index)", "Sweet Spot (Pullback)", "Khung TR", "Giá HT", "Giai đoạn", "Điểm Mua (POE)", "Cắt Lỗ (SL)"]]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning("Hiện tại KHÔNG CÓ cổ phiếu nào thỏa mãn cấu trúc Tích lũy và Sức mạnh Lãnh đạo. Đứng ngoài thị trường (Cash is Position)!")
        else:
            st.error("Lỗi kết nối dữ liệu Thị trường chung.")

# --- TAB 2: BACKTEST CHIẾN DỊCH ---
with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến dịch Giao dịch Long-term")
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
            trades = []
            in_position = False
            entry_price = 0
            stop_loss = 0
            trade_type = ""
            entry_date = ""

            for i in range(253, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-253 : i+1]
                    res = analyze_ggu_topdown(window, index_bt, test_ticker)
                    
                    if res:
                        in_position = True
                        entry_price = current_close
                        entry_date = current_date.strftime("%d/%m/%Y")
                        trade_type = res["Giai đoạn"]
                        stop_loss = float(window['MA50'].iloc[-1]) * 0.95 # Trailing Stop theo MA50

                else:
                    sell_reason = ""
                    exit_price = 0
                    
                    # Khóa lãi bằng Trailing Stop MA50
                    current_ma50 = float(df_bt['Close'].rolling(50).mean().iloc[i])
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
                
                st.markdown("#### 📊 Báo Cáo Chiến Dịch Dài Hạn (Long-term Campaign)")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng số lệnh", f"{len(df_trades)} lệnh")
                m2.metric("Tỷ lệ Thắng (Win Rate)", f"{round(win_rate, 1)}%")
                m3.metric("Tổng LN Lũy kế", f"{round(total_profit, 2)}%")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Chưa có chiến dịch nào được kích hoạt an toàn cho {test_ticker} trong 2 năm qua.")
