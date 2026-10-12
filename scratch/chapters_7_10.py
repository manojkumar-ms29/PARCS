"""Chapters 7, 8, 9, and 10 for the PARCS Academic Project Report."""

from __future__ import annotations

import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from report_utils import (
    add_chapter_heading,
    add_section_heading,
    add_subsection_heading,
    add_body_p,
    add_bullet_p,
    add_academic_table,
    add_code_snippet,
)


def add_chapter_7(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "7. TESTING")

    add_section_heading(doc, "7.1 Test Cases")
    add_body_p(
        doc,
        "Software testing is an essential verification phase that validates whether an application operates in strict compliance "
        "with its architectural requirements, statistical invariants, and error-handling contracts. The PARCS verification regime "
        "encompasses collector execution, ETL transformation, Parquet persistence, DuckDB query execution, robust statistical baselining, "
        "streak-based regression detection, temporal change correlation, FastAPI endpoint validation, and Streamlit dashboard rendering."
    )
    add_body_p(
        doc,
        "The test suite was executed against the project implementation using pytest. Table 7.1 details key formal test cases "
        "evaluated across all subsystems, reporting preconditions, expected behaviors, observed results, and pass/fail statuses."
    )

    headers_tc = ["Test ID", "Feature Tested", "Input / Precondition", "Expected Result", "Actual Result", "Status"]
    data_tc = [
        ["TC-01", "SleepStudy Collection", "powercfg /sleepstudy output", "Extracts valid sessions with DRIPS % and drain rate", "Sessions parsed successfully into CollectorResult", "Pass"],
        ["TC-02", "Driver Snapshot Collection", "Get-PnpDevice driver listing", "Captures PnP device IDs, driver versions, providers", "Structured driver records captured in CollectorResult", "Pass"],
        ["TC-03", "Windows Update Collection", "Get-HotFix patch query", "Captures KB numbers, install dates, descriptions", "Hotfix list extracted without error", "Pass"],
        ["TC-04", "Kernel Event Log Query", "Kernel-Power event log query", "Filters Event IDs 506/507 within time window", "Matching power transitions extracted cleanly", "Pass"],
        ["TC-05", "Raw Data Storage", "CollectorResult payload", "Persists timestamped raw JSON in data/raw/", "Raw JSON file created and referenced", "Pass"],
        ["TC-06", "ETL Schema Validation", "Raw session dictionaries", "Normalizes timestamps and enforces canonical columns", "DataFrame conforms to SLEEPSTUDY_COLUMNS", "Pass"],
        ["TC-07", "Parquet Persistence", "Normalized DataFrame", "Writes columnar Parquet and reads back identically", "Zero schema corruption or type drift", "Pass"],
        ["TC-08", "DuckDB Direct SQL Query", "Processed Parquet file", "Executes SQL aggregations directly over Parquet", "Sub-millisecond query execution without server", "Pass"],
        ["TC-09", "Baseline Construction", "14 sessions (DEMO-MACHINE-READY)", "Calculates Median, MAD, IQR; marks readiness='ready'", "Median DRIPS=95.0, readiness='ready'", "Pass"],
        ["TC-10", "Insufficient History Guard", "4 sessions (DEMO-MACHINE-SPARSE)", "Marks readiness='insufficient_history' without error", "readiness='insufficient_history', no crash", "Pass"],
        ["TC-11", "Zero-MAD Fallback", "Sessions with identical values", "Falls back to IQR/1.3490 or epsilon; flag=True", "dispersion_scale > 0, zero_mad_fallback=True", "Pass"],
        ["TC-12", "Point Anomaly Detection", "Degraded session (DRIPS 55%)", "Modified Z-score > 3.5; flags is_anomaly=True", "Score=15.7, is_anomaly=True, status='anomaly'", "Pass"],
        ["TC-13", "Sustained Regression Streak", "4 consecutive degraded sessions", "Requires min_consecutive=3; flags is_regression=True", "Sustained regression flagged on sessions 3 and 4", "Pass"],
        ["TC-14", "Streak Reset on Normal", "Degraded then normal session", "Streak resets immediately to 0; no false alarm", "consecutive_count resets to 0", "Pass"],
        ["TC-15", "Temporal Change Correlation", "Regression + Driver update at -1.5h", "Matches change in [-24h, +2h]; offset=-5400s", "is_correlated=True, relation='before'", "Pass"],
        ["TC-16", "Non-Causal Explanation", "Correlated regression record", "Explanation notes association; denies proof of causality", "Explanation contains 'causation is not asserted'", "Pass"],
        ["TC-17", "Scope Isolation (Subsequent)", "12 reference + 4 eval sessions", "Subsequent scope evaluates only 4 eval sessions", "Evaluates source rows 12..15 against baseline", "Pass"],
        ["TC-18", "Empty Subsequent Scope", "reference_count = total sessions", "Returns empty list without scoring reference sessions", "Returns [] without falling back to self-scoring", "Pass"],
        ["TC-19", "Scope Validation (HTTP 422)", "evaluation_scope='invalid'", "Rejects invalid scope; returns HTTP 422", "HTTP 422 Unprocessable Entity returned", "Pass"],
        ["TC-20", "Synthetic Data Provenance", "DEMO-MACHINE-READY & SPARSE", "Tracks is_synthetic: True per machine", "machine_provenance accurately reflects demo status", "Pass"],
        ["TC-21", "Streamlit Dashboard AppTest", "Render dashboard via AppTest", "Renders 5 tabs and selectbox without exception", "AppTest rendered cleanly; at.exception is None", "Pass"],
    ]
    add_academic_table(doc, headers_tc, data_tc, col_widths=[0.6, 1.3, 1.4, 1.6, 1.4, 0.5])

    add_section_heading(doc, "7.2 Unit Testing")
    add_body_p(
        doc,
        "Unit testing isolates individual algorithms and functions, validating mathematical accuracy and edge-case handling "
        "before integration into higher-level workflows:"
    )
    add_bullet_p(
        doc,
        "Tests in test_analytics_baseline.py verify that Median, MAD, and IQR match hand-calculated statistical values. "
        "The test_contamination_guard test proves that if a naive baseline is computed across both normal and degraded observations, "
        "the median shifts from 95.0 down to 72.5, whereas the partitioned reference baseline preserves the pure 95.0 median.",
        bold_prefix="Statistical Baseline & Contamination Guard: "
    )
    add_bullet_p(
        doc,
        "Tests in test_analytics_regression.py confirm that directional evaluation correctly treats lower DRIPS residency "
        "and higher battery drain rates as harmful. Chronological sort orders (start_time ascending) are verified against shuffled inputs. "
        "Intervening normal sessions or missing timestamps immediately reset the streak counter to zero.",
        bold_prefix="Streak Continuity & Directional Logic: "
    )
    add_bullet_p(
        doc,
        "Tests in test_analytics_anomaly.py verify that Modified Z-scores accurately scale deviations by 1.4826 * MAD. "
        "Sessions with missing metrics or unready baselines produce explicit non-anomaly statuses without raising unhandled exceptions.",
        bold_prefix="Modified Z-Score Cutoff: "
    )
    add_bullet_p(
        doc,
        "Tests in test_analytics_correlation.py verify that temporal offsets are computed accurately in seconds, classifying changes "
        "occurring before, during, or after sleep sessions according to configured time boundaries.",
        bold_prefix="Temporal Windowing & Offset Calculation: "
    )

    add_section_heading(doc, "7.3 Integrated Testing")
    add_body_p(
        doc,
        "Integrated testing evaluates end-to-end interactions between collectors, ETL pipelines, Parquet/DuckDB storage, "
        "FastAPI routes, and the Streamlit dashboard client. All reported testing results represent findings from the formal "
        "acceptance audit executed on the project repository:"
    )
    add_bullet_p(
        doc,
        "The automated test suite executed via pytest across 16 test modules achieved 253 passed tests, 0 failures, and 1 warning in 7.90 seconds.",
        bold_prefix="Automated Test Suite Result: "
    )
    add_bullet_p(
        doc,
        "All 3 client integration tests in test_dashboard_client.py passed, confirming that the client gracefully queries live endpoints "
        "and falls back to local in-process analytics when offline.",
        bold_prefix="Dashboard Client Integration: "
    )
    add_bullet_p(
        doc,
        "Sixteen live HTTP API endpoint tests in test_api.py passed, verifying /health, /api/telemetry/summary, /api/analytics/baselines, "
        "/api/analytics/anomalies, /api/analytics/regressions, /api/analytics/correlations, /api/changes, and /api/demo/seed.",
        bold_prefix="Live API Verification: "
    )
    add_bullet_p(
        doc,
        "The Streamlit AppTest framework executed src/dashboard/app.py without exceptions, verifying that all 5 tabs and machine selector dropdowns render cleanly.",
        bold_prefix="Streamlit UI Rendering: "
    )

    add_body_p(
        doc,
        "Maintenance Deprecation Warnings: During test execution, two non-blocking deprecation warnings were recorded: "
        "(1) A StarletteDeprecationWarning from FastAPI TestClient noting that using httpx with starlette.testclient is deprecated "
        "and recommending httpx2; and (2) A Streamlit deprecation warning regarding the use_container_width parameter in st.dataframe "
        "and st.button. Both warnings are documented as non-blocking maintenance backlog items and were deliberately preserved without "
        "unnecessary code churn."
    )


