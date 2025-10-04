import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="Rentry 🐷 ", page_icon="📝", layout="centered")

st.title("📝 Rentry 🐖💨 ")
st.write("heo con xin chào 🐷🎀")

uploaded_file = st.file_uploader("📂 Chọn file Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Kiểm tra cột content
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

                data = {"text": content}
                try:
                    res = requests.post("https://rentry.co/api/new", data=data).json()
                    if "url" in res:
                        results.append({
                            "row": idx+1,
                            "status": "✅ Thành công",
                            "url": res["url"],
                            "edit_code": res["edit_code"]
                        })
                    else:
                        results.append({"row": idx+1, "status": f"❌ Lỗi: {res}", "url": None, "edit_code": None})
                except Exception as e:
                    results.append({"row": idx+1, "status": f"❌ Exception: {e}", "url": None, "edit_code": None})

            result_df = pd.DataFrame(results)
            st.success("🎉 Hoàn tất đăng bài!")
            st.dataframe(result_df)

            # Xuất file Excel kết quả
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
