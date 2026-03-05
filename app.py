import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Pro: Scan & Backtest", layout="wide")
st.title("🦅 Wyckoff Hệ Thống: Scan & Backtest T+10")

# --- DANH SÁCH NGÀNH ---
SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN"],
    "Thép": ["HPG.VN", "HSG.VN", "NKG.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "DXG.VN", "DIG.VN", "KBC.VN", "PDR.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN"]
}

@st.cache_data(ttl=900) 
def get_data(ticker, period="1y"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if len(df) < 60: return None
        return df
    except:
        return None

@st.cache_data(ttl=900)
def get_index_data(period="1y"):
    try:
        return yf.Ticker("^VNINDEX").history(period=period)
    except:
        return None

def analyze_poe(df, index_df, ticker):
    df = df.copy()
    index_df = index_df.copy()
    
    # Ép bỏ múi giờ để gộp dữ liệu không bị lỗi
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)

    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # SỨC MẠNH TƯƠNG ĐỐI (RS)
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    if len(combined) < 20: 
        return None 
        
    rs_line = combined['Close_s'] / combined['Close_i']
    rs_ma20 = rs_line.rolling(20).mean()
    is_rs_strong = rs_line.iloc[-1] > rs_ma20.iloc[-1]

    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    recent_60 = df.tail(60)
    tr_high = float(recent_60['High'].max())
    tr_low = float(recent_60['Low'].min())
    
    if tr_low == 0: return None
    
    box_height = tr_high - tr_low
    box_percent = box_height / tr_low 
    bottom_zone = tr_low + (box_height * 0.25)
    
    phase = None
    vung_mua_poe = ""
    dieu_kien = ""
    cat_lo = ""

    # Chỉ báo mua khi cổ phiếu khỏe hơn VN-Index
    if is_rs_strong:
        if box_percent >= 0.10 and current_close <= bottom_zone and current_close >= tr_low:
            if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.7:
                phase = "Pha A/B (Swing Range)"
                vung_mua_poe = f"Quanh {round(tr_low, 2)} - {round(bottom_zone, 2)}"
                dieu_kien = "Volume cạn kiệt, nến xanh rút chân."
                cat_lo = f"Thủng {round(tr_low * 0.97, 2)}"

        elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
                phase = "Pha E (Breakout)"
                vung_mua_poe = f"Chờ test lại {round(tr_high, 2)}"
                dieu_kien = "Test đỉnh vol thấp (No Supply)."
                cat_lo = f"Thủng {round(tr_high * 0.95, 2)}"
                
        elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high:
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2:
                phase = "Pha D (SOS)"
                vung_mua_poe = f"Chờ LPS quanh {round(float(df['MA50'].iloc[-1]), 2)}"
                dieu_kien = "Chỉnh nhẹ về MA50, vol cạn."
                cat_lo = f"Thủng {round(float(df['MA50'].iloc[-1]) * 0.96, 2)}"
                
        elif current_close <= tr_low * 1.02:
            if current_close > current_open and current_vol > float(df['Vol_MA20'].iloc[-1]):
                phase = "Pha C (Spring)"
                vung_mua_poe = f"Mua tại {round(current_close, 2)}"
                dieu_kien = "Xác nhận rút chân thành công."
                cat_lo = f"Thủng {round(tr_low * 0.95, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Giá HT": round(current_close, 2), 
            "Khung TR": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Tín hiệu": phase,
            "RS": "💪 Khỏe hơn VNI",
            "Điểm Mua": vung_mua_poe,
            "Cắt Lỗ": cat_lo
        }
    return None

# ==========================================
# GIAO DIỆN WEB (TABS)
# ==========================================
tab1, tab2 = st.tabs(["🎯 Lọc Mã Hôm Nay", "🧪 Backtest Lịch Sử"])

# --- TAB 1: LỌC MÃ ---
with tab1:
    st.markdown("### Quét các tín hiệu Wyckoff mạnh hơn thị trường chung")
    if st.button("🦅 BẮT ĐẦU QUÉT"):
        results = []
        my_bar = st.progress(0, text="Đang tải dữ liệu VN-Index...")
        index_df = get_index_data("6mo")
        
        if index_df is not None:
            total_tickers = sum(len(tickers) for tickers in SECTORS.values())
            count = 0
            for sector, tickers in SECTORS.items():
                for t in tickers:
                    df = get_data(t, "6mo")
                    if df is not None:
                        res = analyze_poe(df, index_df, t)
                        if res: results.append(res)
                    count += 1
                    my_bar.progress(count / total_tickers, text=f"Đang quét {t}...")
                    time.sleep(0.1)
            
            my_bar.empty()
            if results:
                st.success(f"Quét xong! Tìm thấy {len(results)} mã thỏa mãn tiêu chí.")
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                st.balloons()
            else:
                st.info("Chưa có mã nào thỏa mãn tiêu chuẩn Sức mạnh tương đối và Wyckoff hôm nay.")
        else:
            st.error("Lỗi tải dữ liệu VN-Index.")

# --- TAB 2: BACKTEST ---
with tab2:
    st.markdown("### Kiểm thử tỷ lệ thắng (Win Rate) sau T+10 ngày")
    col1, col2 = st.columns([1, 2])
    with col1:
        test_ticker = st.selectbox("Chọn mã muốn Backtest (1 năm qua):", 
                                  [t for tickers in SECTORS.values() for t in tickers])
    with col2:
        st.write("")
        st.write("")
        run_bt = st.button("⚙️ Chạy Backtest")

    if run_bt:
        df_bt = get_data(test_ticker, "1y")
        index_bt = get_index_data("1y")
        
        if df_bt is not None and index_bt is not None:
            trades = []
            for i in range(60, len(df_bt) - 10):
                window = df_bt.iloc[i-60 : i+1]
                res = analyze_poe(window, index_bt, test_ticker)
                
                if res:
                    entry_date = df_bt.index[i].strftime("%d/%m/%Y")
                    entry_price = res["Giá HT"]
                    exit_price = float(df_bt['Close'].iloc[i+10])
                    profit_pct = ((exit_price - entry_price) / entry_price) * 100
                    
                    trades.append({
                        "Ngày mua": entry_date,
                        "Tín hiệu": res["Tín hiệu"],
                        "Giá mua": entry_price,
                        "Giá T+10": round(exit_price, 2),
                        "Lợi nhuận (%)": round(profit_pct, 2)
                    })
            
            if trades:
                df_trades = pd.DataFrame(trades)
                win_trades = df_trades[df_trades["Lợi nhuận (%)"] > 0]
                win_rate = (len(win_trades) / len(df_trades)) * 100
                avg_profit = df_trades["Lợi nhuận (%)"].mean()
                
                st.markdown("#### 📊 Báo Cáo Tổng Quan")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng số lệnh báo Mua", f"{len(df_trades)} lệnh")
                m2.metric("Tỷ lệ Thắng (Win Rate)", f"{round(win_rate, 1)}%")
                m3.metric("Lợi nhuận TB mỗi lệnh", f"{round(avg_profit, 2)}%")
                
                st.markdown("#### 📈 Biểu đồ Lợi nhuận từng lệnh (%)")
                st.bar_chart(df_trades.set_index("Ngày mua")["Lợi nhuận (%)"])
                
                st.markdown("#### 📝 Lịch sử giao dịch chi tiết")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Không có tín hiệu mua nào xuất hiện cho {test_ticker} trong 1 năm qua.")
