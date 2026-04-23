"""Build training examples from real CDM history + orbital elements.

Label = pc >= maneuver_threshold (1e-4 by default).
Features: 22-element vector matching CONJUNCTION_FEATURE_NAMES.

Because CDMs only give us scalar miss distance + relative speed + RTN
covariance (not the full relative position vector or both objects'
osculating states at TCA), we fill the vector-valued features with
physically-reasonable approximations:
  - relative_position_km ≈ [miss_distance, 0, 0]
  - relative_velocity_vec ≈ [0, relative_velocity, 0]  (perpendicular)
This means b-plane geometry features become constant, but the remaining
17 features (orbital elements, covariance magnitudes, weather) still
carry real signal — and the label Pc is the real CARA-computed value.
"""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import CDMHistory, Conjunction, OrbitalElement
from src.ml.features.conjunction import (
    CONJUNCTION_FEATURE_NAMES,
    extract_conjunction_features,
)

# Earth constants for perigee/apogee derivation
R_EARTH_KM = 6378.137
MU_EARTH = 398600.4418  # km^3/s^2

logger = logging.getLogger(__name__)

MANEUVER_THRESHOLD = 1e-4


def _latest_orbit_before(
    session: Session, norad_id: int, before
) -> OrbitalElement | None:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .where(OrbitalElement.epoch <= before)
        .order_by(OrbitalElement.epoch.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _rtn_cov_to_3x3(cov_dict: dict | None) -> np.ndarray | None:
    """Build 3x3 position covariance (km²) from CDM RTN lower-triangle."""
    if not cov_dict:
        return None
    try:
        cr_r = float(cov_dict.get("CR_R", 0.0))
        ct_r = float(cov_dict.get("CT_R", 0.0))
        ct_t = float(cov_dict.get("CT_T", 0.0))
        cn_r = float(cov_dict.get("CN_R", 0.0))
        cn_t = float(cov_dict.get("CN_T", 0.0))
        cn_n = float(cov_dict.get("CN_N", 0.0))
        if cr_r <= 0 and ct_t <= 0 and cn_n <= 0:
            return None
        # CDM covariance is in m². Convert to km² (divide by 1e6).
        return np.array(
            [
                [cr_r, ct_r, cn_r],
                [ct_r, ct_t, cn_t],
                [cn_r, cn_t, cn_n],
            ]
        ) / 1e6
    except (TypeError, ValueError):
        return None


def _orbit_to_features(orb: OrbitalElement | None) -> dict[str, float] | None:
    """Build the 6 fields extract_conjunction_features consumes from a TLE row."""
    if orb is None or orb.mean_motion is None:
        return None
    try:
        n = float(orb.mean_motion)  # rev/day
        ecc = float(orb.eccentricity or 0.0)
        inc = float(orb.inclination or 0.0)
        bstar = float(orb.bstar or 0.0)
        # Semi-major axis from mean motion (km).
        n_rad_s = n * 2 * np.pi / 86400.0
        if n_rad_s <= 0:
            return None
        a_km = (MU_EARTH / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)
        perigee_alt = a_km * (1 - ecc) - R_EARTH_KM
        apogee_alt = a_km * (1 + ecc) - R_EARTH_KM
        return {
            "mean_motion": n,
            "eccentricity": ecc,
            "inclination": inc,
            "perigee_alt_km": perigee_alt,
            "apogee_alt_km": apogee_alt,
            "bstar": bstar,
        }
    except (TypeError, ValueError):
        return None


def build_training_set(
    session: Session,
    threshold: float = MANEUVER_THRESHOLD,
    default_weather: dict[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) from CDMHistory joined with Conjunction + OrbitalElement.

    One row per CDM (so the same conjunction contributes multiple samples
    as new CDMs arrive — matches real-world training signal).
    """
    weather = default_weather or {"f107_flux": 150.0, "kp_index": 3.0}

    stmt = (
        select(CDMHistory, Conjunction)
        .join(Conjunction, CDMHistory.conjunction_id == Conjunction.id)
        .where(CDMHistory.pc.is_not(None))
        .where(CDMHistory.miss_distance_km.is_not(None))
    )
    rows = session.execute(stmt).all()
    logger.info(f"Found {len(rows)} labeled CDMs for training")

    X_list: list[list[float]] = []
    y_list: list[int] = []

    for cdm, conj in rows:
        pri_orb = _latest_orbit_before(session, conj.primary_norad_id, conj.tca)
        sec_orb = _latest_orbit_before(session, conj.secondary_norad_id, conj.tca)
        pri_feat = _orbit_to_features(pri_orb)
        sec_feat = _orbit_to_features(sec_orb)
        if pri_feat is None or sec_feat is None:
            continue  # skip — can't build orbital features without TLE

        miss = float(cdm.miss_distance_km)
        rel_v = float(conj.relative_velocity_kms or 7.5)  # LEO default

        # Placeholder 3D vectors consistent with scalar magnitudes.
        rel_pos = np.array([miss, 0.0, 0.0])
        rel_vel = np.array([0.0, rel_v, 0.0])

        pri_cov = _rtn_cov_to_3x3(cdm.primary_covariance)
        sec_cov = _rtn_cov_to_3x3(cdm.secondary_covariance)

        feats = extract_conjunction_features(
            miss_distance_km=miss,
            relative_velocity_kms=rel_v,
            relative_position_km=rel_pos,
            relative_velocity_vec=rel_vel,
            primary_features=pri_feat,
            secondary_features=sec_feat,
            primary_cov=pri_cov,
            secondary_cov=sec_cov,
            weather=weather,
        )
        X_list.append([feats[name] for name in CONJUNCTION_FEATURE_NAMES])
        y_list.append(1 if float(cdm.pc) >= threshold else 0)

    if not X_list:
        raise RuntimeError(
            "No usable CDM training rows — check orbital_elements coverage"
        )

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.int64)
    n_pos = int(y.sum())
    logger.info(
        f"Built {len(y)} training samples ({n_pos} positive, "
        f"{len(y) - n_pos} negative)"
    )
    return X, y
