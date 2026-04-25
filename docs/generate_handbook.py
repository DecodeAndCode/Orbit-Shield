"""Generate ORBIT-SHIELD interview handbook PDF."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)
from reportlab.lib.enums import TA_LEFT

OUT = "ORBIT_SHIELD_HANDBOOK.pdf"

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.7*inch,
                        rightMargin=0.7*inch, topMargin=0.7*inch, bottomMargin=0.7*inch)
ss = getSampleStyleSheet()

H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=18, spaceAfter=10,
                    textColor=HexColor("#FF8C00"), fontName="Helvetica-Bold")
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=14, spaceBefore=14,
                    spaceAfter=6, textColor=HexColor("#1a3a5c"), fontName="Helvetica-Bold")
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11.5, spaceBefore=8,
                    spaceAfter=4, textColor=HexColor("#333"), fontName="Helvetica-Bold")
P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=6)
CODE = ParagraphStyle("CODE", parent=ss["Code"], fontSize=8.5, leading=11,
                      backColor=HexColor("#f4f4f4"), borderPadding=4,
                      leftIndent=6, rightIndent=6, spaceAfter=6)
BUL = ParagraphStyle("BUL", parent=P, leftIndent=14, bulletIndent=4)

story = []

def h1(t): story.append(Paragraph(t, H1))
def h2(t): story.append(Paragraph(t, H2))
def h3(t): story.append(Paragraph(t, H3))
def p(t): story.append(Paragraph(t, P))
def code(t): story.append(Paragraph(t.replace("<","&lt;").replace(">","&gt;").replace("\n","<br/>"), CODE))
def bul(items):
    for i in items:
        story.append(Paragraph(f"&bull; {i}", BUL))
def sp(h=6): story.append(Spacer(1, h))
def tbl(rows, widths=None, header=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONT", (0,0), (-1,-1), "Helvetica", 9),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.3, grey),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0,0), (-1,0), HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0,0), (-1,0), HexColor("#ffffff")),
            ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ]
    t.setStyle(TableStyle(style))
    story.append(t)
    sp(8)

# ============ COVER ============
story.append(Spacer(1, 1.5*inch))
story.append(Paragraph("ORBIT-SHIELD", ParagraphStyle("cover", parent=H1, fontSize=36, alignment=1, textColor=HexColor("#FF8C00"))))
story.append(Spacer(1, 12))
story.append(Paragraph("ML-Enhanced Satellite Collision Avoidance",
                       ParagraphStyle("sub", parent=P, fontSize=14, alignment=1, textColor=HexColor("#666"))))
story.append(Spacer(1, 0.4*inch))
story.append(Paragraph("Engineering Handbook &amp; Interview Reference",
                       ParagraphStyle("sub2", parent=P, fontSize=12, alignment=1, textColor=grey)))
story.append(Spacer(1, 0.8*inch))
story.append(Paragraph("Inspired by Privateer Space's <i>Wayfinder</i>. Built solo as a portfolio piece "
                       "demonstrating end-to-end ownership: orbital mechanics, ML, full-stack, infra.",
                       ParagraphStyle("desc", parent=P, fontSize=11, alignment=1)))
story.append(PageBreak())

# ============ 1. PROBLEM ============
h1("1. The Problem We're Solving")
p("Low-Earth orbit is becoming dangerously crowded. Over <b>30,000 tracked objects</b> larger than 10 cm "
  "and an estimated <b>1 million pieces</b> 1–10 cm exist. A 10 cm fragment at orbital velocity (~7.5 km/s) "
  "carries the kinetic energy of a hand grenade. Operators currently rely on Conjunction Data Messages "
  "(CDMs) issued by the U.S. Space Force's 18th Space Defense Squadron, but they receive hundreds per day "
  "with extremely conservative probability of collision (Pc) estimates.")
p("<b>The decision threshold for a collision-avoidance maneuver is Pc &ge; 1e-4.</b> Below that, no action. "
  "Above, burn fuel (which shortens mission life). False positives waste fuel; false negatives risk Kessler "
  "syndrome — runaway debris cascades that could deny entire orbital regimes for decades.")
p("<b>Orbit-Shield's value proposition:</b> ingest the same raw data, propagate trajectories ourselves, "
  "compute classical Pc using NASA's CARA method, then enhance the prediction with ML trained on historical "
  "CDM evolution. Operators get earlier, more accurate warnings and a clearer go/no-go signal.")

# ============ 2. STACK ============
h1("2. Technology Stack — Full Justification")
h2("Backend: Python 3.12 + FastAPI")
bul([
    "<b>Why Python:</b> Every orbital-mechanics library worth using (sgp4, astropy, skyfield, poliastro) is Python-first. ML stack is Python. No need for two languages.",
    "<b>Why FastAPI over Flask/Django:</b> Async I/O native (we ingest from many external APIs in parallel), automatic OpenAPI generation, Pydantic validation, type hints throughout. ~10x faster than Flask for I/O-bound work.",
    "<b>Why Python 3.12:</b> Per-interpreter GIL improvements + better asyncio. Pinned to <code>&gt;=3.12,&lt;3.14</code>.",
])
h2("Database: PostgreSQL + TimescaleDB")
bul([
    "<b>Why PostgreSQL:</b> ACID, mature ARRAY type (we store NORAD ID lists), JSONB for raw CDM blobs, PostGIS-ready if we add geo features.",
    "<b>Why TimescaleDB:</b> CDM history is time-series — same conjunction gets dozens of CDMs over hours/days as TCA approaches. Hypertables auto-partition by time, queries on recent data stay fast at 100M+ rows.",
    "<b>Migrations: Alembic.</b> Same team as SQLAlchemy. <code>alembic revision --autogenerate</code> diffs models against DB.",
])
h2("Async + Sync Split")
p("FastAPI uses <b>asyncpg</b> (async). Celery workers use <b>psycopg2</b> (sync). Both connect to the same DB. "
  "We expose two URLs in config: <code>database_url</code> (asyncpg) and <code>database_url_sync</code> "
  "(psycopg2, derived by stripping <code>+asyncpg</code> from the dialect).")
p("<b>Pitfall we hit:</b> Neon Postgres requires SSL. asyncpg URL needs <code>?ssl=require</code>; psycopg2 "
  "needs <code>?sslmode=require</code>. Same parameter name fails. We patch the sync URL conversion to also "
  "translate <code>ssl=require</code> &rarr; <code>sslmode=require</code>. (commit a0a6467)")
h2("Task Queue: Celery + Redis")
bul([
    "<b>Why Celery:</b> Periodic ingestion tasks (every 6h fetch CelesTrak TLEs, every 1h fetch CDMs). Mature, battle-tested.",
    "<b>Why Redis broker:</b> Lower operational overhead than RabbitMQ. Doubles as cache for space weather data.",
    "<b>Beat scheduler:</b> Separate process from workers. Single-instance, sends jobs at fixed cron-like intervals.",
])
h2("Frontend: React 19 + TypeScript + Vite")
bul([
    "<b>Why React 19:</b> Server Components not needed (Vercel static). New use() hook + concurrent features useful for streaming Cesium data.",
    "<b>Why Vite over CRA:</b> CRA is unmaintained. Vite cold start ~200ms vs 8s. Native ESM dev server.",
    "<b>Why TypeScript:</b> 22-feature ML vectors are easy to corrupt. Types catch field-mismatch bugs at compile.",
    "<b>Why Tailwind v4 + custom CSS:</b> Tailwind for layout primitives, custom CSS variables (--os-*) for the design system tokens.",
    "<b>State: Zustand.</b> Redux is overkill; Context causes re-renders. Zustand stores selector subscriptions.",
    "<b>Data fetching: TanStack Query.</b> Background refetch, request dedup, cache invalidation — all the things you'd hand-write.",
])
h2("3D Globe: CesiumJS + Resium")
bul([
    "<b>Why Cesium:</b> Industry-standard for satellite/space visualization. Jet Propulsion Lab uses it. Handles WGS84 ellipsoid math, terrain, lighting models.",
    "<b>Why Resium:</b> React bindings for Cesium. Lets us use JSX <code>&lt;Entity&gt;</code> instead of imperative <code>viewer.entities.add()</code>.",
    "<b>Imagery: Esri World Imagery.</b> Free for non-commercial. Looks better than default Bing Maps tiles.",
    "<b>Performance:</b> 15,000+ objects rendered as <code>PointPrimitiveCollection</code> (single GPU draw call) instead of individual entities.",
])

# ============ 3. ARCHITECTURE ============
h1("3. System Architecture")
p("Five-layer pipeline, each independently deployable:")
tbl([
    ["Layer", "Components", "Purpose"],
    ["Ingestion", "Celery workers (CelesTrak, Space-Track, NOAA)", "Fetch TLEs, CDMs, space weather"],
    ["Storage", "Postgres + TimescaleDB, Redis", "Persist catalog, history, hot cache"],
    ["Compute", "SGP4 propagator, k-d tree screener, Pc engine", "Find encounters, compute classical Pc"],
    ["ML", "XGBoost models, feature builders", "Enhance Pc predictions"],
    ["API", "FastAPI REST endpoints", "Serve dashboard"],
    ["Frontend", "React + Cesium SPA", "Visualize, alert, drill down"],
], widths=[0.9*inch, 2.4*inch, 3.2*inch])

h2("Data Flow (single conjunction, end-to-end)")
code("""1. CelesTrak fetcher pulls 15,000 TLEs every 6h (Celery task fetch_celestrak_tles)
2. TLEs upserted into satellites + orbital_elements tables
3. Screening task picks pairs whose perigee/apogee overlap (cheap pre-filter)
4. SGP4 propagates each pair forward 7 days @ 60s steps
5. k-d tree (scipy.spatial.cKDTree) finds positions within 5 km radius
6. Numerical TCA root-finding refines closest-approach time
7. Classical Pc computed via B-plane 2D Gaussian integration (NASA CARA)
8. ML inference: XGBoost classifier predicts P(Pc > 1e-4) from 22 features
9. Both stored on conjunctions row (pc_classical, pc_ml)
10. Frontend polls /api/conjunctions, renders sorted by max(pc_ml, pc_classical)""")

# ============ 4. DOMAIN MATH ============
h1("4. Orbital Mechanics — What You Should Be Able to Explain")
h2("TLE format")
p("Two-Line Element set. Compact mean-element representation of an orbit. NASA/NORAD format from the 1960s. "
  "Each line is exactly 69 chars. Encodes: epoch, inclination, RAAN, eccentricity, argument of perigee, "
  "mean anomaly, mean motion, drag term (BSTAR). <b>Critical limitation:</b> no covariance information.")
h2("SGP4")
p("Simplified General Perturbations model 4. Analytical propagator that takes a TLE and computes position/velocity "
  "at any time. Accounts for Earth oblateness (J2, J3, J4), atmospheric drag, lunisolar perturbations. Accurate "
  "to ~1 km within a few days, degrades fast beyond a week. We use the <code>sgp4</code> Python library "
  "(C-extension wrapping the canonical Vallado reference implementation).")
h2("Reference Frames")
p("SGP4 outputs are in <b>TEME</b> (True Equator Mean Equinox of date). Inertial but tied to time-varying equator. "
  "We convert to <b>GCRS</b> (Geocentric Celestial Reference System) for output via astropy. For visualization, "
  "GCRS &rarr; ITRS (Earth-fixed) &rarr; geodetic lat/lon/alt.")
h2("Conjunction Screening")
p("We don't compare every pair (15k * 15k = 225M pairs &times; 10k timesteps = infeasible). Three-stage filter:")
bul([
    "<b>Stage 1 — perigee/apogee overlap:</b> Two orbits can only intersect if their altitude bands overlap. O(N) check.",
    "<b>Stage 2 — inclination:</b> If inclinations differ a lot, they only intersect at specific geometries.",
    "<b>Stage 3 — k-d tree spatial search:</b> At each timestep, build a k-d tree of all positions. Query each point for neighbors within 5 km.",
])
h2("Classical Pc — B-plane Method (NASA CARA)")
p("At time of closest approach (TCA), construct the <b>B-plane</b>: a 2D plane perpendicular to the relative "
  "velocity vector, with origin at the primary object. Project both covariance ellipsoids onto this plane "
  "(they sum into one combined 2D Gaussian). Pc is the probability mass of that Gaussian inside a circle "
  "of radius = sum of the two object radii.")
p("<b>Two computation modes:</b>")
bul([
    "<b>Linearized (Alfano):</b> When R / &sigma;<sub>min</sub> &lt; 0.1, use closed-form approximation. Fast.",
    "<b>Numerical (scipy dblquad):</b> Edge cases. Slower but correct.",
])
h2("Where TLE Covariance Comes From (We Don't Get It)")
p("This is the dirty secret of free orbital data. TLEs ship without uncertainty. We estimate covariance three ways "
  "in priority order:")
bul([
    "<b>1. CDM data (best):</b> If the conjunction has a CDM from Space-Track, use the full 6&times;6 covariance.",
    "<b>2. ML prediction:</b> XGBRegressor trained on historical TLE-vs-truth divergence. Input: orbital elements + object metadata. Output: log&sigma;.",
    "<b>3. TLE ensemble:</b> Compare 3+ recent TLEs for same object, derive empirical scatter.",
    "<b>4. Altitude default:</b> Last resort. LEO=1km, MEO=5km, GEO=10km isotropic.",
])

# ============ 5. ML ============
h1("5. ML Pipeline — Deep Dive")
h2("Why XGBoost, Not Deep Learning?")
bul([
    "<b>Tabular data, modest size:</b> ~100k labeled CDMs at peak. Trees outperform NNs on tabular &lt; 1M rows (Grinsztajn et al. 2022).",
    "<b>Calibrated probabilities:</b> Operators care that 1e-4 actually means 1 in 10,000. XGBoost with isotonic calibration > NN softmax.",
    "<b>Inference speed:</b> Single conjunction prediction in &lt;1 ms. Critical for real-time dashboard.",
    "<b>Feature importance:</b> Shows operators <i>why</i> the model is alerting (regulatory + trust).",
    "<b>No GPU needed:</b> Cheap deployment.",
])
h2("Two Models")
tbl([
    ["Model", "Algorithm", "Features", "Target", "Use"],
    ["CovarianceEstimator", "XGBRegressor", "14 orbital", "log&#8321;&#8320;(&sigma;)", "Fill missing CDM covariance"],
    ["ConjunctionRiskClassifier", "XGBClassifier", "22 encounter", "P(Pc &gt; 1e-4)", "Maneuver-or-not decision"],
], widths=[1.6*inch, 1.1*inch, 1.0*inch, 0.9*inch, 1.5*inch])

h3("CovarianceEstimator — 14 features")
code("""mean_motion, eccentricity, inclination, raan, arg_perigee,
mean_anomaly, bstar, perigee_alt, apogee_alt, semi_major_axis,
period_min, rcs_size_encoded, object_type_encoded, age_days""")
p("<b>Hyperparameters:</b> n_estimators=200, max_depth=6, learning_rate=0.05, "
  "subsample=0.8, colsample_bytree=0.8. Standard tabular defaults from XGBoost docs.")
p("<b>Training data fallback chain:</b> real TLE-vs-precise-ephemeris pairs (best) &rarr; synthetic "
  "(altitude + drag + age &rarr; expected error). Current production: synthetic (R&sup2; 0.87 on held-out).")

h3("ConjunctionRiskClassifier — 22 features")
code("""# Encounter geometry (5)
miss_distance_km, relative_velocity_kms, b_plane_x, b_plane_y, approach_angle_deg
# Primary orbit (6)
pri_mean_motion, pri_eccentricity, pri_inclination,
pri_perigee_alt, pri_apogee_alt, pri_bstar
# Secondary orbit (6)
sec_mean_motion, sec_eccentricity, sec_inclination,
sec_perigee_alt, sec_apogee_alt, sec_bstar
# Covariance (3)
combined_sigma_km, sigma_ratio, mahalanobis_distance
# Space weather (2)
solar_flux_f107, geomagnetic_kp""")
p("<b>Why these 22:</b> Distilled from FAA / NASA conjunction analysis literature. Geometry features capture "
  "the encounter; orbital features capture how 'predictable' each object is; covariance features capture "
  "uncertainty; weather captures atmospheric drag (relevant for LEO &lt; 600 km).")
p("<b>Hyperparameters:</b> n_estimators=300, max_depth=5, learning_rate=0.1, scale_pos_weight=10 (high-Pc events "
  "are ~10x rarer). Class imbalance is the real challenge — most encounters are benign.")
p("<b>Metrics achieved:</b> Synthetic AUC 0.9999, F1 0.9716 (overfit-looking; real CDMs needed for honest numbers). "
  "Production retrain pending paired CDM + truth-state dataset.")

h2("Feature Engineering Modules")
bul([
    "<code>features/orbital.py</code> — extracts 14 sat features from a TLE row.",
    "<code>features/conjunction.py</code> — assembles 22 encounter features from primary + secondary + screening output.",
    "<code>features/weather.py</code> — pulls F10.7 and Kp from Redis (NOAA-sourced, 30-min refresh).",
])
h2("Inference Engine")
p("<code>MLInferenceEngine</code> in <code>inference.py</code> orchestrates: load model from registry &rarr; build feature "
  "vector &rarr; predict &rarr; return Pc + confidence + feature importances. Models cached in memory after first load.")
h2("Model Registry")
p("<code>registry.py</code> saves models as <code>model_name.joblib</code> + <code>model_name.meta.json</code>. "
  "Meta tracks: training timestamp, dataset hash, metrics, feature schema. Loading checks schema compatibility "
  "(refuses to load if features changed).")

# ============ 6. INFRA ============
h1("6. Deployment &amp; Infrastructure")
h2("Why Fly.io for Backend")
bul([
    "<b>Multi-process apps:</b> One <code>fly.toml</code> defines three process groups (app/worker/beat) from one image. Heroku/Render charge per process.",
    "<b>Volumes &amp; private networking:</b> When we add ML model persistence, mount Fly volumes; processes talk over WireGuard mesh.",
    "<b>Docker-native:</b> Same image runs locally and in prod. No platform-specific buildpacks.",
    "<b>Generous free tier:</b> 3 shared-cpu-1x VMs free; we use exactly 3.",
])
h2("Why Vercel for Frontend")
bul([
    "<b>Static SPA + edge cache:</b> Vite build output is plain HTML/JS/CSS. CDN edge serves in &lt;50ms globally.",
    "<b>Preview deploys:</b> Every PR gets unique URL.",
    "<b>Rewrites:</b> <code>/api/*</code> proxied to Fly so we avoid CORS.",
])
h2("Why Neon for Postgres")
bul([
    "<b>Serverless Postgres:</b> Scales to zero. Free tier 0.5 GB.",
    "<b>Branching:</b> Like Git for databases. Useful for ML experiments without polluting prod.",
    "<b>SSL only:</b> Forces secure connections (which caused our sslmode/ssl bug).",
])
h2("Why Upstash for Redis")
bul([
    "<b>Pay-per-request:</b> Free tier 10k commands/day. Celery broker traffic fits easily.",
    "<b>TLS by default:</b> <code>rediss://</code> URLs.",
    "<b>Edge compatible:</b> Could move some work to Vercel Edge later.",
])

h2("CI/CD")
bul([
    "GitHub Actions runs pytest + frontend build on every push (workflow file pending push — needs <code>workflow</code> OAuth scope).",
    "Vercel auto-deploys on push to main.",
    "Fly deploys are manual via <code>flyctl deploy</code> (intentional — DB migrations need ordering).",
])

# ============ 7. ALERTS ============
h1("7. Alerts System Design")
h2("Data Model")
code("""class AlertConfig:
    id: int
    user_email: str
    watched_norad_ids: list[int]  # PostgreSQL ARRAY
    pc_threshold: float           # default 1e-4
    miss_distance_threshold_km: float  # default 5.0
    enabled: bool
    created_at, updated_at""")

h2("Evaluation")
p("Periodic Celery task scans <code>conjunctions</code> table for rows where:")
bul([
    "<code>tca</code> within next 72 hours",
    "<code>primary_norad_id</code> or <code>secondary_norad_id</code> in any active alert config's watched list",
    "<code>max(pc_ml, pc_classical) &ge; pc_threshold</code> OR <code>miss_distance_km &le; miss_distance_threshold_km</code>",
])
p("Matches go to a <code>notifications_outbox</code> table (idempotent — same conjunction won't double-alert).")

h2("Notification Channels — Recommendation")
tbl([
    ["Channel", "Free tier", "Why"],
    ["Resend", "3,000/mo, 100/day", "Best DX, React Email templates, modern API"],
    ["SendGrid", "100/day", "Industry standard, larger templates"],
    ["Slack webhook", "unlimited", "Internal team alerts, no signup"],
    ["Discord webhook", "unlimited", "Same as Slack, gamer-friendly"],
    ["AWS SES", "62k/mo", "Cheapest at scale, harder setup"],
], widths=[1.2*inch, 1.4*inch, 3.4*inch])
p("<b>Customer model in real life:</b> Operators (SpaceX, Planet, Maxar, OneWeb) self-register via dashboard, "
  "input their NORAD IDs + on-call email/Slack. We don't ship pre-loaded with operator emails — that would be a "
  "regulatory minefield (CAN-SPAM, GDPR consent).")

# ============ 8. INCIDENTS ============
h1("8. Bugs We Hit &amp; Fixed (Story-Worthy)")
issues = [
    ("Docker editable install order",
     "<code>pip install -e</code> ran before <code>COPY src</code>, leaving the install pointing nowhere. Alembic crashed with <i>ModuleNotFoundError: No module named 'src'</i>.",
     "Added <code>ENV PYTHONPATH=/app</code> as a safety net so imports work regardless of editable-install state. (commit dd19ca4)"),
    ("Postgres volume credentials",
     "Old <code>collider</code> project pgdata volume persisted across rebrand. New <code>orbit_shield</code> user couldn't auth: <i>password authentication failed for user 'orbit_shield'</i>.",
     "<code>docker compose down -v</code> nuked volumes; fresh init from <code>.env</code>. (Local-only, didn't affect prod.)"),
    ("OAuth workflow scope",
     "Push rejected: <i>refusing to allow an OAuth App to create or update workflow .github/workflows/test.yml without workflow scope</i>.",
     "<code>git reset --soft HEAD~1</code>, dropped the workflow file from staging, recommitted infra without it. Workflow file deferred until <code>gh auth refresh -s workflow</code>."),
    ("Space-Track column name",
     "CDM backfill returned 14 records but upserted 0. Dumping the response: <code>{'error': 'COLUMN [creation_date] DOES NOT EXIST FOR TABLE [basicspacedata_cdm_public]'}</code>. Each window returned a single error blob the script counted as a record.",
     "Space-Track uses <code>CREATED</code>, not <code>CREATION_DATE</code>, for the cdm_public class. Fixed both query builders. Backfill then ingested 1,665 CDMs in 14 days. (commit ec24805)"),
    ("Async/sync SSL parameter mismatch",
     "Neon required SSL. asyncpg accepts <code>?ssl=require</code>; psycopg2 accepts <code>?sslmode=require</code>. Same URL can't satisfy both. API returned 500 on every DB-backed route.",
     "Patched <code>database_url_sync</code> property to translate <code>ssl=require</code> &rarr; <code>sslmode=require</code> when stripping the asyncpg dialect. (commit a0a6467)"),
    ("Vercel rewrite stripping prefix",
     "Frontend hit <code>/api/conjunctions</code>, Vercel rewrote to Fly's <code>/conjunctions</code> &mdash; FastAPI routes mount under <code>/api</code>, so all 404'd. Globe and timeline stayed empty.",
     "Changed destination to preserve prefix: <code>https://orbit-shield-api.fly.dev/api/:path*</code>. (commit 75150c3)"),
    ("Empty positions endpoint",
     "<code>/api/positions</code> returned <code>{count: 0, positions: []}</code> &mdash; CDM upserts only created minimal Satellite rows (NORAD ID + name), no TLE data to propagate.",
     "Triggered <code>fetch_celestrak_tles</code> Celery task synchronously. 15,706 sats with elements; 15,204 propagating successfully."),
    ("Models on wrong machine",
     "Trained models on the Celery worker machine, but the API runs on a separate Fly machine. Models on ephemeral disk &rarr; not reachable.",
     "<b>Open issue:</b> need a Fly volume mounted across all three process groups, OR ship models in the Docker image. Current: re-train on the app machine after each deploy. Doesn't scale."),
]
for title, problem, fix in issues:
    h3(title)
    p(f"<b>Problem:</b> {problem}")
    p(f"<b>Fix:</b> {fix}")
    sp(4)

# ============ 9. DESIGN DECISIONS ============
h1("9. Design Decisions You Should Defend")
decisions = [
    ("Python end-to-end vs. Rust/Go for the compute path",
     "Faster engineering velocity wins for a portfolio piece. SGP4 + scipy are already C-extension-fast at the hot loops. If we hit 500k objects, port the screener to Rust."),
    ("XGBoost vs. neural net",
     "Tabular data + needs interpretability + small dataset. NN would overfit and be harder to explain to a regulator. Revisit if we get 1M+ labeled CDMs."),
    ("Monolithic FastAPI vs. microservices",
     "One repo, one deploy. Microservices cost is real. We can split ingestion vs. API later if scaling demands it."),
    ("CesiumJS vs. three.js or globe.gl",
     "Cesium ships with WGS84 and time animation. three.js would mean writing all that. Bundle size cost (~2MB) acceptable for a power tool."),
    ("Fly.io vs. AWS",
     "AWS = weeks of setup. Fly = one fly.toml, deployed in 5 min. When we need VPC, IAM, or compliance, migrate. Premature optimization to start there."),
    ("Storing raw CDM JSONB blob",
     "We parse out hot fields (Pc, miss_distance, TCA) into typed columns, but keep the full raw CDM in JSONB. Lets us re-extract fields later without re-fetching. ~5KB per row, cheap."),
    ("ML enhances, doesn't replace, classical Pc",
     "Classical method is interpretable and physics-based. Regulators trust it. ML is a second opinion. We show both in the UI; operators decide."),
]
for title, body in decisions:
    h3(title)
    p(body)

# ============ 10. WHAT'S DONE / PENDING ============
h1("10. Project Status — As of 2026-04-24")
h2("Completed")
bul([
    "<b>Phase 1:</b> 5 ORM models, 4 ingestion clients (CelesTrak, Space-Track, SOCRATES, NOAA), Celery periodic tasks, Alembic schema.",
    "<b>Phase 2:</b> SGP4 propagation engine, k-d tree screening with 5 km threshold, perigee/apogee + inclination pre-filters.",
    "<b>Phase 3:</b> Classical Pc via B-plane (linearized + numerical), covariance fallback chain, conjunction enrichment.",
    "<b>Phase 4:</b> XGBoost CovarianceEstimator + ConjunctionRiskClassifier, full feature engineering modules, model registry, MLInferenceEngine.",
    "<b>Phase 5:</b> 7 REST routes (satellites, conjunctions, propagate, positions, ML compare, alerts CRUD), 102 tests passing.",
    "<b>Phase 6:</b> React + CesiumJS dashboard with filter rail, conjunction timeline, event detail drawer, alert config form.",
    "<b>Infra:</b> Docker Compose (6 services), Fly.io 3-process deploy, Vercel frontend, Neon Postgres, Upstash Redis. End-to-end live.",
    "<b>Real data:</b> 15,706 satellites, 15,204 live propagating, 1,665 CDMs ingested.",
])
h2("Pending (in priority order)")
bul([
    "<b>1.</b> Persist trained ML models (Fly volume or bake into image).",
    "<b>2.</b> Backfill <code>pc_ml</code> on existing 1,665 conjunctions (script exists, needs to run).",
    "<b>3.</b> Wire Resend for actual alert emails (~1 hour).",
    "<b>4.</b> Enable Celery Beat schedule in production (catalog refresh every 6h, CDM fetch every 1h).",
    "<b>5.</b> Push <code>.github/workflows/test.yml</code> after <code>gh auth refresh -s workflow</code>.",
    "<b>6.</b> Custom domain (<code>orbit-shield.app</code> or similar).",
    "<b>7.</b> Train ConjunctionRiskClassifier on real CDMs once we have paired truth-state data (currently synthetic).",
])

# ============ 11. INTERVIEW Q&A ============
h1("11. Likely Interview Questions")
qa = [
    ("How does SGP4 differ from numerical integration?",
     "SGP4 is analytical: closed-form expansions of secular and periodic perturbations from a TLE's mean elements. No timestep integration — just plug t into formulas. Trade-off: fast (microseconds per propagation) but accuracy degrades beyond ~1 week. Numerical integrators (RK4, DOPRI8) handle higher-fidelity force models but need fresh state vectors and are 100-1000x slower."),
    ("Why can two TLEs of the same satellite disagree?",
     "TLEs are mean elements derived from a fit window of observations. Different fit windows + different observers (Space-Track vs. CelesTrak) = different mean states even at the same epoch. Empirically TLE position error is often 1-5 km."),
    ("Walk me through how Pc gets computed.",
     "At TCA, build the B-plane (perpendicular to relative velocity). Project both objects' position covariance ellipsoids onto it; sum into combined 2D Gaussian. Object miss-distance vector projected onto plane = mean offset. Pc = integral of that Gaussian over a circle of radius (R1+R2). Linearized form when ratio of HBR to position uncertainty is small; otherwise numerical."),
    ("Why XGBoost over a neural net here?",
     "Tabular features (22), sample size in tens-of-thousands, need calibrated probabilities + interpretability. XGBoost dominates this regime per Grinsztajn 2022. NN would need way more data and would be harder to explain to operators or regulators."),
    ("How do you handle class imbalance?",
     "<code>scale_pos_weight</code> in XGBoost — ratio of negatives to positives. We also use stratified train/test split and monitor PR-AUC, not just ROC-AUC, since ROC-AUC is misleading on imbalanced sets."),
    ("What if Space-Track goes down?",
     "We have CelesTrak as a backup TLE source. CDMs are Space-Track-only (the data isn't elsewhere) — we'd lose the ability to refresh recent encounters but historical data continues to serve."),
    ("How do you scale this to a million objects?",
     "(1) Move screening to Rust or move the k-d tree to a GPU library like RAPIDS cuML. (2) Shard by orbital regime — LEO and GEO never conjunct, parallel workers per band. (3) Switch from 60s timesteps to adaptive: coarse where orbits are far, fine near approach."),
    ("What's the latency budget?",
     "End-to-end: TLE arrives &rarr; conjunction shows in UI in &lt;5 minutes. Screening of 15k objects takes ~30s on one core. ML inference is &lt;1ms per pair. Most time is fetching from external APIs."),
    ("How do you test orbital code?",
     "Two layers: (1) unit tests against published CCSDS test vectors — known input states, known output positions, deterministic. (2) integration tests that propagate ISS for 7 days and check error growth bounds. We don't compare to ground truth in CI (would need ephemeris files)."),
]
for q, a in qa:
    h3("Q: " + q)
    p(a)
    sp(4)

# ============ 12. OPS RUNBOOK ============
h1("12. Operations Runbook")
h2("Live URLs")
tbl([
    ["Service", "URL"],
    ["Frontend", "https://frontend-black-gamma-62.vercel.app"],
    ["API", "https://orbit-shield-api.fly.dev"],
    ["API health", "https://orbit-shield-api.fly.dev/health"],
    ["GitHub", "https://github.com/DecodeAndCode/Orbit-Shield"],
], widths=[1.4*inch, 5.0*inch])
h2("Common Commands")
code("""# Local dev
docker compose up -d                            # Postgres + Redis + API + worker + frontend
cd backend && pytest                             # Run test suite
cd frontend && npm run dev                       # Vite dev server

# Production
flyctl deploy --app orbit-shield-api            # Backend deploy
vercel --prod --yes --scope decodeandcodes-projects  # Frontend deploy
flyctl secrets set KEY=value --app orbit-shield-api  # Update secret
flyctl ssh console --app orbit-shield-api -C "alembic upgrade head"  # Migrate Neon
flyctl logs --app orbit-shield-api              # Tail logs

# Data refresh
flyctl ssh console -C "python scripts/download_cdms.py --days 14"
flyctl ssh console -C "python -m src.ml.training.train_conjunction"
flyctl ssh console -C "python scripts/backfill_ml.py" """)

doc.build(story)
print(f"WROTE {OUT}")
