# --- 7. VENDOR & RESIN HIERARCHY (MINDMAP VIEW) ---
st.markdown("---")
st.subheader("🌳 Vendor-Resin Hierarchical Analysis")
st.markdown("Khung nhìn phân nhánh chi tiết tổng lượng sơn, dung môi và **Độ nhạy (Sensitivity)**. Nhấp vào từng phần tử trên biểu đồ để phóng to (Zoom in) nhánh đó.")

# 1. Bảng điều khiển bộ lọc cho Tree View
col_t1, col_t2 = st.columns([1, 3])
with col_t1:
    # Cho phép chọn Vendor làm trung tâm (như Yungchi trong ảnh)
    vendors_list = group_a['Vendor'].dropna().unique().tolist()
    if not vendors_list:
        vendors_list = ['Unknown']
        
    selected_tree_vendor = st.selectbox("🏢 Select Central Vendor", vendors_list)

with col_t2:
    st.info("💡 **Cách đọc biểu đồ:** Kích thước (độ rộng) của vòng cung thể hiện Tổng lượng sơn sử dụng. **Màu sắc** thể hiện Độ nhạy (% dung môi / 1s). Màu **Đỏ/Cam** cảnh báo các công thức tốn nhiều dung môi (ví dụ: điểm khoanh đỏ PVDF của bạn).")

# 2. Xử lý dữ liệu cho cấu trúc cây
tree_data = group_a[group_a['Vendor'] == selected_tree_vendor].copy()

# Thay thế các giá trị NaN/Null bằng chữ 'Unknown' để biểu đồ không bị lỗi đứt gãy
tree_data['Solvent_Type'] = tree_data['Solvent_Type'].fillna('Unknown')
tree_data['Resin'] = tree_data['Resin'].fillna('Unknown')

if not tree_data.empty:
    # Gom nhóm dữ liệu theo lớp: Vendor -> Resin -> Solvent
    tree_summary = tree_data.groupby(['Vendor', 'Resin', 'Solvent_Type']).agg({
        '塗料重量': 'sum',      # Kích thước Node
        '添加重量': 'sum',
        'Sensitivity': 'mean' # Màu sắc Node
    }).reset_index()

    # Chỉ lấy các giá trị nhạy dương để scale màu chính xác
    tree_summary = tree_summary[tree_summary['Sensitivity'] > 0]

    if not tree_summary.empty:
        # 3. Vẽ biểu đồ Sunburst (Đóng vai trò như Mindmap tương tác)
        fig_tree = px.sunburst(
            tree_summary,
            path=['Vendor', 'Resin', 'Solvent_Type'], # Đường dẫn trung tâm -> nhánh -> lá
            values='塗料重量', # Kích thước lát cắt tỷ lệ với lượng sơn
            color='Sensitivity', # Màu sắc đánh giá hiệu suất
            color_continuous_scale='RdYlGn_r', # Đảo ngược màu: Cao (tốn kém) = Đỏ, Thấp = Xanh
            hover_data={
                '添加重量': ':,.1f',
                'Sensitivity': ':.2f'
            },
            title=f"Hierarchical Performance Mindmap - {selected_tree_vendor}"
        )
        
        # Format lại hover template cho dễ đọc giống thông số trong ảnh của bạn
        fig_tree.update_traces(
            hovertemplate='<b>%{label}</b><br>' +
                          'Total Paint: %{value:,.0f} kg<br>' +
                          'Solvent Added: %{customdata[0]:,.0f} kg<br>' +
                          'Sensitivity: <b>%{color:.2f}% per 1s</b><extra></extra>'
        )

        fig_tree.update_layout(
            height=600, 
            margin=dict(t=40, l=0, r=0, b=0),
            coloraxis_colorbar=dict(title="Sensitivity (%)<br><i>(Đỏ = Tốn dung môi)</i>")
        )

        st.plotly_chart(fig_tree, use_container_width=True)
        
        # 4. Bảng Drill-down hiển thị các điểm bất thường (như PVDF)
        st.write("🚩 **Top High-Sensitivity Alerts (Cảnh báo tốn dung môi):**")
        alerts = tree_summary.sort_values(by='Sensitivity', ascending=False).head(3)
        
        if not alerts.empty:
            cols = st.columns(len(alerts))
            for idx, (_, row) in enumerate(alerts.iterrows()):
                with cols[idx]:
                    st.error(f"""
                    **{row['Resin']}** + **{row['Solvent_Type']}**
                    * Paint: {row['塗料重量']:,.0f} kg
                    * Sensitivity: **{row['Sensitivity']:.2f}% per 1s drop**
                    """)
    else:
        st.warning("Không có dữ liệu Sensitivity hợp lệ để vẽ biểu đồ cho Vendor này.")
else:
    st.warning("Chưa có dữ liệu cho Vendor được chọn.")
