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
import {
  useColliderStore,
  altKmToRegime,
  pcToRiskLevel,
} from "../stores/colliderStore";

function riskCesiumColor(pc: number | null): Color {
  if (pc === null) return Color.GRAY;
  if (pc >= 1e-4) return Color.fromCssColorString("#ef4444").withAlpha(0.95);
  if (pc >= 1e-6) return Color.fromCssColorString("#f59e0b").withAlpha(0.9);
  return Color.fromCssColorString("#22c55e").withAlpha(0.85);
}

function regimeColor(altKm: number): Color {
  if (altKm < 2000) return Color.fromCssColorString("#22d3ee").withAlpha(0.9);
  if (altKm < 35000) return Color.fromCssColorString("#fb923c").withAlpha(0.9);
  if (altKm < 36500) return Color.fromCssColorString("#c084fc").withAlpha(0.9);
  return Color.fromCssColorString("#f472b6").withAlpha(0.9);
}

export default function GlobeView() {
  const { data: conjunctions } = useConjunctions();
  const { data: catalog } = useCatalogPositions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);
  const regimes = useColliderStore((s) => s.regimes);
  const activeRisks = useColliderStore((s) => s.riskLevels);
  const showPointCloud = useColliderStore((s) => s.showPointCloud);
  const showOrbits = useColliderStore((s) => s.showOrbits);
  const viewerRef = useRef<CesiumComponentRef<CesiumViewer> | null>(null);
  const pointsRef = useRef<PointPrimitiveCollection | null>(null);

  const noradIds = useMemo(() => {
    if (!conjunctions || !showOrbits) return [];
    const ids = new Set<number>();
    for (const c of conjunctions.slice(0, 10)) {
      ids.add(c.primary_norad_id);
      ids.add(c.secondary_norad_id);
    }
    return Array.from(ids);
  }, [conjunctions, showOrbits]);

  const { data: propagation } = usePropagate(noradIds, 2, 1);
  const selectedConj = conjunctions?.find((c) => c.id === selectedId);

  // Esri World Imagery — natural Earth satellite tiles, no auth required.
  const baseLayer = useMemo(
    () =>
      new ImageryLayer(
        new UrlTemplateImageryProvider({
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          credit:
            "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
          maximumLevel: 18,
        }),
        {
          brightness: 0.9,
          contrast: 1.1,
          saturation: 1.05,
        }
      ),
    []
  );

  const terrainProvider = useMemo(() => new EllipsoidTerrainProvider(), []);

  // Point cloud render — imperative, GPU-batched via PointPrimitiveCollection.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    if (pointsRef.current) {
      viewer.scene.primitives.remove(pointsRef.current);
      pointsRef.current = null;
    }
    if (!catalog || !showPointCloud) return;

    const collection = new PointPrimitiveCollection();
    for (const p of catalog.positions) {
      const regime = altKmToRegime(p.alt_km);
      if (!regimes.has(regime)) continue;
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
  }, [catalog, regimes, showPointCloud]);

  // Dark space backdrop + subtle atmosphere.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;
    const scene = viewer.scene;
    scene.backgroundColor = Color.fromCssColorString("#05080f");
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.brightnessShift = -0.3;
      scene.skyAtmosphere.saturationShift = -0.1;
    }
    scene.globe.enableLighting = true;
    // Soften terrain shading so imagery reads well at night side.
    scene.globe.atmosphereLightIntensity = 3.0;
  }, []);

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
      fullscreenButton={false}
      baseLayer={baseLayer}
      terrainProvider={terrainProvider}
      style={{ height: "100%", width: "100%" }}
    >
      {showOrbits &&
        propagation?.map((sat) => {
          if (sat.positions.length < 2) return null;

          const isSelected =
            selectedConj &&
            (sat.norad_id === selectedConj.primary_norad_id ||
              sat.norad_id === selectedConj.secondary_norad_id);

          const conjForSat = conjunctions?.find(
            (c) =>
              c.primary_norad_id === sat.norad_id ||
              c.secondary_norad_id === sat.norad_id
          );
          const pc = conjForSat?.pc_classical ?? null;
          const risk = pcToRiskLevel(pc);
          if (!activeRisks.has(risk)) return null;

          const color = riskCesiumColor(pc);
          const width = isSelected ? 3 : 1.5;

          const positions = sat.positions.map((p) =>
            Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000)
          );

          return (
            <Entity key={sat.norad_id} name={`Satellite #${sat.norad_id}`}>
              <PolylineGraphics
                positions={positions}
                width={width}
                material={
                  isSelected ? Color.fromCssColorString("#22d3ee") : color
                }
              />
            </Entity>
          );
        })}
    </Viewer>
  );
}
