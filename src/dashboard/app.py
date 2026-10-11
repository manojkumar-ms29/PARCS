"""PARCS Streamlit Dashboard.

Visualizes Modern Standby telemetry, statistical baselines, anomaly detection,
sustained regressions, and non-causal change correlations.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.client import DEFAULT_API_URL, PARCSApiClient

st.set_page_config(
    page_title="PARCS Analytics & Correlation Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_client(api_url: str) -> PARCSApiClient:
    return PARCSApiClient(base_url=api_url)


def main():
    st.title("⚡ PARCS: Modern Standby Intelligence")
    st.caption("Predictive Analytics, Statistical Baselines, Sustained Regressions & Change Correlation")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_url = st.text_input("Backend API URL", value=DEFAULT_API_URL)
        client = get_client(api_url)

        # Connection health check
        health = client.get_health()
        if health.get("connection") == "online":
            st.success("🟢 API Connected")
        else:
            st.warning("🟠 Running in Local Mode")

        st.divider()

        # Seed demonstration data button
        if st.button("🌱 Seed / Reset Demo Data", use_container_width=True):
            seed_res = client.seed_demo_data()
            if seed_res.get("success"):
                st.success(f"Seeded {seed_res.get('session_records')} sessions and {seed_res.get('change_records')} changes!")
                st.rerun()

        st.divider()
        st.subheader("🔍 Analysis Parameters")
        regression_thresh = st.slider("Harmful Deviation Threshold", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
        min_consecutive = st.number_input("Required Consecutive Sessions", min_value=1, max_value=10, value=3, step=1)
        window_before_h = st.slider("Correlation Window Before (hrs)", min_value=1.0, max_value=72.0, value=24.0, step=1.0)
        window_after_h = st.slider("Correlation Window After (hrs)", min_value=0.5, max_value=24.0, value=2.0, step=0.5)

    # ------------------------------------------------------------------
    # Load Telemetry Summary & Machine Selection
    # ------------------------------------------------------------------
    summary = client.get_telemetry_summary()
    machines = summary.get("machines", [])

    if not machines:
        st.info("No telemetry sessions detected in storage. Click **'Seed / Reset Demo Data'** in the sidebar to load synthetic test data.")
        return

    # Machine selector
    selected_machine = st.selectbox(
        "Select Machine Identifier",
        options=machines,
        index=0,
        help="Filter analytics and correlations strictly by machine identity to preserve isolation.",
    )

    # Machine details & synthetic data check (machine-isolated provenance)
    machine_provenance = summary.get("machine_provenance", {})
    if selected_machine in machine_provenance:
        is_synthetic_machine = bool(machine_provenance[selected_machine])
    else:
        is_synthetic_machine = bool(selected_machine.startswith("DEMO-") or selected_machine.startswith("SYNTHETIC-"))

    if is_synthetic_machine:
        st.warning(
            "⚠️ **DEMONSTRATION FIXTURE (SYNTHETIC DATA)**: "
            f"Machine `{selected_machine}` uses synthetic data generated for end-to-end verification. "
            "It does NOT represent observed telemetry from your local machine."
        )
    else:
        st.info(f"ℹ️ **LOCAL SYSTEM TELEMETRY**: Showing observed telemetry records for `{selected_machine}`.")

    if summary.get("has_mixed_provenance"):
        st.caption("ℹ️ Dataset contains a mix of synthetic fixtures and local observations. Machine-specific provenance is displayed above.")

    # High-level metric cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions in Storage", summary.get("total_sessions", 0))
    with col2:
        st.metric("System Changes Recorded", summary.get("total_changes", 0))
    with col3:
        st.metric("Active Machines", len(machines))
    with col4:
        date_range = summary.get("date_range") or {}
        st.metric("Start Window", (date_range.get("start") or "N/A")[:10])

    st.markdown("---")

    # ------------------------------------------------------------------
    # Analytics Tabs
    # ------------------------------------------------------------------
    tab_baseline, tab_anomaly, tab_regression, tab_correlation, tab_changes = st.tabs([
        "📊 Statistical Baselines",
        "🚨 Anomaly Detection",
        "📉 Sustained Regressions",
        "🔗 Change Correlation",
        "🔄 System Changes Log",
    ])

    # ------------------------------------------------------------------
    # Tab 1: Baselines
    # ------------------------------------------------------------------
    with tab_baseline:
        st.subheader("Statistical Baselines per Metric")
        st.caption("Machine-specific robust statistical baselines (Median, MAD, IQR) evaluated strictly in isolation.")

        baselines = client.get_baselines(machine_id=selected_machine)
        if not baselines:
            st.info(f"No baseline data available for machine `{selected_machine}`.")
        else:
            base_df = pd.DataFrame(baselines)
            # Display readiness status badges
            readiness_counts = base_df["readiness"].value_counts().to_dict()
            st.write("**Readiness Overview:**")
            rc_cols = st.columns(len(readiness_counts))
            for col, (status_name, count) in zip(rc_cols, readiness_counts.items()):
                with col:
                    if status_name == "ready":
                        st.success(f"✅ {status_name.upper()}: {count} metric(s)")
                    else:
                        st.warning(f"⚠️ {status_name.upper()}: {count} metric(s)")

            st.dataframe(
                base_df[[
                    "metric",
                    "readiness",
                    "valid_count",
                    "min_observations",
                    "median",
                    "mad",
                    "iqr",
                    "dispersion_scale",
                ]],
                use_container_width=True,
                hide_index=True,
            )

    # ------------------------------------------------------------------
    # Tab 2: Anomalies
    # ------------------------------------------------------------------
    with tab_anomaly:
        st.subheader("Statistical Anomalies (Modified Z-Score)")
        st.caption("Identifies extreme deviations beyond the statistical cutoff without asserting causality.")

        anomalies = client.get_anomalies(machine_id=selected_machine)
        if not anomalies:
            st.info(f"No observations to evaluate for `{selected_machine}`.")
        else:
            anom_df = pd.DataFrame(anomalies)
            flagged = anom_df[anom_df["is_anomaly"]]

            st.write(f"Total sessions evaluated: **{len(anom_df)}** | Anomalies detected: **{len(flagged)}**")

            if flagged.empty:
                st.success("No statistical anomalies detected under current threshold.")
            else:
                st.dataframe(
                    flagged[[
                        "start_time",
                        "metric",
                        "observed_value",
                        "baseline_median",
                        "deviation_score",
                        "threshold",
                        "status",
                        "reason",
                    ]],
                    use_container_width=True,
                    hide_index=True,
                )

    # ------------------------------------------------------------------
    # Tab 3: Sustained Regressions
    # ------------------------------------------------------------------
    with tab_regression:
        st.subheader("Sustained Performance Regressions")
        st.caption("Requires consecutive qualifying observations in timestamp order to rule out transient spikes.")

        regressions = client.get_regressions(
            machine_id=selected_machine,
            threshold=regression_thresh,
            min_consecutive=min_consecutive,
            only_regressions=False,
        )

        if not regressions:
            st.info(f"No regression evaluation records found for `{selected_machine}`.")
        else:
            reg_df = pd.DataFrame(regressions)
            flagged_regs = reg_df[reg_df["is_regression"]]

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.metric("Total Sessions Evaluated", len(reg_df))
            with col_r2:
                st.metric("Sustained Regression Sessions", len(flagged_regs))

            if flagged_regs.empty:
                st.success("✅ No sustained performance regressions detected.")
            else:
                st.error(f"🚨 Sustained regression detected in {len(flagged_regs)} session(s)!")
                st.dataframe(
                    flagged_regs[[
                        "start_time",
                        "end_time",
                        "metric",
                        "observed_value",
                        "baseline_median",
                        "deviation_score",
                        "consecutive_count",
                        "required_consecutive",
                        "reason",
                    ]],
                    use_container_width=True,
                    hide_index=True,
                )

    # ------------------------------------------------------------------
    # Tab 4: Change Correlation
    # ------------------------------------------------------------------
    with tab_correlation:
        st.subheader("Change Correlation (Non-Causal Evidence)")
        st.caption(
            "Identifies system changes occurring within the temporal window around each regression. "
            "Preserves chronological ordering and machine isolation."
        )

        st.info(
            "🛡️ **Non-Causal Scientific Policy**: Temporal proximity does NOT prove causation. "
            "PARCS documents observed system changes as investigative evidence without asserting that "
            "an update or driver caused the regression."
        )

        correlations = client.get_correlations(
            machine_id=selected_machine,
            window_before_hours=window_before_h,
            window_after_hours=window_after_h,
            only_regressions=True,
        )

        if not correlations:
            st.info(f"No qualifying regressions to correlate for `{selected_machine}`.")
        else:
            corr_df = pd.DataFrame(correlations)
            matched_changes = corr_df[corr_df["is_correlated"]]

            st.write(
                f"Regressions evaluated: **{corr_df['source_row_index'].nunique()}** | "
                f"Matching system changes: **{len(matched_changes)}**"
            )

            st.dataframe(
                corr_df[[
                    "start_time",
                    "metric",
                    "correlation_status",
                    "temporal_relation",
                    "temporal_offset_seconds",
                    "change_type",
                    "change_id",
                    "change_timestamp",
                    "change_description",
                    "reason",
                ]],
                use_container_width=True,
                hide_index=True,
            )

    # ------------------------------------------------------------------
    # Tab 5: System Changes
    # ------------------------------------------------------------------
    with tab_changes:
        st.subheader("System Changes Log")
        st.caption("Drivers, Windows Updates, and Event Logs collected for this machine.")

        changes = client.get_changes(machine_id=selected_machine)
        if not changes:
            st.info(f"No system changes recorded for `{selected_machine}`.")
        else:
            ch_df = pd.DataFrame(changes)
            st.dataframe(
                ch_df[["timestamp", "change_type", "change_id", "description"]],
                use_container_width=True,
                hide_index=True,
            )


if __name__ == "__main__":
    main()
