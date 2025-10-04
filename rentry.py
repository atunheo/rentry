import streamlit as st
import pandas as pd
import requests
import io
import time

st.set_page_config(page_title="Rentry Bulk Poster", page_icon="🐷", layout="centered")

st.title("🐷 Rentry Bulk Poster (Local, API + Form Fallback)")
st.write("Upload file Excel có cột **content**, app sẽ đăng từng bài lên [rentry.co](https://rentry.co).")

uploaded_file = st.file_uploader("📂 Chọn file Excel (.xlsx)", type=["xlsx"])
delay = st.number_input("⏱ Giãn cách giữa các bài (giây)", min_value=0.0, value=3.0, step=0.5)

# Headers giả lập trình duyệt
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://rentry.co",
    "Referer": "https://rentry.co/",
    "Connection": "keep-alive"
}

def post_rentry(content: str):
    """
    Đăng bài lên rentry bằng API, nếu fail thì fallback sang form submit
    """
    data = {"text": content}

    # --- API Mode ---
    try:
        r = requests.post("https://rentry.co/api/new", data=data, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"error": "API trả về không phải JSON", "raw": r.text[:200]}
        else:
            # Thử fallback
            return post_rentry_form(content)
    except Exception as e:
        return {"error": f"API Exception: {e}"}

def post_rentry_form(content: str):
    """
    Fallback: giả lập submit form web
    """
    try:
        r = requests.post("https://rentry.co", data={"text": content}, headers=HEADERS, timeout=20)
        if r.status_code == 200 and "rentry.co/" in r.url:
            # Nếu thành công, link sẽ ở r.url
            return {"url": r.url, "edit_code": "Chỉ có khi dùng API"}
        else:
            return {"error": f"Form mode fail: {r.status_code}", "raw": r.text[:200]}
    except Exception as e:
        return {"error": f"Form Exception: {e}"}

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if "content" not in df.columns:
        st.error("❌ File Excel phải có cột tên là `content`.")
    else:
        st.write("📋 Xem trước dữ liệu:")
        st.dataframe(df.head())

        if st.button("🚀 Bắt đầu đăng"):
            results = []

            for idx, row in df.iterrows():
                content = str(row["content"]).strip()
                if not content or content.lower() == "nan":
                    results.append({"row": idx+1, "status": "❌ Trống", "url": None, "edit_code": None})
                    continue

                res = post_rentry(content)

                if "url" in res:
                    results.append({
                        "row": idx+1,
                        "status": "✅ Thành công",
                        "url": res["url"],
                        "edit_code": res.get("edit_code", "N/A")
                    })
                else:
                    results.append({
                        "row": idx+1,
                        "status": f"❌ Lỗi: {res}",
                        "url": None,
                        "edit_code": None
                    })

                # Giãn cách
                if delay > 0 and idx < len(df) - 1:
                    time.sleep(delay)

            result_df = pd.DataFrame(results)
            st.success("🎉 Hoàn tất đăng bài!")
            st.dataframe(result_df)

            # Xuất Excel kết quả
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                result_df.to_excel(writer, index=False, sheet_name="Results")
            output.seek(0)

            st.download_button(
                label="📥 Tải file kết quả",
                data=output,
                file_name="rentry_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