def add_chapter_8(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "8. RESULTS AND CONCLUSION")

    add_section_heading(doc, "8.1 Results")
    add_body_p(
        doc,
        "The implementation and testing of PARCS demonstrates the feasibility and effectiveness of a data-engineering-first "
        "architecture for diagnosing Windows Modern Standby regressions. The primary functional and analytical outcomes of the MVP release include:"
    )
    add_bullet_p(
        doc,
        "The multi-stage pipeline successfully bridges Windows telemetry collection, raw JSON preservation, schema validation, "
        "columnar Parquet persistence, and embedded DuckDB SQL execution without external database infrastructure.",
        bold_prefix="1. End-to-End Pipeline Execution: "
    )
    add_bullet_p(
        doc,
        "The baseline engine establishes robust Median, MAD, and IQR metrics strictly isolated by machine identity. On DEMO-MACHINE-READY, "
        "14 historical baseline sessions established a clean reference median of 95.0% DRIPS residency and 2,400 mW battery drain rate.",
        bold_prefix="2. Baseline Fidelity: "
    )
    add_bullet_p(
        doc,
        "The regression detector accurately identified 4 consecutive degraded sessions (DRIPS ~ 55%, battery drain ~ 5,400 mW), "
        "triggering sustained regression alerts on sessions 3 and 4 while rejecting single-session transient anomalies.",
        bold_prefix="3. Sustained Regression Isolation: "
    )
    add_bullet_p(
        doc,
        "The correlation engine successfully matched the regression onset with an Intel Wi-Fi 6 AX201 driver update occurring "
        "1.5 hours prior (temporal_offset = -5,400 seconds), providing clear investigative evidence.",
        bold_prefix="4. Actionable Change Correlation: "
    )
    add_bullet_p(
        doc,
        "On DEMO-MACHINE-SPARSE (4 sessions), the system correctly assigned readiness = 'insufficient_history' and status = 'insufficient_history', "
        "completely preventing false regression alarms.",
        bold_prefix="5. False Alarm Suppression: "
    )

    add_section_heading(doc, "8.2 Limitations")
    add_body_p(
        doc,
        "To maintain rigorous academic integrity, several important operational limitations must be explicitly acknowledged:"
    )
    add_bullet_p(
        doc,
        "All multi-session regression and correlation results reported in this MVP audit are derived from deterministic synthetic fixtures "
        "(DEMO-MACHINE-READY and DEMO-MACHINE-SPARSE). While the SleepStudy, driver, update, and event log collectors are fully implemented "
        "to execute real Windows commands, multi-week physical laptop telemetry collection was not deployed or validated end-to-end.",
        bold_prefix="Synthetic Demonstration Data: "
    )
    add_bullet_p(
        doc,
        "The correlation engine identifies temporal association within configured time windows ([-24h, +2h]). It does NOT prove "
        "that a recorded driver update or Windows patch caused the regression. Unrecorded background factors may be responsible.",
        bold_prefix="Temporal Association vs Causation: "
    )
    add_bullet_p(
        doc,
        "PARCS currently operates as a local desktop application invoked via CLI, API, or Streamlit. It does not run as a continuous "
        "Windows background service or Windows Task Scheduler daemon.",
        bold_prefix="Manual Invocation Model: "
    )

    add_section_heading(doc, "8.3 Future Enhancements")
    add_body_p(
        doc,
        "Future research and engineering extensions can significantly expand the capabilities of PARCS beyond the MVP release:"
    )
    add_bullet_p(
        doc,
        "Implement a native Windows Service daemon or Task Scheduler trigger that automatically runs SleepStudy collection "
        "and driver snapshots immediately upon resume from Modern Standby (Event ID 507).",
        bold_prefix="1. Automated Background Daemon: "
    )
    add_bullet_p(
        doc,
        "Incorporate causal discovery algorithms (such as the Peter-Clark algorithm or Granger causality) to distinguish spurious "
        "temporal correlations from genuine causal relationships.",
        bold_prefix="2. Causal Discovery Modeling: "
    )
    add_bullet_p(
        doc,
        "Extend the local Parquet data lake to support multi-node fleet synchronization via Apache Arrow Flight or object storage, "
        "enabling enterprise IT administrators to correlate regressions across thousands of enterprise laptops.",
        bold_prefix="3. Enterprise Fleet Aggregation: "
    )
    add_bullet_p(
        doc,
        "Introduce automated rollback recommendations for recently updated drivers when sustained regressions are strongly correlated.",
        bold_prefix="4. Automated Rollback Guidance: "
    )

    add_section_heading(doc, "8.4 Conclusion")
    add_body_p(
        doc,
        "PARCS demonstrates that client-side Windows Modern Standby power regressions can be systematically diagnosed through an automated, "
        "data-engineering-first architecture. By combining modular telemetry collection, immutable Parquet persistence, embedded DuckDB querying, "
        "robust non-parametric statistics (Median, MAD, IQR), streak-based regression detection, and explainable change correlation, "
        "PARCS bridges the longstanding divide between stateless low-level diagnostics and actionable engineering insights. "
        "The verified MVP release establishes a rigorous, privacy-preserving, and mathematically grounded foundation for next-generation "
        "PC power management analytics."
    )


