"""Chapters 2, 3, and 4 for the PARCS Academic Project Report."""

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
)


def add_chapter_2(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "2. LITERATURE STUDY")

    add_section_heading(doc, "2.1 Introduction")
    add_body_p(
        doc,
        "A rigorous literature study establishes the theoretical foundations, algorithmic paradigms, "
        "and architectural patterns relevant to the problem of diagnosing Windows Modern Standby power "
        "regressions. In systems engineering, performance degradation during quiescent sleep states cannot "
        "be addressed purely through intuitive heuristic checks; it requires understanding low-power hardware "
        "states, statistical process control, robust anomaly detection in noisy telemetry, time-series regression "
        "isolation, and non-causal event correlation. Furthermore, storing and querying longitudinal endpoint "
        "telemetry necessitates an analysis of modern columnar analytical file formats and embedded in-process SQL "
        "engines. This chapter surveys peer-reviewed literature and authoritative technical frameworks across "
        "these domains, analyzes existing diagnostic approaches, and identifies the core research gap that PARCS addresses."
    )

    add_section_heading(doc, "2.2 Review of Relevant Research and Technical Concepts")

    add_subsection_heading(doc, "2.2.1 ACPI Power States and Windows Modern Standby Architecture")
    add_body_p(
        doc,
        "The Advanced Configuration and Power Interface (ACPI) Specification (ACPI Specification Working Group, 2022) "
        "defines the global system power states (G-states), sleep states (S-states), and device power states (D-states). "
        "Historically, laptops relied on ACPI S3 (Suspend-to-RAM) to achieve quiescent low power. In S3, the CPU and system "
        "clocks are disabled, and volatile memory context is refreshed in self-refresh mode. Modern computing platforms, "
        "however, increasingly adopt ACPI S0 Low Power Idle (S0ix), branded on Microsoft Windows as Modern Standby or "
        "Connected Standby (Microsoft Hardware Developer Center, 2023)."
    )
    add_body_p(
        doc,
        "In Modern Standby, the platform remains within ACPI S0. Low power is achieved opportunistically when the operating "
        "system directs all platform components and peripherals into low-power device states (D3hot/D3cold), permitting the SoC "
        "power management controller to transition into Deepest Runtime Idle Power State (DRIPS). Popp et al. (2018) analyzed "
        "SoC power state transitions in mobile architectures, observing that achieving target battery longevity requires "
        "sustained DRIPS residency of at least 95% of total sleep time. When a single platform component—such as a PCIe Wi-Fi "
        "transceiver, audio codec, or USB host controller—fails to enter D3, the power management controller is blocked from "
        "initiating hardware DRIPS (SW_DRIPS vs HW_DRIPS mismatch). Consequently, the CPU remains trapped in shallow C-states "
        "(C2 or C3), increasing quiescent power consumption by a factor of 10 to 50 times baseline expectations."
    )

    add_subsection_heading(doc, "2.2.2 Robust Statistical Process Monitoring and Dispersion Estimators")
    add_body_p(
        doc,
        "Statistical process monitoring in systems telemetry requires estimating typical baseline behavior in the presence "
        "of noisy, skewed, or contaminated observations. Classical parametric statistics rely on sample mean (mu) and standard "
        "deviation (sigma). However, as established in foundational robust statistics literature (Hampel, 1974; Rousseeuw & Croux, 1993), "
        "mean and standard deviation possess a breakdown point of 0%, meaning that a single extreme outlier (such as an overnight "
        "Windows Update maintenance session) can arbitrarily distort the baseline mean and inflate the standard deviation, masking "
        "subsequent degradations (the masking effect) or erroneously flagging normal variations (the swamping effect)."
    )
    add_body_p(
        doc,
        "To achieve robustness against outliers and distributional skewness, modern telemetry frameworks employ estimators "
        "with high breakdown points (up to 50%). The median represents the optimal robust location estimator, while the "
        "Median Absolute Deviation (MAD) serves as the primary dispersion estimator:"
    )
    add_body_p(
        doc,
        "MAD = median(|x_i - median(X)|)",
        bold_prefix="Formulation: "
    )
    add_body_p(
        doc,
        "Under a standard normal distribution, MAD scaled by 1.4826 asymptotically estimates standard deviation. Iglewicz and Hoaglin (1993) "
        "introduced the Modified Z-score (M_i) for outlier detection:"
    )
    add_body_p(
        doc,
        "M_i = 0.6745 * |x_i - median(X)| / MAD",
        bold_prefix="Modified Z-score: "
    )
    add_body_p(
        doc,
        "In practical systems engineering, when identical observations occur repeatedly (such as laptops consistently achieving "
        "exactly 99% DRIPS residency), MAD collapses to zero. A robust baseline implementation must incorporate documented fallback "
        "mechanisms, utilizing the Interquartile Range (IQR / 1.3490) or a minimal positive epsilon, to prevent division-by-zero "
        "singularities while preserving scale sensitivity."
    )

    add_subsection_heading(doc, "2.2.3 Time-Series Anomaly and Sustained Regression Detection")
    add_body_p(
        doc,
        "A critical distinction in systems performance analysis is the difference between point anomalies and sustained regressions. "
        "A point anomaly represents an isolated, single-session deviation from baseline expectation—such as an active user downloading "
        "a game update while the laptop lid is closed. In contrast, a sustained regression represents a permanent or persistent shift "
        "in platform behavior resulting from a structural change in the system (e.g. an incompatible device driver update)."
    )
    add_body_p(
        doc,
        "Basseville and Nikiforov (1993) formalized the detection of abrupt and persistent changes in dynamic time series. "
        "In industrial software reliability, detecting persistent shifts without incurring unacceptable false-positive rates "
        "requires streak-based sequential evaluation: an alert is raised only when a minimum run length (k consecutive sessions) "
        "consistently crosses a directional harmful deviation threshold in chronological order. Furthermore, prospective "
        "evaluation requires that degraded observations must not contaminate the historical reference window used to evaluate them, "
        "a principle known as reference partition isolation."
    )

    add_subsection_heading(doc, "2.2.4 Temporal Event Correlation and Non-Causal Systems Diagnostics")
    add_body_p(
        doc,
        "When a performance regression is detected, engineers must identify the likely environmental factors associated with "
        "the degradation. Oliner et al. (2012) conducted a comprehensive survey of anomalies and event correlation in software "
        "systems, emphasizing that temporal proximity between system events (driver updates, OS hotfixes, service configuration changes) "
        "and regression onset provides the primary investigative clue for root-cause triage."
    )
    add_body_p(
        doc,
        "However, Pearl (2009) established in foundational causal inference literature that temporal association does not equal "
        "causality. An event occurring before a regression (e.g. a routine audio driver update) may be purely coincidental, while "
        "the true unrecorded root cause is an environmental temperature change or background malware. Diagnostic software must "
        "therefore maintain strict epistemological humility: systems must explicitly classify relationships as temporal correlations "
        "within defined time windows ([-W_before, +W_after]), providing evidence for human investigation rather than asserting "
        "unsubstantiated causal claims."
    )

    add_subsection_heading(doc, "2.2.5 Modern Columnar Analytical Storage and In-Process Query Engines")
    add_body_p(
        doc,
        "Telemetry ingestion architectures have evolved away from traditional row-oriented relational databases (RDBMS) toward "
        "columnar storage formats. Abadi et al. (2008) demonstrated that columnar architectures achieve order-of-magnitude performance "
        "improvements for analytical queries involving aggregate computations over selected metric columns. Apache Parquet (Apache Software Foundation, 2023) "
        "has emerged as the open industry standard for columnar persistence, featuring run-length encoding, dictionary compression, "
        "and metadata-driven chunk skipping."
    )
    add_body_p(
        doc,
        "Concurrently, Raasveldt and Mühleisen (2019) introduced DuckDB, an embedded, vectorized analytical database management system. "
        "Unlike SQLite (which is row-oriented and optimized for transactional OLTP workloads) and client-server databases like PostgreSQL "
        "or ClickHouse (which require external daemon management and network socket communication), DuckDB operates directly inside the "
        "host application process. DuckDB executes zero-copy SQL queries against Parquet files directly on the local filesystem, "
        "achieving microsecond query latencies with zero external infrastructure overhead."
    )

    add_section_heading(doc, "2.3 Analysis of Existing Approaches")
    add_body_p(
        doc,
        "To evaluate the technical positioning of PARCS, existing commercial and operating system diagnostic tools were evaluated "
        "across key functional capabilities: longitudinal persistence, machine-specific baselines, sustained regression detection, "
        "event correlation, local-first execution, and zero-server infrastructure."
    )

    headers_comp = ["Diagnostic Tool", "Storage Architecture", "Baseline Strategy", "Regression Model", "Event Correlation", "Zero Server"]
    data_comp = [
        ["powercfg /sleepstudy", "Stateless HTML/XML", "None (Static threshold)", "None (Single-session)", "None (Isolated)", "Yes"],
        ["Windows Perf Analyzer", "ETW trace files (.etl)", "None (Manual inspection)", "None (Manual timeline)", "Manual ETW cross-check", "Yes"],
        ["Reliability Monitor", "Local WMI/Registry", "None (Daily score index)", "None (Crash frequency)", "Visual event overlay", "Yes"],
        ["Datadog / Dynatrace", "Cloud SaaS Data Lake", "Parametric (Mean/Std)", "Statistical / ML anomaly", "Automated APM traces", "No (Heavy Cloud)"],
        ["PARCS (Proposed)", "Parquet + DuckDB", "Robust (Median, MAD, IQR)", "Streak-based consecutive", "Temporal window correlation", "Yes (Local First)"],
    ]
    add_academic_table(doc, headers_comp, data_comp, col_widths=[1.5, 1.4, 1.3, 1.3, 1.4, 0.7])

    add_body_p(
        doc,
        "As summarized in the comparison table, native operating system tools provide deep hardware inspection but lack "
        "longitudinal memory and automated correlation. Enterprise APM suites offer longitudinal tracking but require heavyweight "
        "cloud infrastructure, subscription licensing, and proprietary data offloading. PARCS uniquely bridges this divide "
        "by delivering advanced analytical capabilities in a lightweight, local-first architecture."
    )

    add_section_heading(doc, "2.4 Research Gap")
    add_body_p(
        doc,
        "The survey of existing literature and diagnostic tooling reveals a prominent technical gap: there is an acute lack of "
        "an automated, privacy-preserving, zero-infrastructure data engineering pipeline that can continuously monitor Windows "
        "Modern Standby telemetry, construct robust machine-isolated statistical baselines, detect sustained performance regressions, "
        "and temporally correlate degradations with recorded system changes without relying on external database daemons or cloud services. "
        "PARCS is explicitly engineered to address this gap."
    )

    add_section_heading(doc, "2.5 Summary")
    add_body_p(
        doc,
        "This chapter reviewed foundational concepts in ACPI S0ix Modern Standby, robust statistics (Median, MAD, IQR), "
        "Modified Z-scores, change point detection, non-causal event correlation, and columnar analytics with Parquet and DuckDB. "
        "These technical foundations establish the theoretical framework implemented in PARCS, detailed in subsequent chapters."
    )


