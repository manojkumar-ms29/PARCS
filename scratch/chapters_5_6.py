"""Chapters 5 and 6 for the PARCS Academic Project Report."""

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
    add_figure_image,
    add_academic_table,
    add_code_snippet,
)


def add_chapter_5(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "5. SYSTEM DESIGN")

    add_section_heading(doc, "5.1 Introduction")
    add_body_p(
        doc,
        "System design translates the functional and non-functional requirements identified in the system analysis phase "
        "into a coherent, robust, and extensible software architecture. In data-intensive systems, design choices dictate "
        "not only execution performance and storage efficiency, but also data integrity, modularity, and analytical "
        "correctness. PARCS is architected around a strict data-engineering-first philosophy: each stage of the pipeline "
        "possesses well-defined input and output contracts, preventing cross-layer coupling and ensuring that analytical "
        "assumptions (such as machine isolation and prospective reference purity) are enforced by design. This chapter "
        "details the system architecture, software workflow, use case model, logical components, activity flow, data flow "
        "diagrams (DFD Level 0 and Level 1), and foundational design considerations."
    )

    add_section_heading(doc, "5.2 System Architecture")
    add_body_p(
        doc,
        "The overall system architecture of PARCS is organized into six decoupled tiers spanning telemetry ingestion, "
        "raw preservation, ETL normalization, columnar persistence, analytics, and service presentation. Each layer operates "
        "strictly within its designated functional boundary:"
    )
    add_bullet_p(
        doc,
        "Executes Windows-native utilities (powercfg /sleepstudy, Get-PnpDevice, Get-HotFix, wevtutil) to capture hardware, driver, and OS events without performing any business logic or data transformation.",
        bold_prefix="1. Telemetry Ingestion Layer: "
    )
    add_bullet_p(
        doc,
        "Immutably archives raw collector output in timestamped JSON/HTML files under data/raw/, and executes schema validation, data cleaning, and canonical type casting.",
        bold_prefix="2. Raw Storage & ETL Layer: "
    )
    add_bullet_p(
        doc,
        "Stores normalized telemetry in Apache Parquet columnar files (data/processed/) and provides zero-copy, in-process SQL analytical query capabilities via embedded DuckDB.",
        bold_prefix="3. Persistence & Query Layer: "
    )
    add_bullet_p(
        doc,
        "Extracts behavioral performance features, constructs machine-isolated robust statistical baselines (Median, MAD, IQR), evaluates Modified Z-score point anomalies, and identifies sustained regressions across consecutive sessions.",
        bold_prefix="4. Feature Engineering & Analytics Layer: "
    )
    add_bullet_p(
        doc,
        "Associates detected regressions with recorded system changes within configurable temporal windows, tracking data provenance (is_synthetic flags).",
        bold_prefix="5. Correlation & Provenance Layer: "
    )
    add_bullet_p(
        doc,
        "Exposes analytics via an asynchronous FastAPI REST service and renders responsive charts and diagnostic metrics in a Streamlit web application.",
        bold_prefix="6. Service & Presentation Layer: "
    )

    add_figure_image(doc, "scratch/figures/fig_5_1_architecture.png", "Figure 5.1: Overall System Architecture of PARCS")

    add_section_heading(doc, "5.3 Software Workflow Diagram")
    add_body_p(
        doc,
        "The software workflow illustrates the chronological data path as raw Windows events are transformed into "
        "actionable engineering insights. The workflow enforces unidirectional data flow, ensuring that downstream layers "
        "cannot alter or corrupt upstream telemetry."
    )

    add_figure_image(doc, "scratch/figures/fig_5_2_workflow.png", "Figure 5.2: End-to-End Processing Software Workflow Diagram")

    add_body_p(
        doc,
        "As depicted in Figure 5.2, collection initiates on the Windows host. Structured collector results are preserved "
        "in raw storage, validated by the ETL pipeline, and persisted to Parquet. The analytics engine queries Parquet via "
        "DuckDB, partitions observations into reference and evaluation sets, builds machine-specific baselines, evaluates "
        "anomalies and regressions, and performs non-causal change correlation, serving results via FastAPI and Streamlit."
    )

    add_section_heading(doc, "5.4 Use Case Diagram")
    add_body_p(
        doc,
        "The use case diagram models the interactions between the primary human actor—the Performance Engineer or System "
        "Administrator—and the core functional boundaries of PARCS."
    )

    add_figure_image(doc, "scratch/figures/fig_5_3_usecase.png", "Figure 5.3: Use Case Diagram of PARCS")

    add_body_p(
        doc,
        "The primary actor interacts with seven discrete use cases: ingesting telemetry (UC-1), seeding deterministic demo fixtures (UC-2), "
        "inspecting machine baselines and readiness statuses (UC-3), detecting point anomalies (UC-4), identifying sustained regressions (UC-5), "
        "correlating regressions with system events (UC-6), and exploring telemetry trends through the visual dashboard (UC-7)."
    )

    add_section_heading(doc, "5.5 Logical Component and Data Model Design")
    add_body_p(
        doc,
        "PARCS is constructed from cohesive Python modules organized into functional subsystems paired with strongly typed "
        "columnar data schemas. This modularity ensures separation of concerns between collection, storage, and statistical modeling."
    )

    add_figure_image(doc, "scratch/figures/fig_5_4_components.png", "Figure 5.4: Logical Component and Data Model Architecture")

    add_body_p(
        doc,
        "The data model design establishes strict columnar contracts across the pipeline. The sleepstudy dataset tracks machine_id, "
        "start_time, end_time, duration_seconds, drips_percent, battery_drain_percent, battery_drain_rate_mw, and is_synthetic. "
        "The changes dataset records machine_id, timestamp, change_type, change_id, description, and is_synthetic. The baseline schema "
        "captures median, mad, iqr, dispersion_scale, valid_count, and readiness, while the correlation schema outputs matched "
        "change_id, temporal_relation, offset_seconds, and non-causal explanation strings."
    )

    add_section_heading(doc, "5.6 Activity Diagram")
    add_body_p(
        doc,
        "The activity diagram models the dynamic control flow during telemetry analysis, emphasizing decision points around "
        "observation count thresholds, baseline readiness, and streak continuity."
    )

    add_figure_image(doc, "scratch/figures/fig_5_5_activity.png", "Figure 5.5: Activity Diagram of PARCS Telemetry Ingestion and Analysis")

    add_body_p(
        doc,
        "A critical branch in Figure 5.5 occurs during observation count evaluation: if a machine contains fewer than 10 valid "
        "historical sessions, its baseline readiness is assigned 'insufficient_history', and the regression detector returns an "
        "explicit unready status without raising false alarms. Only machines with ready baselines proceed to streak-based regression evaluation."
    )

    add_section_heading(doc, "5.7 Data Flow Diagram")
    add_body_p(
        doc,
        "Data Flow Diagrams (DFDs) model how data moves, transforms, and rests across system boundaries without implying control logic."
    )

    add_subsection_heading(doc, "5.7.1 Context-Level Data Flow Diagram (DFD Level 0)")
    add_body_p(
        doc,
        "The Context-Level DFD treats PARCS as a single unified process interacting with external entities: the Windows Host OS "
        "(providing diagnostic telemetry) and the Performance Engineer (submitting analytical queries and receiving visual insights)."
    )

    add_figure_image(doc, "scratch/figures/fig_5_6_dfd0.png", "Figure 5.6: Context-Level Data Flow Diagram (DFD Level 0)")

    add_subsection_heading(doc, "5.7.2 Level-1 Data Flow Diagram (DFD Level 1)")
    add_body_p(
        doc,
        "The Level-1 DFD decomposes Process 0.0 into seven discrete sub-processes (1.0 Collection, 2.0 ETL, 3.0 Storage/DuckDB Query, "
        "4.0 Baseline Construction, 5.0 Regression Scoring, 6.0 Temporal Correlation, 7.0 Presentation) interacting with three "
        "persistent data stores: D1 Raw Storage, D2 Parquet Data Store, and D3 Analytics Cache."
    )

    add_figure_image(doc, "scratch/figures/fig_5_7_dfd1.png", "Figure 5.7: Level-1 Data Flow Diagram of PARCS (DFD Level 1)")

    add_section_heading(doc, "5.8 Design Considerations")
    add_body_p(
        doc,
        "The architecture incorporates four essential engineering design considerations:"
    )
    add_bullet_p(
        doc,
        "To prevent later degraded sessions from contaminating the baseline used to evaluate them, PARCS deterministically splits "
        "observations chronologically into reference and subsequent evaluation partitions.",
        bold_prefix="1. Prospective Reference Partitioning: "
    )
    add_bullet_p(
        doc,
        "Observations from different machines are never aggregated. Machine identities are isolated across all pandas groupby and "
        "DuckDB query filters.",
        bold_prefix="2. Strict Machine Isolation: "
    )
    add_bullet_p(
        doc,
        "When observations exhibit zero variance (MAD = 0), the system dynamically falls back to IQR / 1.3490 or a minimal epsilon "
        "(1e-4) to prevent division-by-zero errors while maintaining sensitivity.",
        bold_prefix="3. Zero-MAD Fallback Handling: "
    )
    add_bullet_p(
        doc,
        "All explanations explicitly state temporal offsets (e.g. 'Driver updated 1.5h before regression onset') while declaring that "
        "causation is not asserted, preventing engineers from misinterpreting correlation as proof.",
        bold_prefix="4. Non-Causal Epistemological Framing: "
    )

    add_section_heading(doc, "5.9 Chapter Summary")
    add_body_p(
        doc,
        "This chapter articulated the comprehensive design of PARCS across six architectural layers, complete with formal UML "
        "and data flow diagrams. The design enforces machine isolation, prospective reference purity, robust zero-MAD resilience, "
        "and explainable correlation, establishing the framework for implementation."
    )


