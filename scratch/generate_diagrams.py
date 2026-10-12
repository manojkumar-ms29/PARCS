import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

os.makedirs("scratch/figures", exist_ok=True)

# Set high-DPI and professional font settings
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif']
plt.rcParams['font.size'] = 10

def create_figure_5_1():
    """Figure 5.1: Overall System Architecture of PARCS."""
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Background frame
    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#f8f9fa', zorder=1)
    ax.add_patch(frame)

    # Title box inside diagram
    ax.text(50, 94, "PARCS Multi-Tiered System Architecture", ha='center', va='center', fontsize=13, fontweight='bold', color='#1a252f')
    ax.text(50, 91.5, "Data-Engineering-First Windows Modern Standby Diagnostic Pipeline", ha='center', va='center', fontsize=9.5, style='italic', color='#555555')

    layers = [
        {"y": 79, "h": 9, "title": "1. Telemetry Ingestion Layer", "desc": "SleepStudy (powercfg) | Driver Snapshots (PnP) | Windows Update (HotFix) | EventLog (Kernel-Power)", "fc": "#e8f4f8", "ec": "#2980b9"},
        {"y": 66, "h": 9, "title": "2. Raw Storage & ETL Validation Layer", "desc": "Raw JSON/HTML Data Lake | Schema Normalization | Type Casting & Immutability", "fc": "#eafaf1", "ec": "#27ae60"},
        {"y": 53, "h": 9, "title": "3. Persistence & Analytical Query Layer", "desc": "Apache Parquet (Columnar Store) | Embedded DuckDB SQL Engine (Direct Parquet Querying)", "fc": "#fef9e7", "ec": "#f39c12"},
        {"y": 40, "h": 9, "title": "4. Feature Engineering & Analytics Layer", "desc": "Feature Extraction | Machine-Isolated Baselines (Median/MAD/IQR) | Anomaly & Regression Detection", "fc": "#f4ecf7", "ec": "#8e44ad"},
        {"y": 27, "h": 9, "title": "5. Correlation & Provenance Layer", "desc": "Temporal Change Correlation ([-W_before, +W_after]) | Provenance Verification (Synthetic vs Real)", "fc": "#fdedec", "ec": "#c0392b"},
        {"y": 14, "h": 9, "title": "6. Service & Presentation Layer", "desc": "FastAPI REST Service (/health, /baselines, /regressions, /correlations) | Streamlit Web Dashboard", "fc": "#ebedef", "ec": "#34495e"},
    ]

    for layer in layers:
        box = patches.FancyBboxPatch((8, layer["y"]), 84, layer["h"], boxstyle="round,pad=0.8", linewidth=1.2, edgecolor=layer["ec"], facecolor=layer["fc"], zorder=2)
        ax.add_patch(box)
        ax.text(50, layer["y"] + layer["h"] - 3, layer["title"], ha='center', va='center', fontsize=10.5, fontweight='bold', color='#2c3e50', zorder=3)
        ax.text(50, layer["y"] + 2.5, layer["desc"], ha='center', va='center', fontsize=8.5, color='#34495e', zorder=3)

    # Downward connecting arrows
    for i in range(len(layers) - 1):
        y_top = layers[i]["y"]
        y_bottom = layers[i+1]["y"] + layers[i+1]["h"]
        ax.annotate('', xy=(50, y_bottom), xytext=(50, y_top),
                    arrowprops=dict(facecolor='#2c3e50', edgecolor='#2c3e50', width=1.5, headwidth=6, headlength=5), zorder=4)

    # Bottom caption
    ax.text(50, 4.5, "Strict Machine Isolation & Prospective Reference Partitioning Across All Layers", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#7f8c8d')

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_1_architecture.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_1_architecture.png")

def create_figure_5_2():
    """Figure 5.2: End-to-End Processing Software Workflow Diagram."""
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fdfefe', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 94.5, "PARCS End-to-End Processing Software Workflow", ha='center', va='center', fontsize=12.5, fontweight='bold', color='#1a252f')

    steps = [
        ("Windows Host", 10, 82, 18, 7, "#d4efdf", "#27ae60"),
        ("Telemetry Collectors", 41, 82, 22, 7, "#d6eaf8", "#2980b9"),
        ("Raw Storage (JSON/HTML)", 72, 82, 20, 7, "#e8daef", "#8e44ad"),
        
        ("ETL & Validation", 72, 64, 20, 7, "#fcf3cf", "#f39c12"),
        ("Parquet Persistence", 41, 64, 22, 7, "#fadbd8", "#e74c3c"),
        ("DuckDB SQL Engine", 10, 64, 20, 7, "#d5f5e3", "#2ecc71"),

        ("Feature Extraction", 10, 46, 20, 7, "#d4e6f1", "#3498db"),
        ("Reference Baseline", 41, 46, 22, 7, "#fdebd0", "#d35400"),
        ("Anomaly Detection", 72, 46, 20, 7, "#ebf5fb", "#2980b9"),

        ("Sustained Regression", 72, 28, 20, 7, "#f9ebea", "#c0392b"),
        ("Change Correlation", 41, 28, 22, 7, "#e8f8f5", "#16a085"),
        ("FastAPI REST Service", 10, 28, 20, 7, "#f4ecf7", "#8e44ad"),

        ("Streamlit Interactive Visual Dashboard", 25, 10, 50, 8, "#eaeded", "#2c3e50")
    ]

    for name, x, y, w, h, fc, ec in steps:
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", linewidth=1.2, edgecolor=ec, facecolor=fc, zorder=2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8.5, fontweight='bold', color='#2c3e50', zorder=3)

    # Connections
    arrows = [
        ((28, 85.5), (41, 85.5)),
        ((63, 85.5), (72, 85.5)),
        ((82, 82), (82, 71)),
        ((72, 67.5), (63, 67.5)),
        ((41, 67.5), (30, 67.5)),
        ((20, 64), (20, 53)),
        ((30, 49.5), (41, 49.5)),
        ((63, 49.5), (72, 49.5)),
        ((82, 46), (82, 35)),
        ((72, 31.5), (63, 31.5)),
        ((41, 31.5), (30, 31.5)),
        ((20, 28), (20, 18), (35, 18)), # bend to streamlit
    ]

    ax.annotate('', xy=(41, 85.5), xytext=(28, 85.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(72, 85.5), xytext=(63, 85.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(82, 71), xytext=(82, 82), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(63, 67.5), xytext=(72, 67.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(30, 67.5), xytext=(41, 67.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(20, 53), xytext=(20, 64), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(41, 49.5), xytext=(30, 49.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(72, 49.5), xytext=(63, 49.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(82, 35), xytext=(82, 46), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(63, 31.5), xytext=(72, 31.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(30, 31.5), xytext=(41, 31.5), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(40, 18), xytext=(20, 28), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.annotate('', xy=(60, 18), xytext=(52, 28), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_2_workflow.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_2_workflow.png")

def create_figure_5_3():
    """Figure 5.3: Use Case Diagram of PARCS."""
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fcfcfc', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 94.5, "PARCS Use Case Model", ha='center', va='center', fontsize=13, fontweight='bold', color='#1a252f')

    # Actor on the left
    actor_x, actor_y = 12, 50
    # Head
    circle = patches.Circle((actor_x, actor_y + 10), 3, facecolor='#34495e', edgecolor='#2c3e50', zorder=3)
    ax.add_patch(circle)
    # Body
    ax.plot([actor_x, actor_x], [actor_y + 7, actor_y], color='#2c3e50', lw=2, zorder=3)
    # Arms
    ax.plot([actor_x - 4, actor_x + 4], [actor_y + 4, actor_y + 4], color='#2c3e50', lw=2, zorder=3)
    # Legs
    ax.plot([actor_x, actor_x - 3], [actor_y, actor_y - 6], color='#2c3e50', lw=2, zorder=3)
    ax.plot([actor_x, actor_x + 3], [actor_y, actor_y - 6], color='#2c3e50', lw=2, zorder=3)
    ax.text(actor_x, actor_y - 10, "Performance Engineer /\nSystem Administrator", ha='center', va='center', fontsize=9, fontweight='bold', color='#2c3e50')

    # System boundary box
    sys_box = patches.Rectangle((28, 8), 68, 82, linewidth=1.2, edgecolor='#7f8c8d', facecolor='#f8f9fa', linestyle='--', zorder=2)
    ax.add_patch(sys_box)
    ax.text(62, 87, "PARCS System Boundary", ha='center', va='center', fontsize=11, fontweight='bold', color='#2c3e50')

    use_cases = [
        (62, 79, "UC-1: Ingest & Validate Windows Telemetry"),
        (62, 69, "UC-2: Seed Deterministic Synthetic Demo Data"),
        (62, 59, "UC-3: View Machine Baseline & Readiness Status"),
        (62, 49, "UC-4: Detect Robust Point Anomalies (Modified Z-Score)"),
        (62, 39, "UC-5: Detect Sustained Performance Regressions"),
        (62, 29, "UC-6: Correlate Regressions with System Changes"),
        (62, 19, "UC-7: Inspect Visual Dashboard & System Telemetry Log"),
    ]

    for ux, uy, utext in use_cases:
        ellipse = patches.Ellipse((ux, uy), 46, 6.8, facecolor='#ebf5fb', edgecolor='#2980b9', linewidth=1.2, zorder=3)
        ax.add_patch(ellipse)
        ax.text(ux, uy, utext, ha='center', va='center', fontsize=8.5, fontweight='bold', color='#1b4f72', zorder=4)
        # Association line
        ax.plot([actor_x + 5, ux - 23], [actor_y + 3, uy], color='#7f8c8d', lw=1.1, linestyle='-', zorder=2)

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_3_usecase.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_3_usecase.png")

def create_figure_5_4():
    """Figure 5.4: Logical Component and Data Model Architecture."""
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fcfcfc', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 94.5, "Logical Component & Analytical Data Model Design", ha='center', va='center', fontsize=12.5, fontweight='bold', color='#1a252f')

    # Left: Software Components
    ax.text(26, 88, "Functional Subsystems", ha='center', va='center', fontsize=10.5, fontweight='bold', color='#2980b9')
    components = [
        (6, 73, 40, 11, "Telemetry Collection Subsystem", "SleepStudyCollector, DriverCollector,\nUpdateCollector, EventLogCollector"),
        (6, 58, 40, 11, "ETL & Persistence Subsystem", "ETL Pipeline, Schema Validator,\nParquetWriter/Reader, DuckDBManager"),
        (6, 43, 40, 11, "Analytics & Correlation Engine", "FeatureEngineering, BaselineBuilder,\nAnomalyDetector, RegressionDetector, Correlation"),
        (6, 28, 40, 11, "Service & Presentation Subsystem", "AnalyticsService, FastAPI App,\nPARCSApiClient, Streamlit Dashboard"),
    ]
    for x, y, w, h, title, desc in components:
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", linewidth=1.2, edgecolor='#2980b9', facecolor='#ebf5fb', zorder=2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h - 3, title, ha='center', va='center', fontsize=9, fontweight='bold', color='#1b4f72', zorder=3)
        ax.text(x + w/2, y + 3.5, desc, ha='center', va='center', fontsize=7.5, color='#34495e', zorder=3)

    # Right: Relational/Parquet Data Models
    ax.text(74, 88, "Parquet & Analytics Schemas", ha='center', va='center', fontsize=10.5, fontweight='bold', color='#27ae60')
    schemas = [
        (54, 73, 40, 11, "sleepstudy.parquet", "machine_id, start_time, end_time, duration_s,\ndrips_percent, drain_rate_mw, is_synthetic"),
        (54, 58, 40, 11, "changes.parquet", "machine_id, timestamp, change_type,\nchange_id, description, is_synthetic"),
        (54, 43, 40, 11, "baseline_schema", "machine_id, metric, median, mad, iqr,\nscale, valid_count, readiness"),
        (54, 28, 40, 11, "correlation_schema", "machine_id, metric, change_id, offset_s,\ntemporal_relation, reason, is_correlated"),
    ]
    for x, y, w, h, title, desc in schemas:
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", linewidth=1.2, edgecolor='#27ae60', facecolor='#eafaf1', zorder=2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h - 3, title, ha='center', va='center', fontsize=9, fontweight='bold', color='#1e8449', zorder=3)
        ax.text(x + w/2, y + 3.5, desc, ha='center', va='center', fontsize=7.5, color='#34495e', zorder=3)

    # Connecting relations
    for i in range(4):
        y_val = 78.5 - (i * 15)
        ax.annotate('', xy=(54, y_val), xytext=(46, y_val),
                    arrowprops=dict(facecolor='#7f8c8d', edgecolor='#7f8c8d', width=1, headwidth=4, headlength=4))

    ax.text(50, 14, "Immutability & Machine-Isolation Guaranteed via Strict Columnar Partitioning", ha='center', va='center', fontsize=8.5, style='italic', color='#555555')

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_4_components.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_4_components.png")

def create_figure_5_5():
    """Figure 5.5: Activity Diagram of PARCS Telemetry Processing."""
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fcfcfc', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 94.5, "PARCS Telemetry Ingestion & Regression Analysis Activity Flow", ha='center', va='center', fontsize=12, fontweight='bold', color='#1a252f')

    # Initial state
    start_circle = patches.Circle((50, 88), 2.2, facecolor='#2c3e50', edgecolor='#2c3e50', zorder=3)
    ax.add_patch(start_circle)
    ax.text(50, 84, "Start Ingestion", ha='center', va='center', fontsize=7.5, color='#555555')

    nodes = [
        (35, 74, 30, 6, "Execute Telemetry Collection"),
        (35, 62, 30, 6, "ETL Normalization & Parquet Persistence"),
        (35, 50, 30, 6, "Partition Reference vs Evaluation Sets"),
    ]
    for x, y, w, h, text in nodes:
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4", linewidth=1.1, edgecolor='#2980b9', facecolor='#ebf5fb', zorder=2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=8, fontweight='bold', color='#1b4f72', zorder=3)

    # Decision diamond: Observations >= min_observations?
    diamond = patches.Polygon([[50, 44], [62, 38], [50, 32], [38, 38]], facecolor='#fef9e7', edgecolor='#f39c12', linewidth=1.2, zorder=2)
    ax.add_patch(diamond)
    ax.text(50, 38, "Observations\n>= 10?", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#7d6608', zorder=3)

    # Branch left: No (Sparse)
    box_sparse = patches.FancyBboxPatch((8, 22), 34, 6, boxstyle="round,pad=0.4", linewidth=1.1, edgecolor='#e67e22', facecolor='#fdf2e9', zorder=2)
    ax.add_patch(box_sparse)
    ax.text(25, 25, "Mark readiness = 'insufficient_history'\n(No false regression alarms)", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#a04000', zorder=3)

    # Branch right: Yes (Ready)
    box_ready = patches.FancyBboxPatch((58, 22), 34, 6, boxstyle="round,pad=0.4", linewidth=1.1, edgecolor='#27ae60', facecolor='#eafaf1', zorder=2)
    ax.add_patch(box_ready)
    ax.text(75, 25, "Compute Median, MAD, IQR\nDetect Sustained Regressions", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#1e8449', zorder=3)

    # Merge node & final correlation
    box_final = patches.FancyBboxPatch((32, 10), 36, 6, boxstyle="round,pad=0.4", linewidth=1.1, edgecolor='#8e44ad', facecolor='#f4ecf7', zorder=2)
    ax.add_patch(box_final)
    ax.text(50, 13, "Correlate with Recorded Changes\n& Render Dashboard", ha='center', va='center', fontsize=8, fontweight='bold', color='#512e5f', zorder=3)

    # Connectors
    ax.annotate('', xy=(50, 80), xytext=(50, 85.8), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(50, 68), xytext=(50, 74), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(50, 56), xytext=(50, 62), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(50, 44), xytext=(50, 50), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # Decision branches
    ax.annotate('', xy=(25, 28), xytext=(38, 38), arrowprops=dict(facecolor='#e67e22', width=1, headwidth=4))
    ax.text(28, 35, "No (<10)", fontsize=7.5, fontweight='bold', color='#d35400')

    ax.annotate('', xy=(75, 28), xytext=(62, 38), arrowprops=dict(facecolor='#27ae60', width=1, headwidth=4))
    ax.text(70, 35, "Yes (>=10)", fontsize=7.5, fontweight='bold', color='#27ae60')

    # Merge to final
    ax.annotate('', xy=(42, 16), xytext=(25, 22), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(58, 16), xytext=(75, 22), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_5_activity.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_5_activity.png")

def create_figure_5_6():
    """Figure 5.6: Context-Level Data Flow Diagram (DFD Level 0)."""
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fcfcfc', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 93, "PARCS Context-Level Data Flow Diagram (DFD Level 0)", ha='center', va='center', fontsize=12.5, fontweight='bold', color='#1a252f')

    # External Entity: Windows OS / Host Telemetry
    box_ext1 = patches.Rectangle((6, 42), 22, 18, linewidth=1.2, edgecolor='#2980b9', facecolor='#ebf5fb', zorder=2)
    ax.add_patch(box_ext1)
    ax.text(17, 51, "External Entity 1:\nWindows Host OS\n(Diagnostics)", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#1b4f72')

    # Central Process: PARCS System
    circle_proc = patches.Circle((50, 51), 16, linewidth=1.5, edgecolor='#8e44ad', facecolor='#f4ecf7', zorder=2)
    ax.add_patch(circle_proc)
    ax.text(50, 52, "Process 0.0:\nPARCS\nTelemetry &\nRegression Engine", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#512e5f')

    # External Entity: Performance Engineer
    box_ext2 = patches.Rectangle((72, 42), 22, 18, linewidth=1.2, edgecolor='#27ae60', facecolor='#eafaf1', zorder=2)
    ax.add_patch(box_ext2)
    ax.text(83, 51, "External Entity 2:\nPerformance Engineer\n/ System Admin", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#1e8449')

    # Data flows left
    ax.annotate('', xy=(34, 54), xytext=(28, 54), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.text(31, 57, "SleepStudy XML, Driver & Update Snapshots", ha='center', va='bottom', fontsize=7.5, color='#2c3e50')

    # Data flows right (top and bottom)
    ax.annotate('', xy=(66, 56), xytext=(72, 56), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.text(69, 58.5, "Query & Filter Requests", ha='center', va='bottom', fontsize=7.5, color='#2c3e50')

    ax.annotate('', xy=(72, 46), xytext=(66, 46), arrowprops=dict(facecolor='#2c3e50', width=1.2, headwidth=5))
    ax.text(69, 42, "Baselines, Regressions & Visual Insights", ha='center', va='top', fontsize=7.5, color='#2c3e50')

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_6_dfd0.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_6_dfd0.png")

def create_figure_5_7():
    """Figure 5.7: Level-1 Data Flow Diagram (DFD Level 1)."""
    fig, ax = plt.subplots(figsize=(9.5, 7), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    frame = patches.Rectangle((2, 2), 96, 96, linewidth=1.5, edgecolor='#2c3e50', facecolor='#fcfcfc', zorder=1)
    ax.add_patch(frame)

    ax.text(50, 95.5, "PARCS Level-1 Data Flow Diagram (DFD Level 1)", ha='center', va='center', fontsize=12.5, fontweight='bold', color='#1a252f')

    # Processes (Circles or Rounded boxes)
    procs = [
        ("1.0 Collect Telemetry", 16, 82),
        ("2.0 ETL & Normalization", 50, 82),
        ("3.0 Parquet & DuckDB Querying", 84, 82),
        ("4.0 Baseline Construction", 84, 48),
        ("5.0 Regression & Anomaly Scoring", 50, 48),
        ("6.0 Temporal Change Correlation", 16, 48),
        ("7.0 API & Dashboard Display", 50, 14),
    ]

    for name, x, y in procs:
        circ = patches.FancyBboxPatch((x-12, y-6), 24, 12, boxstyle="round,pad=0.3", linewidth=1.2, edgecolor='#2980b9', facecolor='#ebf5fb', zorder=2)
        ax.add_patch(circ)
        ax.text(x, y, name, ha='center', va='center', fontsize=7.5, fontweight='bold', color='#1b4f72', zorder=3)

    # Data Stores (Open-ended horizontal bars)
    def draw_store(x, y, text):
        ax.plot([x-10, x+10], [y+3, y+3], color='#27ae60', lw=1.5, zorder=3)
        ax.plot([x-10, x+10], [y-3, y-3], color='#27ae60', lw=1.5, zorder=3)
        ax.text(x, y, text, ha='center', va='center', fontsize=7, fontweight='bold', color='#1e8449', zorder=4)

    draw_store(33, 67, "D1: Raw Storage")
    draw_store(67, 67, "D2: Parquet Store")
    draw_store(50, 31, "D3: Analytics Cache")

    # Arrows connecting Level 1
    # 1.0 -> D1 -> 2.0
    ax.annotate('', xy=(23, 67), xytext=(16, 76), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(44, 76), xytext=(38, 67), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 2.0 -> D2 -> 3.0
    ax.annotate('', xy=(57, 67), xytext=(50, 76), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(78, 76), xytext=(72, 67), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 3.0 -> 4.0
    ax.annotate('', xy=(84, 54), xytext=(84, 76), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 4.0 -> 5.0
    ax.annotate('', xy=(62, 48), xytext=(72, 48), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 5.0 -> 6.0
    ax.annotate('', xy=(28, 48), xytext=(38, 48), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 5.0 -> D3
    ax.annotate('', xy=(50, 34), xytext=(50, 42), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    # 6.0 & D3 -> 7.0
    ax.annotate('', xy=(40, 18), xytext=(20, 42), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))
    ax.annotate('', xy=(50, 20), xytext=(50, 28), arrowprops=dict(facecolor='#2c3e50', width=1, headwidth=4))

    plt.tight_layout()
    plt.savefig("scratch/figures/fig_5_7_dfd1.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved fig_5_7_dfd1.png")

if __name__ == "__main__":
    create_figure_5_1()
    create_figure_5_2()
    create_figure_5_3()
    create_figure_5_4()
    create_figure_5_5()
    create_figure_5_6()
    create_figure_5_7()
    print("All 7 system design diagrams created successfully!")
