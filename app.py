import streamlit as st
import yfinance as yf
import pandas as pd
import time
import numpy as np

st.set_page_config(page_title="Wyckoff Master: GGU System", layout="wide")
st.title("🏛️ Hệ Thống Wyckoff GGU: Tracking Smart Money")
st.markdown("Xác định Cấu trúc Tích lũy, Lọc VSA Loại trừ Phân phối, và Định vị Kế hoạch Giao dịch")

SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN", "STB.VN", "VPB.VN", "ACB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN", "MBS.VN", "FTS.VN"],
    "Thép": ["HPG.VN", "HSG.VN", "NKG.VN", "VGS.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "DXG.VN", "DIG.VN", "KBC.VN", "PDR.VN", "NLG.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN"]
}

@st.cache_data(ttl=900)
def get_data(ticker, period="1y"):
    try:
        df = yf.Ticker(ticker).history(period=period)
        if len(df) < 150: return None
        return df
    except:
        return None

@st.cache_data(ttl=900)
def get_index_data(period="1y"):
    try:
        df = yf.Ticker("^VNINDEX").history(period=period)
        if df is not None and len(df) > 20: return df
        return yf.Ticker("E1VFVN30.VN").history(period=period)
    except:
        return yf.Ticker("E1VFVN30.VN").history(period=period)