def add_chapter_6(doc: docx.Document) -> None:
    doc.add_page_break()
    add_chapter_heading(doc, "6. SYSTEM IMPLEMENTATION")

    add_section_heading(doc, "6.1 Introduction")
    add_body_p(
        doc,
        "System implementation translates the design specifications into modular, maintainable, and verifiable Python source code. "
        "PARCS is organized under the src/ directory into discrete packages: collectors, etl, storage, analytics, api, dashboard, "
        "and utils. This chapter details the technical implementation of each subsystem, documenting the concrete algorithms, "
        "contracts, and validation checks implemented in the codebase."
    )

    add_section_heading(doc, "6.2 Module Description")

    add_subsection_heading(doc, "6.2.1 Telemetry Collectors (src/collectors/)")
    add_body_p(
        doc,
        "All collectors inherit from the BaseCollector abstract base class defined in src/collectors/base.py, implementing "
        "a standardized collect() method that returns a strongly typed CollectorResult namedtuple or dataclass containing "
        "collector name, success status, collected_at timestamp, raw_path reference, data payload, and error string. "
        "The collection layer comprises four specialized modules:"
    )
    add_bullet_p(
        doc,
        "Executes powercfg /sleepstudy /output <path> /xml via Python's subprocess.run with check=False and timeout guards. "
        "Parses the generated XML/HTML report to extract session start/end timestamps, duration in seconds, DRIPS percentage, "
        "total battery drain percentage, and battery drain rate in milliwatts (mW). Preserves the raw report under data/raw/.",
        bold_prefix="SleepStudyCollector (sleepstudy.py): "
    )
    add_bullet_p(
        doc,
        "Executes PowerShell Get-PnpDevice to capture a complete snapshot of installed Plug-and-Play device drivers, recording "
        "device instance ID, friendly name, driver version, manufacturer/provider, and device status.",
        bold_prefix="DriverCollector (drivers.py): "
    )
    add_bullet_p(
        doc,
        "Queries Windows Update history via PowerShell Get-HotFix and Microsoft.Update.Session COM objects, extracting hotfix "
        "identifiers (e.g. KB5034204), installation timestamps, and descriptions.",
        bold_prefix="UpdateCollector (updates.py): "
    )
    add_bullet_p(
        doc,
        "Queries the Windows Event Log via wevtutil or Get-WinEvent, focusing on Microsoft-Windows-Kernel-Power (Event IDs 506 and 507) "
        "to capture sleep transitions, wake reasons, and hardware power events around sleep sessions.",
        bold_prefix="EventLogCollector (eventlog.py): "
    )

    add_subsection_heading(doc, "6.2.2 Raw Storage Preservation (src/storage/raw.py, paths.py)")
    add_body_p(
        doc,
        "To guarantee auditability and protect against data loss during schema migrations, the raw storage module persists all "
        "collector payloads into data/raw/ using deterministic timestamped filenames: <collector>-<timestamp>-<hash>.json. "
        "Raw files are strictly immutable; once written, they are never updated or truncated."
    )

    add_subsection_heading(doc, "6.2.3 ETL and Schema Validation (src/etl/)")
    add_body_p(
        doc,
        "The ETL pipeline (pipeline.py, sleepstudy.py, transform.py) extracts raw sessions and system changes, applies data "
        "cleaning (stripping whitespace, normalizing ISO 8601 UTC timestamps), and validates schemas against canonical column "
        "specifications (SLEEPSTUDY_COLUMNS and CHANGE_SCHEMA_COLUMNS). Null and invalid values are handled gracefully, ensuring "
        "downstream analytics receive consistent tabular data."
    )

    add_subsection_heading(doc, "6.2.4 Columnar Parquet Persistence (src/storage/parquet.py)")
    add_body_p(
        doc,
        "Normalized datasets are persisted to Apache Parquet format using pyarrow and pandas under data/processed/sleepstudy.parquet "
        "and data/processed/changes.parquet. Write operations utilize atomic file swaps to prevent file corruption during concurrent reads."
    )

    add_subsection_heading(doc, "6.2.5 DuckDB Analytical Storage (src/storage/db.py)")
    add_body_p(
        doc,
        "The DuckDBManager establishes an in-process DuckDB connection. It registers the Parquet files as views or queries "
        "them directly via DuckDB's read_parquet() function, providing sub-millisecond analytical aggregations without "
        "requiring external database server processes."
    )

    add_subsection_heading(doc, "6.2.6 Feature Engineering (src/analytics/features.py)")
    add_body_p(
        doc,
        "The feature engineering module takes normalized SleepStudy sessions and derives analytical metrics, ensuring that "
        "start_time and end_time are parsed as timezone-aware UTC timestamps, calculating duration deltas, and validating that "
        "drips_percent falls within [0.0, 100.0] and battery_drain_rate_mw is positive."
    )

    add_subsection_heading(doc, "6.2.7 Statistical Baseline Construction (src/analytics/baseline.py)")
    add_body_p(
        doc,
        "The baseline module computes machine-specific non-parametric baselines. For each machine and metric (drips_percent, "
        "battery_drain_rate_mw, battery_drain_percent), it calculates the median, MAD, and IQR. If valid_count < min_observations "
        "(default 10), readiness is set to 'insufficient_history'. If MAD == 0, it falls back to IQR / 1.3490 or epsilon (1e-4), "
        "setting zero_mad_fallback = True."
    )

    add_subsection_heading(doc, "6.2.8 Point Anomaly Detection (src/analytics/anomaly.py)")
    add_body_p(
        doc,
        "The anomaly detector computes Modified Z-scores for each session against the ready baseline. Sessions exceeding "
        "the cutoff (threshold = 3.5) are flagged with is_anomaly = True and assigned status = 'anomaly'. If the baseline is unready, "
        "status = 'insufficient_history' is returned with is_anomaly = False."
    )

    add_subsection_heading(doc, "6.2.9 Sustained Regression Detection (src/analytics/regression.py)")
    add_body_p(
        doc,
        "The regression detector evaluates observations sequentially in chronological timestamp order. It enforces directional "
        "harmful deviations (lower DRIPS %, higher battery drain). A regression event is flagged when at least min_consecutive "
        "(default 3) consecutive qualifying sessions cross the threshold. Non-qualifying or missing sessions immediately reset the streak."
    )

    add_subsection_heading(doc, "6.2.10 Temporal Change Correlation (src/analytics/correlation.py)")
    add_body_p(
        doc,
        "When regressions are flagged, the correlation engine searches for system changes on the same machine within the window "
        "[start_time - 24 hours, start_time + 2 hours]. It computes the temporal offset in seconds, classifies the relation "
        "('before', 'concurrent', 'after'), and generates an explainable non-causal reason string."
    )

    add_subsection_heading(doc, "6.2.11 FastAPI Backend Services (src/api/)")
    add_body_p(
        doc,
        "The FastAPI backend (app.py, service.py, models.py) provides high-performance asynchronous REST endpoints. "
        "AnalyticsService coordinates data loading, prospective partitioning, baseline generation, and regression scoring. "
        "All parameters are validated via Pydantic models."
    )

    add_subsection_heading(doc, "6.2.12 Streamlit Dashboard Application (src/dashboard/)")
    add_body_p(
        doc,
        "The dashboard (app.py, client.py) delivers an interactive user interface featuring a sidebar for machine selection "
        "and threshold configuration, metric summary cards, and five analytical tabs: Statistical Baselines, Anomaly Detection, "
        "Sustained Regressions, Change Correlation, and System Changes Log."
    )

    add_section_heading(doc, "6.3 Validation Checks")
    add_body_p(
        doc,
        "PARCS implements six critical validation checks verified by the automated test suite:"
    )
    add_bullet_p(
        doc,
        "AnalyticsService.partition_machine_features supports 'subsequent' (evaluating only sessions occurring after the reference partition) "
        "and 'all' (scoring the entire dataset against the reference). Invalid scope values are rejected with HTTP 422.",
        bold_prefix="1. Evaluation-Scope Isolation: "
    )
    add_bullet_p(
        doc,
        "Reference observations are strictly excluded from subsequent evaluation sets, preventing circular self-scoring.",
        bold_prefix="2. Reference Exclusion: "
    )
    add_bullet_p(
        doc,
        "When reference_count covers all available observations, the subsequent evaluation set is empty, and the service returns an empty list ([]) "
        "without silently falling back to scoring reference sessions.",
        bold_prefix="3. Empty Subsequent Handling: "
    )
    add_bullet_p(
        doc,
        "Machines with fewer than min_observations (such as DEMO-MACHINE-SPARSE with 4 sessions) receive status 'insufficient_history' and is_regression = False.",
        bold_prefix="4. Insufficient History Guard: "
    )
    add_bullet_p(
        doc,
        "API query parameters (threshold <= 0, min_consecutive < 1, negative windows) are rejected with HTTP 422 Unprocessable Entity.",
        bold_prefix="5. HTTP 422 Validation: "
    )
    add_bullet_p(
        doc,
        "Synthetic fixtures are explicitly tagged with is_synthetic: True, and telemetry summaries report machine-specific provenance without false flags.",
        bold_prefix="6. Provenance Validation: "
    )

    add_section_heading(doc, "6.4 Chapter Summary")
    add_body_p(
        doc,
        "This chapter detailed the concrete Python implementation of PARCS across all functional modules. Each component enforces "
        "strict contracts, robust statistical methods, and exhaustive validation checks, ensuring reliability and academic credibility."
    )

print("Chapters 5 and 6 module compiled successfully.")
