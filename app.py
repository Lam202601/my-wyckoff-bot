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

# ttl=900 nghĩa là lưu bộ nhớ đệm 15 phút. Cứ sau 15p bấm quét là có dữ liệu mới
@st.cache_data(ttl=900) 
def get_data(ticker, period="1y"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if len(df) < 60: return None
        return df
    except:
        return None

def analyze_poe(df, ticker):
    df = df.copy() # Tạo bản sao để tránh lỗi dữ liệu
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    # Kẻ hộp 60 phiên
    recent_60 = df.tail(60)
    tr_high = float(recent_60['High'].max())
    tr_low = float(recent_60['Low'].min())
    
    if tr_low == 0: return None
    
    box_height = tr_high - tr_low
    box_percent = box_height / tr_low 
    bottom_zone = tr_low + (box_height * 0.25)
    
    phase = None
    
    # 1. SWING TRADE (PHA A/B)
    if box_percent >= 0.10 and current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.7:
            phase = "Pha A/B (Swing Range)"

    # 2. XU HƯỚNG (PHA C, D, E)
    elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
            phase = "Pha E (Breakout)"
            
    elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2:
            phase = "Pha D (SOS)"
            
    elif current_close <= tr_low * 1.02:
        if current_close > current_open and current_vol > float(df['Vol_MA20'].iloc[-1]):
            phase = "Pha C (Spring)"

    if phase:
        return {"Mã": ticker.replace(".VN", ""), "Giá": round(current_close, 2), "Giai đoạn": phase}
    return None

# ==========================================
# TẠO 2 TAB GIAO DIỆN
# ==========================================
tab1, tab2 = st.tabs(["🎯 Lọc Mã Hôm Nay", "🧪 Backtest Lịch Sử"])

# --- TAB 1: LỌC MÃ ---
with tab1:
    st.markdown("### Quét các tín hiệu Wyckoff mới nhất trên thị trường")
    if st.button("🦅 BẮT ĐẦU QUÉT"):
        results = []
        my_bar = st.progress(0, text="Đang tải dữ liệu...")
        total_tickers = sum(len(tickers) for tickers in SECTORS.values())
        count = 0
        
        for sector, tickers in SECTORS.items():
            for t in tickers:
                df = get_data(t, "6mo")
                if df is not None:
                    res = analyze_poe(df, t)
                    if res: results.append(res)
                count += 1
                my_bar.progress(count / total_tickers, text=f"Đang quét {t}...")
                time.sleep(0.1)
                
        my_bar.empty()
        if results:
            st.success(f"Quét xong! Tìm thấy {len(results)} mã.")
            st.table(pd.DataFrame(results))
            st.balloons()
        else:
            st.info("Chưa có mã nào đạt tiêu chuẩn hôm nay.")

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
        if df_bt is not None:
            trades = []
            # Chạy vòng lặp từ ngày 60 đến cách hiện tại 10 ngày (để đủ time đo T+10)
            for i in range(60, len(df_bt) - 10):
                # Cắt lát dữ liệu đến ngày i
                window = df_bt.iloc[i-60 : i+1]
                res = analyze_poe(window, test_ticker)
                
                if res:
                    entry_date = df_bt.index[i].strftime("%d/%m/%Y")
                    entry_price = res["Giá"]
                    # Lấy giá trị sau 10 ngày (T+10)
                    exit_price = float(df_bt['Close'].iloc[i+10])
                    profit_pct = ((exit_price - entry_price) / entry_price) * 100
                    
                    trades.append({
                        "Ngày mua": entry_date,
                        "Tín hiệu": res["Giai đoạn"],
                        "Giá mua": entry_price,
                        "Giá T+10": round(exit_price, 2),
                        "Lợi nhuận (%)": round(profit_pct, 2)
                    })
            
            if trades:
                df_trades = pd.DataFrame(trades)
                # Tính toán thống kê
                win_trades = df_trades[df_trades["Lợi nhuận (%)"] > 0]
                win_rate = (len(win_trades) / len(df_trades)) * 100
                avg_profit = df_trades["Lợi nhuận (%)"].mean()
                
                # Hiển thị Metrics tổng quan
                st.markdown("#### 📊 Báo Cáo Tổng Quan")
                m1, m2, m3 = st.columns(3)
                m1.metric("Tổng số lần báo Mua", f"{len(df_trades)} lần")
                m2.metric("Tỷ lệ Thắng (Win Rate)", f"{round(win_rate, 1)}%")
                m3.metric("Lợi nhuận TB mỗi lệnh", f"{round(avg_profit, 2)}%")
                
                # Biểu đồ trực quan lợi nhuận
                st.markdown("#### 📈 Biểu đồ Lợi nhuận từng lệnh (%)")
                st.bar_chart(df_trades.set_index("Ngày mua")["Lợi nhuận (%)"])
                
                # Bảng chi tiết
                st.markdown("#### 📝 Lịch sử giao dịch chi tiết")
                st.dataframe(df_trades, use_container_width=True)
            else:
                st.warning(f"Không có tín hiệu mua nào xuất hiện cho {test_ticker} trong 1 năm qua.")
