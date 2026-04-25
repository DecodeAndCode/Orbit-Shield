"""Quick script to check database status."""
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://collider:collider@localhost:5432/collider")
with engine.connect() as c:
    sats = c.execute(text("SELECT count(*) FROM satellites")).scalar()
    tles = c.execute(text("SELECT count(*) FROM orbital_elements")).scalar()
    conjs = c.execute(text("SELECT count(*) FROM conjunctions WHERE screening_source = 'COMPUTED'")).scalar()
    print(f"Satellites: {sats}")
    print(f"TLEs: {tles}")
    print(f"Computed conjunctions: {conjs}")

    if conjs > 0:
        rows = c.execute(text(
            "SELECT primary_norad_id, secondary_norad_id, tca, miss_distance_km, relative_velocity_kms "
            "FROM conjunctions WHERE screening_source = 'COMPUTED' ORDER BY miss_distance_km LIMIT 10"
        )).fetchall()
        print("\nTop 10 closest approaches:")
        for r in rows:
            print(f"  NORAD {r[0]} vs {r[1]} | TCA: {r[2]} | Miss: {r[3]:.2f} km | RelVel: {r[4]:.2f} km/s")