def add_chapter_3(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "3. SOFTWARE REQUIREMENT ANALYSIS")

    add_section_heading(doc, "3.1 Hardware Specification")
    add_body_p(
        doc,
        "Hardware requirements define the minimum and recommended physical computing resources necessary to execute the "
        "PARCS telemetry collection, ETL pipeline, DuckDB analytical engine, FastAPI REST backend, and Streamlit user interface. "
        "Because PARCS operates entirely in-process using embedded columnar storage, its hardware footprint is exceptionally lightweight."
    )

    headers_hw = ["Hardware Component", "Minimum Requirement", "Recommended Specification", "Evaluation Platform Role"]
    data_hw = [
        ["Processor (CPU)", "x86-64 Dual-Core (1.8 GHz)", "Intel Core i5 / AMD Ryzen 5 Quad-Core+", "Host telemetry generation & DuckDB execution"],
        ["System Memory (RAM)", "4 GB DDR4", "8 GB to 16 GB DDR4/DDR5", "In-memory pandas/DuckDB vectorized execution"],
        ["Storage Space", "200 MB free disk space", "1 GB NVMe SSD space", "Raw JSON reports & processed Parquet datasets"],
        ["Display Resolution", "1280 x 720 (HD)", "1920 x 1080 (Full HD) or higher", "Streamlit responsive dashboard rendering"],
        ["Power Management", "ACPI S0 Low Power Idle support", "Windows Modern Standby certified hardware", "SleepStudy telemetry generation on Windows"],
    ]
    add_academic_table(doc, headers_hw, data_hw, col_widths=[1.5, 1.5, 1.7, 1.8])

    add_section_heading(doc, "3.2 Software Specification")
    add_body_p(
        doc,
        "The software specification enumerates the programming languages, runtime environments, core libraries, web frameworks, "
        "and testing suites utilized in the implementation of PARCS, confirmed directly from the repository's requirements.txt."
    )

    headers_sw = ["Software Component", "Version Specification", "Functional Role in PARCS Architecture"]
    data_sw = [
        ["Operating System", "Windows 10 / 11 (64-bit)", "Host environment for powercfg, PnP device enumeration, and event logs"],
        ["Python Runtime", "Python 3.10 to 3.14 (Tested on 3.14.5)", "Core programming language for collectors, ETL, analytics, and API"],
        ["DuckDB", "duckdb >= 0.9.0", "Embedded in-process SQL analytical query engine over Parquet tables"],
        ["Apache Arrow / PyArrow", "pyarrow >= 14.0.0", "Columnar memory layout and high-performance Parquet reading/writing"],
        ["Pandas", "pandas >= 2.0.0", "Tabular data manipulation, time-series indexing, and feature engineering"],
        ["FastAPI", "fastapi >= 0.100.0", "Asynchronous REST API framework exposing analytical endpoints"],
        ["Uvicorn", "uvicorn >= 0.20.0", "ASGI web server implementation for FastAPI backend hosting"],
        ["Streamlit", "streamlit >= 1.30.0", "Interactive data visualization dashboard and telemetry exploration UI"],
        ["HTTPX", "httpx >= 0.25.0", "Asynchronous and synchronous HTTP client for dashboard API communication"],
        ["Pydantic", "pydantic >= 2.0.0", "Data validation and settings management using Python type annotations"],
        ["pytest", "pytest >= 7.0.0", "Automated test runner executing unit and integration verification suites"],
    ]
    add_academic_table(doc, headers_sw, data_sw, col_widths=[1.6, 1.8, 3.1])

    add_section_heading(doc, "3.3 About the Software and Its Features")
    add_body_p(
        doc,
        "PARCS is implemented in modern Python, leveraging an optimal data-engineering stack designed for high throughput, "
        "low memory consumption, and zero external daemon management:"
    )
    add_bullet_p(
        doc,
        "Python 3.14 provides a highly optimized runtime with modern type annotation support and robust system automation capabilities, "
        "allowing seamless interaction with Windows command-line utilities and system APIs.",
        bold_prefix="Python Runtime: "
    )
    add_bullet_p(
        doc,
        "Apache Parquet delivers efficient columnar compression, schema enforcement, and rapid selective scans. Telemetry data is "
        "partitioned immutably, ensuring long-term longitudinal persistence without database table bloat.",
        bold_prefix="Apache Parquet: "
    )
    add_bullet_p(
        doc,
        "DuckDB provides vectorized analytical SQL execution directly against Parquet files. Because DuckDB is embedded as a Python library, "
        "PARCS requires no background database service, socket configuration, or database administrative credentials.",
        bold_prefix="Embedded DuckDB: "
    )
    add_bullet_p(
        doc,
        "FastAPI provides OpenAPI-compliant, type-safe REST endpoints with automatic Pydantic schema validation. Query parameters "
        "such as threshold cutoffs, observation counts, and evaluation scopes are validated automatically, rejecting malformed requests "
        "with HTTP 422.",
        bold_prefix="FastAPI: "
    )
    add_bullet_p(
        doc,
        "Streamlit provides a dynamic, responsive web interface that connects directly to the FastAPI backend or falls back seamlessly "
        "to local in-process analytics if the backend service is offline.",
        bold_prefix="Streamlit: "
    )


