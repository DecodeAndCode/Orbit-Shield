# Collider — Project Plan

## Project Name
**Collider** — ML-Enhanced Satellite Collision Avoidance System

## Inspiration
Wavefinder by Privateer — space situational awareness platform.

## Problem Statement
Even sub-centimeter space debris causes catastrophic damage at orbital velocities (~7.5 km/s in LEO). Current tracking systems (US Space Command's 18th SDS) only track objects >10 cm. NASA's CARA program handles conjunction assessment for ~4,000 active satellites, but:
- TLEs lack covariance/uncertainty data
- Classical Pc computation has known limitations
- No public real-time dashboard exists for researchers

## Goal
Build a system that ingests real-time orbital data, propagates trajectories, detects upcoming conjunctions, estimates collision probability with ML enhancement, and alerts operators hours/days before potential collisions.

## Scope (Realistic for Solo Dev)
- Focus on **tracked objects** (47,000+ in catalog), NOT sub-cm debris detection
- ML improves predictions for tracked-object conjunctions
- Sub-cm debris framed as future research direction

---

## 14-Week Roadmap

### Phase 0: Domain Study (Week 1)
- [ ] Study NASA CARA workflow: Tracking → Cataloging → Screening → CDM → Pc → Decision
- [ ] Understand TLE format, SGP4 propagation, TEME reference frame
- [ ] Read NASA CARA Handbook: `ntrs.nasa.gov/api/citations/20230002470`
- [ ] Explore CelesTrak SOCRATES documentation
- [ ] Study Alfano's collision probability papers

### Phase 1: Data Ingestion Pipeline (Weeks 2–3)
- [ ] Register Space-Track.org account
- [ ] Fetch ISS TLE from CelesTrak, propagate 24hr orbit (Milestone 1: "Hello Space")
- [ ] Build automated TLE/OMM ingestion from Space-Track + CelesTrak
- [ ] Ingest full catalog (~47,000 objects) into PostgreSQL
- [ ] Categorize objects: active satellite, debris, rocket body
- [ ] Set up daily update pipeline via Celery workers
- [ ] Pull SOCRATES conjunction reports (3x daily)

**Data Sources:**
| Source | Provides | Access |
|--------|----------|--------|
| Space-Track.org | Full catalog, TLEs/OMMs, CDMs | Free account |
| CelesTrak | TLEs, SOCRATES conjunction reports | No account needed |
| CelesTrak SOCRATES | Pre-computed conjunctions, 3x daily | Free |
| ESA DISCOSweb | Physical properties (mass, size, shape) | Academic account |
| NASA Open APIs | ISS position, solar activity | Free API key |
| NOAA Space Weather | Solar flux (F10.7), geomagnetic indices | Free |

### Phase 2: Orbit Propagation & Conjunction Screening (Weeks 3–5)
- [ ] SGP4 propagation for full catalog at configurable time steps
- [ ] Spatial filtering pipeline:
  1. Perigee/Apogee altitude overlap filter
  2. Orbital plane (inclination) filter
  3. Time-stepped k-d tree spatial indexing (scipy.spatial.cKDTree)
  4. Fine-grained TCA via numerical root-finding
- [ ] Screen with 5 km radius threshold
- [ ] Replicate at least one SOCRATES conjunction (Milestone 3)
- [ ] Validate miss distances against SOCRATES

### Phase 3: Collision Probability Computation (Weeks 5–7)
- [ ] Implement classical 2D Gaussian Pc (B-plane projection method, per NASA CARA)
- [ ] Handle covariance challenge — TLEs lack uncertainty info:
  - Estimate from sequential TLE comparisons
  - Pull CDM covariances from Space-Track for specific events
  - LeoLabs free tier for high-precision orbits with covariances
- [ ] Build conjunction event timeline with Pc values
- [ ] Compare computed Pc against SOCRATES maximum probability values

### Phase 4: ML Enhancement Layer (Weeks 7–11)
**Priority-ordered ML tasks:**

1. **Conjunction Evolution Prediction** (most feasible)
   - Input: Sequence of CDMs for an evolving event (Pc changing over days)
   - Output: Will Pc exceed maneuver threshold (~1e-4)?
   - Training data: 450,000+ historical CDMs (2015-2018) from NASA CARA
   - Models: LSTM/Transformer on CDM sequences, XGBoost baseline

2. **Orbit Propagation Correction** (high impact)
   - Input: Current orbital state + atmospheric/solar conditions
   - Output: Position correction residual on top of SGP4
   - Models: Neural ODE, Physics-Informed Neural Network (PINN)
   - Training data: Historical TLE sequences (new TLE = ground truth for previous propagation)

3. **TLE Covariance Estimation** (novel research direction)
   - Input: Object type, orbit regime, TLE age, fit span, drag coefficient, RCS
   - Output: Predicted 3x3 position covariance matrix
   - Training data: GPS satellites with laser ranging truth data

4. **Space Weather → Drag Impact** (complementary)
   - Predict atmospheric density corrections from solar flux & geomagnetic indices

- [ ] Feature engineering pipeline
- [ ] Train & evaluate models with wandb/mlflow tracking
- [ ] Compare ML Pc predictions vs. classical Pc

### Phase 5: Web Dashboard & Alert System (Weeks 10–14)
- [x] FastAPI backend serving propagation results, conjunction data, ML predictions
- [x] React + CesiumJS frontend:
  - [x] 3D globe view with orbits, color-coded conjunction risk
  - [x] Conjunction timeline sorted by Pc with countdown timers
  - [x] Event deep-dive: miss distance trend, Pc evolution, orbital geometry
  - [x] Alert configuration: thresholds, notification channels, watched satellites
  - [x] ML Insights panel: ML vs. classical Pc, confidence intervals
- [x] WebSocket real-time updates
- [ ] Email/Slack/Discord alert integration (deferred — Phase 6)

### Phase 6: Integration & Polish (Weeks 12–14)
- [ ] End-to-end testing with live data
- [ ] Documentation & README
- [ ] Performance optimization (batch propagation, caching)
- [ ] Deploy (Vercel frontend, cloud backend)

---

## Key Milestones (Demo Checkpoints)

| Milestone | Week | Deliverable |
|-----------|------|-------------|
| "Hello Space" | 2 | ISS TLE fetch → 24hr propagation → ground track plot |
| "Catalog Explorer" | 4 | Full catalog in DB, automated daily updates, object categorization |
| "First Conjunction" | 6 | Replicate SOCRATES conjunction, compute miss distance at TCA |
| "Risk Calculator" | 8 | Classical Pc computation, Pc timeline, SOCRATES validation |
| "ML Prototype" | 10 | Trained conjunction evolution model, comparison dashboard |
| "Full Dashboard" | 12 | React+CesiumJS app with live data, alerts, ML panel |
| "Ship It" | 14 | Deployed, documented, demo-ready |

---

## Open Questions / Decisions Needed
- Monorepo vs. separate frontend/backend repos?
- TimescaleDB vs. plain PostgreSQL for time-series?
- CesiumJS (heavyweight, best 3D) vs. Three.js + globe library (lighter)?
- How to handle rate limits on Space-Track API for full catalog updates?
