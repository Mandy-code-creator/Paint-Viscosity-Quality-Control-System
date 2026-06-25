# =========================================================
# TAB 4: PRINTED WORKER LOOKUP SOP
# =========================================================
with tab4:
    st.markdown("### 🖨️ Printed Worker Lookup SOP")

    st.markdown(
        "Quick-reference SOP for operators without dashboard access. "
        "Select the correct Resin, Vendor, Solvent, Initial Viscosity Range "
        "and Paint Weight Range. Add Stage 1 only, then mix and re-measure."
    )

    st.warning(
        "⚠️ **Mandatory Rule:** Do NOT add Stage 2 or Stage 3 continuously. "
        "After every addition, mix completely and measure viscosity again."
    )

    st.info(
        "💡 **Calculation Method Used in This Table:** "
        "Operating Dilution Base = Typical Paint Weight + 120 kg. "
        "Historical Total Solvent = median actual solvent addition from "
        "similar historical batches. "
        "Stage 1 = Historical Total Solvent × 60%; "
        "Stage 2 = Historical Total Solvent × 25%; "
        "Stage 3 = Historical Total Solvent × 15%."
    )

    st.caption(
        "⚠️ The displayed solvent dose is a historical lookup value for the "
        "specified Resin + Vendor + Solvent + Viscosity Range + Paint Weight Range. "
        "Do not multiply the dose directly by viscosity-drop seconds, because "
        "dilution efficiency may decrease at higher solvent ratios."
    )

    matrix_df = master_df.copy()

    # =====================================================
    # 1. PAINT WEIGHT RANGE FOR PRINTED LOOKUP
    # =====================================================
    weight_bins = [0, 25, 50, 80, 120, 200, np.inf]

    weight_labels = [
        "0-25 kg",
        "26-50 kg",
        "51-80 kg",
        "81-120 kg",
        "121-200 kg",
        ">200 kg"
    ]

    matrix_df["Paint_Weight_Range"] = pd.cut(
        matrix_df["塗料重量"],
        bins=weight_bins,
        labels=weight_labels,
        include_lowest=True,
        right=True
    )

    # =====================================================
    # 2. OPERATOR LOOKUP TABLE
    # =====================================================
    worker_sop = matrix_df.groupby(
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Paint_Weight_Range"
        ],
        observed=False
    ).agg(
        Valid_Batches=("塗料批號", "nunique"),
        Typical_Paint_Weight=("塗料重量", "median"),
        Typical_Target_Visc=("黏度(秒)_1", "median"),
        Historical_Total_Solvent=("添加重量", "median"),
        Historical_Solvent_P90=(
            "添加重量",
            lambda x: x.quantile(0.90)
        ),
        Median_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            "median"
        ),
        P90_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.90)
        ),
        P95_Solvent_Ratio=(
            "Solvent_Ratio_Percent",
            lambda x: x.quantile(0.95)
        )
    ).reset_index()

    worker_sop = worker_sop[
        (worker_sop["Valid_Batches"] >= 5)
        & (worker_sop["Historical_Total_Solvent"] > 0)
    ].copy()

    # =====================================================
    # 3. OPERATING DILUTION BASE
    # =====================================================
    worker_sop["Operating_Dilution_Base"] = (
        worker_sop["Typical_Paint_Weight"] + 120
    )

    # =====================================================
    # 4. STAGED ADDITION QUANTITIES
    # Based on median historical total solvent
    # =====================================================
    worker_sop["Stage_1_Add_kg"] = (
        worker_sop["Historical_Total_Solvent"] * 0.60
    )

    worker_sop["Stage_2_Max_Add_kg"] = (
        worker_sop["Historical_Total_Solvent"] * 0.25
    )

    worker_sop["Stage_3_Max_Add_kg"] = (
        worker_sop["Historical_Total_Solvent"] * 0.15
    )

    worker_sop["Calculation_Basis"] = (
        "Median historical solvent addition"
    )

    worker_sop["Stage_Split_Formula"] = (
        "Stage 1: 60% | Stage 2: 25% | Stage 3: 15%"
    )

    # =====================================================
    # 5. SATURATION THRESHOLDS
    # =====================================================
    saturation_summary = []

    system_keys = matrix_df[
        ["Resin", "Vendor", "Solvent_Type"]
    ].drop_duplicates()

    for _, system_row in system_keys.iterrows():
        resin_value = system_row["Resin"]
        vendor_value = system_row["Vendor"]
        solvent_value = system_row["Solvent_Type"]

        temp_system_df = matrix_df[
            (matrix_df["Resin"] == resin_value)
            & (matrix_df["Vendor"] == vendor_value)
            & (matrix_df["Solvent_Type"] == solvent_value)
        ].copy()

        temp_saturation = build_saturation_profile(temp_system_df)

        saturation_summary.append({
            "Resin": resin_value,
            "Vendor": vendor_value,
            "Solvent_Type": solvent_value,
            "Saturation_Warning_Ratio": (
                temp_saturation["warning_ratio"]
            ),
            "Saturation_Stop_Ratio": (
                temp_saturation["saturation_ratio"]
            )
        })

    saturation_summary_df = pd.DataFrame(saturation_summary)

    worker_sop = worker_sop.merge(
        saturation_summary_df,
        on=["Resin", "Vendor", "Solvent_Type"],
        how="left"
    )

    # No clear saturation pattern:
    # use P90 as warning and P95 as stop safeguard.
    worker_sop["Warning_Ratio"] = (
        worker_sop["Saturation_Warning_Ratio"]
        .fillna(worker_sop["P90_Solvent_Ratio"])
    )

    worker_sop["Stop_Ratio"] = (
        worker_sop["Saturation_Stop_Ratio"]
        .fillna(worker_sop["P95_Solvent_Ratio"])
    )

    # =====================================================
    # 6. OPERATOR INSTRUCTIONS
    # =====================================================
    worker_sop["Stage_1_Instruction"] = (
        "Add Stage 1 → Mix 5 min → Measure"
    )

    worker_sop["Stage_2_Instruction"] = (
        "Only if viscosity remains above USL"
    )

    worker_sop["Stop_Instruction"] = (
        "Stop and contact Process Engineer"
    )

    # =====================================================
    # 7. FINAL PRINTED SOP TABLE
    # =====================================================
    worker_output = worker_sop[
        [
            "Resin",
            "Vendor",
            "Solvent_Type",
            "Initial_Viscosity_Zone",
            "Paint_Weight_Range",
            "Valid_Batches",
            "Typical_Paint_Weight",
            "Operating_Dilution_Base",
            "Typical_Target_Visc",
            "Historical_Total_Solvent",
            "Calculation_Basis",
            "Stage_Split_Formula",
            "Stage_1_Add_kg",
            "Stage_1_Instruction",
            "Stage_2_Max_Add_kg",
            "Stage_2_Instruction",
            "Stage_3_Max_Add_kg",
            "Warning_Ratio",
            "Stop_Ratio",
            "Stop_Instruction"
        ]
    ].copy()

    worker_output.rename(
        columns={
            "Solvent_Type": "Solvent",
            "Initial_Viscosity_Zone": "Initial Viscosity Range",
            "Paint_Weight_Range": "Paint Weight Range",
            "Valid_Batches": "Valid Batches",
            "Typical_Paint_Weight": "Typical Paint Weight (kg)",
            "Operating_Dilution_Base": (
                "Operating Dilution Base (Paint + 120 kg)"
            ),
            "Typical_Target_Visc": "Typical Target (s)",
            "Historical_Total_Solvent": "Historical Total Solvent (kg)",
            "Calculation_Basis": "Calculation Basis",
            "Stage_Split_Formula": "Stage Split Formula",
            "Stage_1_Add_kg": "Stage 1 Add (kg)",
            "Stage_1_Instruction": "Stage 1 Action",
            "Stage_2_Max_Add_kg": "Stage 2 Max Add (kg)",
            "Stage_2_Instruction": "Stage 2 Condition",
            "Stage_3_Max_Add_kg": "Stage 3 Max Add (kg)",
            "Warning_Ratio": "Warning Ratio (%)",
            "Stop_Ratio": "Stop / Engineer Approval (%)",
            "Stop_Instruction": "Escalation Rule"
        },
        inplace=True
    )

    worker_output = worker_output.sort_values(
        by=[
            "Resin",
            "Vendor",
            "Solvent",
            "Initial Viscosity Range",
            "Paint Weight Range"
        ]
    )

    st.dataframe(
        worker_output,
        column_config={
            "Valid Batches": st.column_config.NumberColumn(
                format="%d"
            ),
            "Typical Paint Weight (kg)": st.column_config.NumberColumn(
                format="%.1f kg"
            ),
            "Operating Dilution Base (Paint + 120 kg)": (
                st.column_config.NumberColumn(
                    format="%.1f kg"
                )
            ),
            "Typical Target (s)": st.column_config.NumberColumn(
                format="%.1f s"
            ),
            "Historical Total Solvent (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),
            "Stage 1 Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),
            "Stage 2 Max Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),
            "Stage 3 Max Add (kg)": st.column_config.NumberColumn(
                format="%.2f kg"
            ),
            "Warning Ratio (%)": st.column_config.NumberColumn(
                format="%.1f%%"
            ),
            "Stop / Engineer Approval (%)": (
                st.column_config.NumberColumn(
                    format="%.1f%%"
                )
            )
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.markdown("### Manual Calculation Note")

    st.markdown(
        """
        **Operating Dilution Base**  
        `= Typical Paint Weight + 120 kg`

        **Historical Total Solvent**  
        `= Median actual solvent added in similar historical batches`

        **Stage 1 Addition**  
        `= Historical Total Solvent × 60%`

        **Stage 2 Maximum Addition**  
        `= Historical Total Solvent × 25%`

        **Stage 3 Maximum Addition**  
        `= Historical Total Solvent × 15%`

        **Important:** The Stage 1 / 2 / 3 values are historical lookup values,
        not a linear viscosity-reduction formula. Always measure viscosity after
        every addition.
        """
    )

    csv_export = worker_output.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "📥 Download Printable Worker SOP (CSV)",
        data=csv_export,
        file_name="Printed_Worker_Viscosity_SOP.csv",
        mime="text/csv"
    )