def add_chapter_4(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "4. SYSTEM ANALYSIS")

    add_section_heading(doc, "4.1 Requirement Specification")
    add_body_p(
        doc,
        "Requirement specification defines the essential functional capabilities and non-functional quality attributes "
        "that govern the design, implementation, and verification of PARCS."
    )

    add_subsection_heading(doc, "4.1.1 Functional Requirements")
    add_body_p(doc, "The functional requirements define the explicit operations performed by PARCS:")
    
    fr_items = [
        ("FR-01 (SleepStudy Collection): ", "The system shall execute Windows powercfg /sleepstudy via subprocess, extract structured standby sessions (start/end timestamps, duration, DRIPS %, battery drain %, drain rate mW), and preserve the raw HTML/XML report."),
        ("FR-02 (Driver Telemetry): ", "The system shall capture timestamped snapshots of installed Plug-and-Play device drivers, preserving device IDs, driver names, versions, providers, and status."),
        ("FR-03 (Update Telemetry): ", "The system shall query Windows Update history, capturing hotfix identifiers (KB numbers), descriptions, and installation timestamps."),
        ("FR-04 (Event Log Telemetry): ", "The system shall extract Microsoft-Windows-Kernel-Power events within configurable time windows around sleep sessions."),
        ("FR-05 (Raw Data Preservation): ", "The system shall store raw collector outputs in timestamped JSON/HTML files under data/raw/ before performing any transformation."),
        ("FR-06 (ETL Normalization): ", "The system shall normalize raw session and change data into standardized schemas, validating types and handling missing fields."),
        ("FR-07 (Parquet Persistence): ", "The system shall persist normalized sessions into data/processed/sleepstudy.parquet and system changes into data/processed/changes.parquet."),
        ("FR-08 (DuckDB Analytical Querying): ", "The system shall provide an in-process DuckDB manager capable of executing SQL aggregations directly over Parquet files."),
        ("FR-09 (Machine-Isolated Baselines): ", "The system shall compute Median, MAD, and IQR baselines strictly partitioned by machine_id, marking readiness as 'ready' if observations >= min_observations (default 10) or 'insufficient_history' otherwise."),
        ("FR-10 (Point Anomaly Detection): ", "The system shall compute Modified Z-scores against ready baselines, flagging deviations exceeding the threshold (default 3.5) without asserting causality."),
        ("FR-11 (Sustained Regression Detection): ", "The system shall detect consecutive qualifying directional degradations (default 3 sessions) in chronological order, isolating reference observations from subsequent evaluation."),
        ("FR-12 (Temporal Change Correlation): ", "The system shall identify system changes occurring within configurable temporal windows around regression onset, annotating temporal relations ('before', 'concurrent', 'after')."),
        ("FR-13 (REST API Services): ", "The system shall expose analytics via FastAPI endpoints (/health, /api/telemetry/summary, /api/analytics/baselines, /api/analytics/anomalies, /api/analytics/regressions, /api/analytics/correlations)."),
        ("FR-14 (Visual Dashboard): ", "The system shall deliver a multi-tab Streamlit dashboard providing machine selection, metric overviews, baseline inspections, and regression timelines."),
    ]
    for prefix, desc in fr_items:
        add_bullet_p(doc, desc, bold_prefix=prefix)

    add_subsection_heading(doc, "4.1.2 Non-Functional Requirements")
    add_body_p(doc, "The non-functional requirements define the quality, reliability, and security constraints of the application:")
    
    nfr_items = [
        ("NFR-01 (Machine Isolation): ", "Observations from different machines shall never be combined or permitted to contaminate one another's baselines or evaluations."),
        ("NFR-02 (Prospective Evaluation Purity): ", "Historical reference observations shall be strictly isolated from subsequent evaluation sets to prevent degraded sessions from shifting the baseline used to score themselves."),
        ("NFR-03 (Non-Causal Explainability): ", "All regression and correlation outputs shall state statistical and temporal observations without asserting unverified causal claims."),
        ("NFR-04 (Zero Infrastructure Overhead): ", "The system shall operate without requiring external database servers, background services, cloud dependencies, or administrative network ports."),
        ("NFR-05 (Deterministic Repeatability): ", "All analytical calculations, baseline sort orders, and streak evaluations shall yield identical, deterministic results across repeated executions."),
        ("NFR-06 (Data Provenance Transparency): ", "The system shall explicitly distinguish synthetic demonstration fixtures (is_synthetic: True) from genuine physical system telemetry across all layers."),
    ]
    for prefix, desc in nfr_items:
        add_bullet_p(doc, desc, bold_prefix=prefix)

    add_section_heading(doc, "4.2 Characteristics and Limitations of Existing Approaches")
    add_body_p(
        doc,
        "Existing techniques for Windows Modern Standby diagnostics rely on disconnected manual workflows. An engineer "
        "noticing high battery drain must open an elevated command prompt, run powercfg /sleepstudy, open the resulting "
        "HTML report in a web browser, and manually scroll through dozens of sleep sessions. If a poor session is identified, "
        "the engineer must manually open Device Manager to check recently updated drivers, open Windows Update Settings to inspect "
        "recent hotfixes, and open Windows Event Viewer to inspect Kernel-Power Event ID 506 or 507 entries. This manual triage "
        "process is tedious, highly subjective, and incapable of detecting subtle, gradual performance degradation over time."
    )

    add_section_heading(doc, "4.3 Proposed System")
    add_body_p(
        doc,
        "PARCS replaces manual, disconnected triage with an automated, data-engineering-first telemetry analytics pipeline. "
        "By decoupling collection, normalization, persistence, statistical modeling, and visualization, PARCS establishes "
        "an end-to-end automated workflow:"
    )
    add_bullet_p(
        doc,
        "PARCS unifies SleepStudy, driver snapshots, Windows updates, and event logs into a single structured pipeline.",
        bold_prefix="Unified Multi-Source Telemetry: "
    )
    add_bullet_p(
        doc,
        "Using Apache Parquet and DuckDB, PARCS enables instant historical queries without the operational overhead of a relational database server.",
        bold_prefix="Columnar Data Lake: "
    )
    add_bullet_p(
        doc,
        "Non-parametric Median, MAD, and IQR statistics adapt dynamically to each specific machine's hardware characteristics.",
        bold_prefix="Machine-Specific Robust Baselines: "
    )
    add_bullet_p(
        doc,
        "Requiring consecutive qualifying degradations prevents single-session transient anomalies from triggering false alarms.",
        bold_prefix="Streak-Based Regression Detection: "
    )
    add_bullet_p(
        doc,
        "Automated matching of regression onset with recorded changes eliminates manual cross-referencing while preserving non-causal integrity.",
        bold_prefix="Explainable Temporal Correlation: "
    )

    add_section_heading(doc, "4.4 Software Requirement Specification")
    add_body_p(
        doc,
        "The Software Requirement Specification (SRS) formalizes the operational environment, input specifications, "
        "processing requirements, and expected system outputs for PARCS:"
    )
    add_bullet_p(
        doc,
        "Desktop execution environment running Windows 10/11 with Python 3.10+ and required packages installed in a virtual environment (.venv).",
        bold_prefix="System Environment: "
    )
    add_bullet_p(
        doc,
        "SleepStudy HTML/XML files generated by powercfg, PowerShell driver query JSON structures, Windows Update hotfix lists, and wevtutil event log records.",
        bold_prefix="Input Requirements: "
    )
    add_bullet_p(
        doc,
        "Schema validation, data type normalization, columnar Parquet writing, in-process DuckDB SQL aggregation, robust baseline estimation, streak tracking, and temporal window matching.",
        bold_prefix="Processing Requirements: "
    )
    add_bullet_p(
        doc,
        "Standardized Parquet tables (sleepstudy.parquet, changes.parquet), JSON REST API responses, and interactive Streamlit UI charts and tables.",
        bold_prefix="Output Requirements: "
    )
    add_bullet_p(
        doc,
        "Collection requires appropriate local Windows permissions; real-machine validation requires physical sleep cycles; synthetic fixtures are utilized for verified automated testing.",
        bold_prefix="Constraints and Assumptions: "
    )

print("Chapters 2, 3, and 4 module compiled successfully.")
