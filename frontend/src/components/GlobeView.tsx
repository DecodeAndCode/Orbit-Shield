import { useEffect, useMemo, useRef } from "react";
import { Viewer, Entity, PolylineGraphics, type CesiumComponentRef } from "resium";
import {
  Cartesian3,
  Color,
  PointPrimitiveCollection,
  UrlTemplateImageryProvider,
  ImageryLayer,
  EllipsoidTerrainProvider,
  Viewer as CesiumViewer,
} from "cesium";
import {
  usePropagate,
  useConjunctions,
  useCatalogPositions,
} from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

function riskCesiumColor(pc: number | null): Color {
  if (pc === null) return Color.GRAY;
  if (pc >= 1e-4) return Color.RED.withAlpha(0.9);
  if (pc >= 1e-6) return Color.YELLOW.withAlpha(0.8);
  return Color.GREEN.withAlpha(0.7);
}

function regimeColor(altKm: number): Color {
  if (altKm < 2000) return Color.fromCssColorString("#4fc3f7").withAlpha(0.85); // LEO cyan
  if (altKm < 35000) return Color.fromCssColorString("#ffb74d").withAlpha(0.85); // MEO orange
  return Color.fromCssColorString("#ba68c8").withAlpha(0.85); // GEO purple
}

export default function GlobeView() {
  const { data: conjunctions } = useConjunctions();
  const { data: catalog } = useCatalogPositions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);
  const viewerRef = useRef<CesiumComponentRef<CesiumViewer> | null>(null);
  const pointsRef = useRef<PointPrimitiveCollection | null>(null);

  const noradIds = useMemo(() => {
    if (!conjunctions) return [];
    const ids = new Set<number>();
    for (const c of conjunctions.slice(0, 10)) {
      ids.add(c.primary_norad_id);
      ids.add(c.secondary_norad_id);
    }
    return Array.from(ids);
  }, [conjunctions]);

  const { data: propagation } = usePropagate(noradIds, 2, 1);
  const selectedConj = conjunctions?.find((c) => c.id === selectedId);

  const baseLayer = useMemo(
    () =>
      new ImageryLayer(
        new UrlTemplateImageryProvider({
          url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
          credit: "© OpenStreetMap contributors",
          maximumLevel: 18,
        }),
        {}
      ),
    []
  );

  const terrainProvider = useMemo(() => new EllipsoidTerrainProvider(), []);

  // Imperative point cloud render — 14k Entities would tank perf.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer || !catalog) return;

    if (pointsRef.current) {
      viewer.scene.primitives.remove(pointsRef.current);
      pointsRef.current = null;
    }

    const collection = new PointPrimitiveCollection();
    for (const p of catalog.positions) {
      collection.add({
        position: Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000),
        color: regimeColor(p.alt_km),
        pixelSize: 2.5,
        outlineWidth: 0,
      });
    }
    viewer.scene.primitives.add(collection);
    pointsRef.current = collection;

    return () => {
      if (pointsRef.current && !viewer.isDestroyed()) {
        viewer.scene.primitives.remove(pointsRef.current);
        pointsRef.current = null;
      }
    };
  }, [catalog]);

  return (
    <Viewer
      ref={viewerRef}
      full
      timeline={false}
      animation={false}
      homeButton={false}
      baseLayerPicker={false}
      navigationHelpButton={false}
      sceneModePicker={false}
      geocoder={false}
      selectionIndicator={false}
      infoBox={false}
      baseLayer={baseLayer}
      terrainProvider={terrainProvider}
      style={{ height: "100%", width: "100%" }}
    >
      {propagation?.map((sat) => {
        if (sat.positions.length < 2) return null;

        const isSelected =
          selectedConj &&
          (sat.norad_id === selectedConj.primary_norad_id ||
            sat.norad_id === selectedConj.secondary_norad_id);

        const pc = conjunctions?.find(
          (c) =>
            c.primary_norad_id === sat.norad_id ||
            c.secondary_norad_id === sat.norad_id
        )?.pc_classical;

        const color = riskCesiumColor(pc ?? null);
        const width = isSelected ? 3 : 1;

        const positions = sat.positions.map((p) =>
          Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000)
        );

        return (
          <Entity key={sat.norad_id} name={`Satellite #${sat.norad_id}`}>
            <PolylineGraphics
              positions={positions}
              width={width}
              material={isSelected ? Color.CYAN : color}
            />
          </Entity>
        );
      })}
    </Viewer>
  );
}