def analyze_ggu_wyckoff(df, index_df, ticker):
    df = df.copy()
    index_df = index_df.copy()
    
    # 1. ĐỒNG BỘ DỮ LIỆU
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)

    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # 2. SỨC MẠNH TƯƠNG ĐỐI (RS) SO VỚI THỊ TRƯỜNG CHUNG
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 20: return None 
    rs_line = combined['Close_s'] / combined['Close_i']
    is_rs_strong = rs_line.iloc[-1] > rs_line.rolling(20).mean().iloc[-1]

    # 3. NHẬN DIỆN CẤU TRÚC (TRADING RANGE) & SỰ KIỆN SC
    lookback_window = 120
    lookback = df.tail(lookback_window)
    min_price = lookback['Low'].min()
    max_price = lookback['High'].max()
    
    # Định vị SC (Ngày có Vol lớn nhất ở nửa dưới của hộp)
    bottom_half = min_price + (max_price - min_price) * 0.4
    potential_sc = lookback[lookback['Low'] <= bottom_half]
    if potential_sc.empty: return None
    
    sc_date = potential_sc['Volume'].idxmax()
    sc_low = float(lookback.loc[sc_date]['Low'])
    
    # Định vị AR (Đỉnh phục hồi sau SC)
    after_sc = df.loc[sc_date:].head(25)
    if len(after_sc) < 5: return None 
    ar_high = float(after_sc['High'].max())
    
    # Xác lập Trading Range (TR)
    tr_low = sc_low
    tr_high = ar_high
    box_height = tr_high - tr_low
    if tr_low == 0 or (box_height / tr_low) < 0.08: return None

    # 4. BỘ LỌC VSA: PHÂN BIỆT TÍCH LŨY (GOM) VS PHÂN PHỐI (XẢ)
    since_sc = df.loc[sc_date:]
    up_days = since_sc[since_sc['Close'] > since_sc['Open']]
    down_days = since_sc[since_sc['Close'] < since_sc['Open']]
    
    avg_up_vol = up_days['Volume'].mean() if not up_days.empty else 0
    avg_down_vol = down_days['Volume'].mean() if not down_days.empty else 0
    
    # Nếu Vol ngày giảm > Vol ngày tăng -> Cấu trúc Phân Phối -> BỎ QUA NGAY LẬP TỨC
    if avg_down_vol > avg_up_vol: return None 

    # 5. ĐỊNH VỊ PHA (PHASE) & ĐIỂM VÀO LỆNH (POE)
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    bottom_zone = tr_low + (box_height * 0.3)
    
    phase = None
    vung_mua_poe = ""
    cat_lo = ""
    chien_dich = ""
    
    # Chỉ đánh khi RS khỏe và Cấu trúc là Tích Lũy
    if is_rs_strong:
        # PHA C (Spring / Shakeout): Rũ bỏ thủng SC và rút chân mạnh
        if current_close <= tr_low * 1.05 and current_close >= tr_low * 0.95:
            if current_close > current_open and current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.8:
                phase = "Pha C (Spring/Test)"
                chien_dich = "Khởi đầu Long-term Campaign"
                vung_mua_poe = f"Mua bắt Spring quanh {round(current_close, 2)}"
                cat_lo = f"Thủng {round(current_close * 0.95, 2)}"
                
        # PHA D (SOS / LPS): Vượt MA50, Vol nến xanh tăng vọt, nến đỏ cạn Vol
        elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high * 0.98:
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2 and current_close > current_open:
                phase = "Pha D (SOS - Dòng tiền kích hoạt)"
                chien_dich = "Long-term Campaign"
                vung_mua_poe = f"Chờ LPS (chỉnh nhẹ) về {round(float(df['MA50'].iloc[-1]), 2)}"
                cat_lo = f"Thủng MA50 ({round(float(df['MA50'].iloc[-1]) * 0.97, 2)})"
                
        # PHA E (Mark-up): Breakout khỏi Kháng cự AR
        elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
                phase = "Pha E (Breakout/Mark-up)"
                chien_dich = "Long-term Campaign (FOMO)"
                vung_mua_poe = f"Chờ BUEC (test lại đỉnh) quanh {round(tr_high, 2)}"
                cat_lo = f"Thủng {round(tr_high * 0.96, 2)}"

        # PHA A/B (Lình xình trong TR): Đánh Swing
        elif current_close <= bottom_zone and current_close >= tr_low:
            if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.75:
                phase = "Pha A/B (Kiểm định biên dưới)"
                chien_dich = "Swing Trade (Lướt sóng ngắn)"
                vung_mua_poe = f"Mua hỗ trợ {round(tr_low, 2)} - Target {round(tr_high, 2)}"
                cat_lo = f"Thủng {round(tr_low * 0.96, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Chiến lược": chien_dich,
            "Khung TR (Hỗ trợ - Kháng cự)": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Giá HT": round(current_close, 2), 
            "Vị thế Wyckoff": phase,
            "Bối cảnh VSA": "✅ Tích lũy (Cầu > Cung)",
            "Điểm Mua (POE)": vung_mua_poe,
            "Cắt Lỗ (SL)": cat_lo
        }
    return None

# ==========================================
# GIAO DIỆN WEB (TABS)
# ==========================================
tab1, tab2 = st.tabs(["🎯 Radar Săn Mã (Lọc VSA)", "🧪 Backtest Chiến Dịch Kép"])

# --- TAB 1: RADAR SĂN MÃ ---
with tab1:
    st.markdown("### 🦅 Quét Tín Hiệu Giao Dịch Chuẩn GGU (Loại bỏ Phân Phối)")
    if st.button("🚀 KÍCH HOẠT RADAR"):
        results = []
        my_bar = st.progress(0, text="Khởi động hệ thống phân tích VSA...")
        index_df = get_index_data("1y")
        
        if index_df is not None:
            total_tickers = sum(len(tickers) for tickers in SECTORS.values())
            count = 0
            for sector, tickers in SECTORS.items():
                for t in tickers:
                    df = get_data(t, "1y")
                    if df is not None:
                        res = analyze_ggu_wyckoff(df, index_df, t)
                        if res: results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang phân tích cấu trúc {t}...")
                    time.sleep(0.05)
            
            my_bar.empty()
            if results:
                st.success(f"Radar hoàn tất! Tìm thấy {len(results)} mã đang Tích Lũy / Tái Tích Lũy chuẩn.")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
            else:
                st.info("Hệ thống VSA quét gắt gao: Thị trường đang rủi ro, chưa có mã nào thoát khỏi cấu trúc Phân phối.")
        else:
            st.error("Lỗi kết nối dữ liệu Thị trường chung.")

