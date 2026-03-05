import streamlit as st
import yfinance as yf
import pandas as pd

# Cấu hình giao diện
st.set_page_config(page_title="Wyckoff Screener", layout="wide")
st.title("🛡️ Wyckoff Stock Screener 2026")

# Sidebar để nhập danh sách mã
st.sidebar.header("Cài đặt bộ lọc")
list_macau = st.sidebar.text_area("Nhập danh sách mã (ví dụ: FPT.VN, VCB.VN, HPG.VN, AAPL):", "FPT.VN, VCB.VN, HPG.VN, TCB.VN, DGC.VN")
tickers = [t.strip() for t in list_macau.split(",")]

def scan_wyckoff(ticker):
    try:
        stock = yf.download(ticker, period="1y", interval="1d", progress=False)
        index = yf.download("^VNINDEX", period="1y", interval="1d", progress=False)
        if len(stock) < 100: return None

        # Logic RS và Wyckoff (như đã bàn)
        combined = pd.merge(stock['Close'], index['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
        rs_line = combined['Close_s'] / combined['Close_i']
        rs_sma20 = rs_line.rolling(window=20).mean()
        
        last_close = stock['Close'].iloc[-1]
        ma200 = stock['Close'].rolling(window=200).mean().iloc[-1]
        recent = stock.tail(30)
        tr_width = (recent['High'].max() - recent['Low'].min()) / recent['Low'].min()
        recent_vol = recent['Volume'].mean()
        avg_vol = stock['Volume'].tail(50).mean()

        # Điều kiện lọc: Xu hướng tăng + RS khỏe + Nền siết + Cạn cung
        if last_close > ma200 and rs_line.iloc[-1] > rs_sma20.iloc[-1] and tr_width < 0.12 and recent_vol < avg_vol:
            return {
                "Mã": ticker,
                "Giá": round(float(last_close), 2),
                "Nền siết": f"{round(float(tr_width)*100, 2)}%",
                "RS": "Khỏe hơn VN-Index",
                "Dòng tiền": "Cạn cung (Hấp thụ)"
            }
    except: return None
    return None

if st.button("🚀 Quét thị trường ngay"):
    results = []
    with st.spinner("Đang soi dấu vết cá mập..."):
        for t in tickers:
            res = scan_wyckoff(t)
            if res: results.append(res)
    
    if results:
        st.balloons()
        st.table(pd.DataFrame(results))
    else:
        st.info("Chưa tìm thấy mã nào hội đủ điều kiện 'siêu phẩm'. Hãy kiên nhẫn!")