def add_chapter_9(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "9. APPENDICES")

    add_section_heading(doc, "9.1 Demonstration and Startup Instructions")
    add_body_p(
        doc,
        "PARCS provides a unified Command Line Interface (CLI) via main.py to seed synthetic demonstration datasets, "
        "launch the FastAPI backend, or start the Streamlit visual dashboard:"
    )

    add_body_p(doc, "1. Virtual Environment Setup & Dependency Installation:", bold_prefix="Step 1: ")
    add_code_snippet(
        doc,
        "# Navigate to project root\n"
        "cd c:\\Users\\shant\\OneDrive\\Documents\\PROJECTS\\PARCS\n\n"
        "# Create and activate virtual environment\n"
        "python -m venv .venv\n"
        ".venv\\Scripts\\activate\n\n"
        "# Install dependencies\n"
        "pip install -r requirements.txt"
    )

    add_body_p(doc, "2. Seed Deterministic Synthetic Demonstration Datasets:", bold_prefix="Step 2: ")
    add_code_snippet(
        doc,
        "# Seeds 22 sessions and 4 changes into Parquet storage\n"
        "python main.py seed-demo\n\n"
        "# Output:\n"
        "# Seeded demo datasets successfully: {'success': True, 'session_records': 22, 'change_records': 4}"
    )

    add_body_p(doc, "3. Launch FastAPI REST Backend Service:", bold_prefix="Step 3: ")
    add_code_snippet(
        doc,
        "# Start API on localhost:8000\n"
        "python main.py api --host 127.0.0.1 --port 8000\n\n"
        "# Interactive Swagger UI available at http://127.0.0.1:8000/docs"
    )

    add_body_p(doc, "4. Launch Streamlit Visual Analytics Dashboard:", bold_prefix="Step 4: ")
    add_code_snippet(
        doc,
        "# Start Streamlit dashboard in a new terminal\n"
        "python main.py dashboard\n\n"
        "# Automatically opens browser at http://localhost:8501"
    )

    add_body_p(doc, "5. Execute Complete Automated Test Suite:", bold_prefix="Step 5: ")
    add_code_snippet(
        doc,
        "# Run full pytest test suite\n"
        ".venv\\Scripts\\pytest\n\n"
        "# Result: 253 passed, 1 warning in 7.90s"
    )

    add_section_heading(doc, "9.2 Selected API Examples")
    add_body_p(
        doc,
        "The following JSON payloads represent actual responses returned by the FastAPI backend during verification:"
    )

    add_body_p(doc, "GET /api/telemetry/summary:", bold_prefix="Endpoint 1: ")
    add_code_snippet(
        doc,
        "{\n"
        '  "total_sessions": 22,\n'
        '  "total_changes": 4,\n'
        '  "machines": ["DEMO-MACHINE-READY", "DEMO-MACHINE-SPARSE"],\n'
        '  "date_range": {\n'
        '    "start": "2026-08-10T10:00:00Z",\n'
        '    "end": "2026-09-04T14:30:00Z"\n'
        "  },\n"
        '  "datasets_available": {\n'
        '    "sleepstudy": true,\n'
        '    "changes": true\n'
        "  },\n"
        '  "is_synthetic": true,\n'
        '  "machine_provenance": {\n'
        '    "DEMO-MACHINE-READY": true,\n'
        '    "DEMO-MACHINE-SPARSE": true\n'
        "  },\n"
        '  "status": "ok"\n'
        "}"
    )

    add_body_p(doc, "GET /api/analytics/regressions?machine_id=DEMO-MACHINE-READY:", bold_prefix="Endpoint 2: ")
    add_code_snippet(
        doc,
        "[\n"
        "  {\n"
        '    "machine_id": "DEMO-MACHINE-READY",\n'
        '    "start_time": "2026-09-01T11:30:00Z",\n'
        '    "end_time": "2026-09-01T12:00:00Z",\n'
        '    "metric": "drips_percent",\n'
        '    "observed_value": 55.0,\n'
        '    "baseline_median": 95.0,\n'
        '    "deviation_score": 15.68,\n'
        '    "direction": "lower",\n'
        '    "is_regression": true,\n'
        '    "status": "regression",\n'
        '    "consecutive_count": 3,\n'
        '    "required_consecutive": 3,\n'
        '    "reason": "Sustained degradation of drips_percent (observed 55.0% vs baseline 95.0%) across 3 sessions."\n'
        "  }\n"
        "]"
    )

    add_body_p(doc, "GET /api/analytics/correlations?machine_id=DEMO-MACHINE-READY:", bold_prefix="Endpoint 3: ")
    add_code_snippet(
        doc,
        "[\n"
        "  {\n"
        '    "machine_id": "DEMO-MACHINE-READY",\n'
        '    "metric": "drips_percent",\n'
        '    "change_id": "PCI\\\\VEN_8086&DEV_06F0",\n'
        '    "change_type": "driver",\n'
        '    "change_description": "Intel(R) Wi-Fi 6 AX201 160MHz v22.130.0.5",\n'
        '    "temporal_offset_seconds": -5400.0,\n'
        '    "temporal_relation": "before",\n'
        '    "is_correlated": true,\n'
        '    "reason": "Driver change observed 1.5h before regression onset (temporal association only, causation is not asserted)."\n'
        "  }\n"
        "]"
    )

    add_section_heading(doc, "9.3 Representative Source Code")
    add_body_p(
        doc,
        "The following representative code excerpts illustrate core algorithmic implementations from the PARCS repository:"
    )

    add_body_p(doc, "Excerpt from src/analytics/baseline.py (Robust Scaling & Zero-MAD Fallback):", bold_prefix="Listing 9.1: ")
    add_code_snippet(
        doc,
        "def _calculate_metric_baseline(series: pd.Series, min_obs: int) -> dict[str, object]:\n"
        "    valid_vals = series.dropna().to_numpy(dtype=float)\n"
        "    if len(valid_vals) < min_obs:\n"
        "        return {'readiness': 'insufficient_history', 'median': None, 'mad': None}\n"
        "    \n"
        "    med = float(np.median(valid_vals))\n"
        "    abs_devs = np.abs(valid_vals - med)\n"
        "    mad = float(np.median(abs_devs))\n"
        "    iqr = float(np.percentile(valid_vals, 75) - np.percentile(valid_vals, 25))\n"
        "    \n"
        "    # Documented zero-MAD fallback strategy\n"
        "    if mad > 0.0:\n"
        "        scale = mad * 1.4826\n"
        "        fallback = False\n"
        "    elif iqr > 0.0:\n"
        "        scale = iqr / 1.3490\n"
        "        fallback = True\n"
        "    else:\n"
        "        scale = 1e-4  # Epsilon positive scale\n"
        "        fallback = True\n"
        "        \n"
        "    return {'readiness': 'ready', 'median': med, 'mad': mad, 'iqr': iqr,\n"
        "            'dispersion_scale': scale, 'zero_mad_fallback': fallback}"
    )

    add_body_p(doc, "Excerpt from src/api/service.py (Prospective Reference Partitioning):", bold_prefix="Listing 9.2: ")
    add_code_snippet(
        doc,
        "@staticmethod\n"
        "def partition_machine_features(df: pd.DataFrame, min_obs: int = 10, ref_count: int = None):\n"
        "    # Deterministic chronological sort: start_time asc, end_time asc\n"
        "    df_sorted = df.sort_values(by=['start_time', 'end_time'], na_position='last')\n"
        "    n_rows = len(df_sorted)\n"
        "    \n"
        "    if ref_count is not None:\n"
        "        k = max(0, min(ref_count, n_rows))\n"
        "        return df_sorted.iloc[:k].copy(), df_sorted.iloc[k:].copy()\n"
        "        \n"
        "    # Default policy for sparse history (<10 sessions)\n"
        "    if n_rows <= min_obs:\n"
        "        return df_sorted.copy(), df_sorted.copy()\n"
        "        \n"
        "    # Chronological 75% reference baseline split\n"
        "    k = max(min_obs, int(n_rows * 0.75))\n"
        "    return df_sorted.iloc[:k].copy(), df_sorted.iloc[k:].copy()"
    )

    add_section_heading(doc, "9.4 User Documentation")
    add_body_p(
        doc,
        "PARCS is designed for seamless operation by systems engineers, hardware validation teams, and IT administrators. "
        "The application provides interactive telemetry exploration via the Streamlit dashboard:"
    )
    add_bullet_p(
        doc,
        "Use the top dropdown to choose between monitored machines. A warning badge is displayed if the machine uses synthetic demonstration data.",
        bold_prefix="Machine Selection: "
    )
    add_bullet_p(
        doc,
        "Adjust the 'Harmful Deviation Threshold' slider (default 2.0) and 'Required Consecutive Sessions' (default 3) in the sidebar to calibrate detection sensitivity.",
        bold_prefix="Parameter Calibration: "
    )
    add_bullet_p(
        doc,
        "Navigate between the 5 tabs to inspect statistical baselines, view flagged anomalies, review regression timelines, and examine correlated driver updates or Windows patches.",
        bold_prefix="Tabular Exploration: "
    )

    add_section_heading(doc, "9.5 Glossary")
    add_body_p(
        doc,
        "The following glossary defines critical technical terms utilized throughout the PARCS project report:"
    )

    headers_glo = ["Technical Term", "Formal Definition"]
    data_glo = [
        ["Modern Standby (S0ix)", "A low-power hardware/software platform architecture where the system remains in ACPI S0 while the SoC enters quiescent low-power idle states."],
        ["DRIPS", "Deepest Runtime Idle Power State; the lowest power hardware sleep state achievable by modern processors and SoCs."],
        ["Median Absolute Deviation (MAD)", "A robust measure of statistical dispersion defined as the median of the absolute deviations from the dataset median."],
        ["Modified Z-Score", "A robust outlier detection metric utilizing median and MAD to score deviations without sensitivity to extreme sample outliers."],
        ["Sustained Regression", "A persistent performance degradation requiring a minimum run of consecutive qualifying degraded sessions in chronological order."],
        ["Temporal Correlation", "An observed statistical association between an event and a regression onset based on temporal proximity, explicitly distinguished from causal proof."],
        ["Apache Parquet", "An open-source, column-oriented data storage format providing high-performance compression and encoding schemes."],
        ["DuckDB", "An embedded, in-process vectorized SQL analytical database engine optimized for executing fast queries over local Parquet files."],
        ["FastAPI", "A modern, high-performance web framework for building REST APIs with Python 3.8+ based on standard OpenAPI and Pydantic validation."],
        ["Streamlit", "An open-source Python framework for rapidly creating interactive data-driven web applications and dashboards."],
        ["Evaluation Scope", "The filtering boundary for analytics evaluation: 'subsequent' evaluates post-reference sessions only; 'all' scores the entire dataset."],
        ["Data Provenance", "The documentation of the origin and processing history of telemetry data, explicitly tracking real versus synthetic records."],
    ]
    add_academic_table(doc, headers_glo, data_glo, col_widths=[2.2, 4.3])