# --- TAB 2: BACKTEST CHIẾN DỊCH ---
with tab2:
    st.markdown("### 🧪 Mô phỏng Chiến thuật Swing Trade & Long-term Campaign")
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.selectbox("Chọn mã muốn Backtest (1 năm qua):", 
                                  [t for tickers in SECTORS.values() for t in tickers])
    with col2:
        st.write("")
        st.write("")
        run_bt = st.button("⚙️ Chạy Mô Phỏng Giao Dịch")

    if run_bt:
        df_bt = get_data(test_ticker, "1y")
        index_bt = get_index_data("1y")
        
        if df_bt is not None and index_bt is not None:
            trades = []
            in_position = False
            entry_price = 0
            stop_loss = 0
            take_profit = 0
            trade_type = ""
            entry_date = ""
            campaign = ""

            # Bắt đầu quét từ phiên 150 để có đủ dữ liệu tạo Trading Range ban đầu
            for i in range(150, len(df_bt)):
                current_date = df_bt.index[i]
                current_close = float(df_bt['Close'].iloc[i])
                current_low = float(df_bt['Low'].iloc[i])
                current_high = float(df_bt['High'].iloc[i])

                if not in_position:
                    window = df_bt.iloc[i-150 : i+1]
                    res = analyze_ggu_wyckoff(window, index_bt, test_ticker)
                    
                    if res:
                        in_position = True
                        entry_price = current_close
                        entry_date = current_date.strftime("%d/%m/%Y")
                        trade_type = res["Vị thế Wyckoff"]
                        campaign = res["Chiến lược"]
                        
                        # Set Target và Stoploss tùy theo Chiến dịch
                        if "Swing" in campaign:
                            tr_high = float(res["Khung TR (Hỗ trợ - Kháng cự)"].split(" - ")[1])
                            tr_low = float(res["Khung TR (Hỗ trợ - Kháng cự)"].split(" - ")[0])
                            take_profit = tr_high
                            stop_loss = tr_low * 0.95 # Thủng hỗ trợ 5% cắt
                        else:
                            # Long-term Campaign: Gồng vô cực, dời Trailing Stop theo MA50
                            take_profit = float('inf') 
                            stop_loss = float(window['MA50'].iloc[-1]) * 0.95

                else:
                    sell_reason = ""
                    exit_price = 0
                    
                    # Cập nhật Trailing Stop cho Long-term
                    if "Long-term" in campaign:
                        current_ma50 = float(df_bt['Close'].rolling(50).mean().iloc[i])
                        new_stop = current_ma50 * 0.95
                        if new_stop > stop_loss: stop_loss = new_stop 

                    # Kiểm tra thoát lệnh
                    if current_low <= stop_loss:
                        exit_price = stop_loss
                        sell_reason = "Chạm Trailing Stop / Cắt lỗ"
                    elif current_high >= take_profit:
                        exit_price = take_profit
                        sell_reason = "Chốt lời Swing (Chạm Kháng cự)"

                    if exit_price > 0:
                        profit_pct = ((exit_price - entry_price) / entry_price) * 100
                        trades.append({
                            "Ngày Mua": entry_date,
                            "Chiến Lược": campaign,
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
                
                st.markdown("#### 📊 Báo Cáo Giao Dịch (Campaign Report)")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng số lệnh", f"{len(df_trades)} lệnh")
                m2.metric("Tỷ lệ Thắng (Win Rate)", f"{round(win_rate, 1)}%")
                m3.metric("Tổng LN Lũy kế", f"{round(total_profit, 2)}%")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Chưa có chiến dịch nào được kích hoạt an toàn cho {test_ticker} trong 1 năm qua.")