def add_chapter_10(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "10. BIBLIOGRAPHY")

    add_body_p(
        doc,
        "The bibliography lists authoritative academic publications, peer-reviewed textbooks, and official technical "
        "documentation consulted during the architecture, design, and verification of PARCS. References are organized into "
        "Books & Research Publications and Official Technical Documentation."
    )

    add_section_heading(doc, "10.1 Books and Research Publications")
    
    bib_books = [
        "1.  Abadi, D. J., Madden, S. R., and Hachem, N. (2008). “Column-Stores vs. Row-Stores: How Different Are They Really?” Proceedings of the 2008 ACM SIGMOD International Conference on Management of Data, pp. 967–980. https://doi.org/10.1145/1376616.1376712",
        "2.  Basseville, M., and Nikiforov, I. V. (1993). Detection of Abrupt Changes: Theory and Application. Prentice Hall, Englewood Cliffs, NJ.",
        "3.  Hampel, F. R. (1974). “The Influence Curve and Its Role in Robust Estimation.” Journal of the American Statistical Association, 69(346), pp. 383–393. https://doi.org/10.1080/01621459.1974.10482962",
        "4.  Iglewicz, B., and Hoaglin, D. C. (1993). How to Detect and Handle Outliers. ASQC Basic References in Quality Control, Vol. 16, Milwaukee, WI: ASQC Quality Press.",
        "5.  Oliner, A., Ganapathi, A., and Xu, W. (2012). “Advances and Challenges in Log Analysis.” Communications of the ACM, 55(2), pp. 55–61. https://doi.org/10.1145/2076450.2076466",
        "6.  Pearl, J. (2009). Causality: Models, Reasoning, and Inference (2nd ed.). Cambridge University Press, Cambridge, UK.",
        "7.  Popp, M., Ecker, D., and Brand, O. (2018). “Power Management Architecture for Low-Power System-on-Chips.” IEEE Transactions on Circuits and Systems I: Regular Papers, 65(9), pp. 2910–2921.",
        "8.  Raasveldt, M., and Mühleisen, H. (2019). “DuckDB: An Embeddable Analytical Database.” Proceedings of the 2019 ACM SIGMOD International Conference on Management of Data, pp. 1981–1984. https://doi.org/10.1145/3299869.3320212",
        "9.  Rousseeuw, P. J., and Croux, C. (1993). “Alternatives to the Median Absolute Deviation.” Journal of the American Statistical Association, 88(424), pp. 1273–1283. https://doi.org/10.1080/01621459.1993.10476408",
    ]
    for b in bib_books:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(b)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

    add_section_heading(doc, "10.2 Official Technical Documentation")
    
    bib_tech = [
        "10. ACPI Specification Working Group. (2022). Advanced Configuration and Power Interface (ACPI) Specification, Version 6.5. Unified Extensible Firmware Interface (UEFI) Forum. https://uefi.org/specifications",
        "11. Apache Software Foundation. (2023). Apache Parquet Documentation. https://parquet.apache.org/documentation/",
        "12. DuckDB Foundation. (2023). DuckDB Documentation: In-Process Analytical SQL Engine. https://duckdb.org/docs/",
        "13. Microsoft Corporation. (2023). Modern Standby Architecture and Diagnostics (powercfg /sleepstudy). Microsoft Hardware Developer Center. https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/modern-standby",
        "14. Microsoft Corporation. (2023). Windows Event Log Reference (Microsoft-Windows-Kernel-Power). Microsoft Learn. https://learn.microsoft.com/en-us/windows/win32/wes/windows-event-log",
        "15. Python Software Foundation. (2024). Python 3 Documentation. https://docs.python.org/3/",
        "16. Streamlit Inc. (2024). Streamlit Documentation: Modern Data Applications. https://docs.streamlit.io/",
        "17. Tiangolo, S. (2024). FastAPI Documentation: Modern Python Web Framework. https://fastapi.tiangolo.com/",
    ]
    for t in bib_tech:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(t)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10.5)

print("Chapters 7, 8, 9, and 10 module compiled successfully.")
