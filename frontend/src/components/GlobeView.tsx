import { useEffect, useMemo, useRef } from "react";
import {
  Viewer,
  Entity,
  PolylineGraphics,
  PointGraphics,
  LabelGraphics,
  type CesiumComponentRef,
} from "resium";
import {
  Cartesian3,
  Color,
  PointPrimitiveCollection,
  UrlTemplateImageryProvider,
  ImageryLayer,
  EllipsoidTerrainProvider,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Cartographic,
  Math as CMath,
  LabelStyle,
  VerticalOrigin,
  Cartesian2,
  HeightReference,
  CallbackProperty,
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
  const setHoveredSat = useColliderStore((s) => s.setHoveredSat);
  const focusNoradId = useColliderStore((s) => s.focusNoradId);
  const focusOnSat = useColliderStore((s) => s.focusOnSat);
  const viewerRef = useRef<CesiumComponentRef<CesiumViewer> | null>(null);
  const pointsRef = useRef<PointPrimitiveCollection | null>(null);
  const catalogIndex = useRef<Map<number, { lat: number; lon: number; alt: number }>>(
    new Map()
  );

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

  // Position for focused/searched sat highlight halo
  const focusPos = useMemo(() => {
    if (focusNoradId === null) return null;
    const p = catalogIndex.current.get(focusNoradId);
    if (!p) return null;
    return Cartesian3.fromDegrees(p.lon, p.lat, p.alt * 1000);
  }, [focusNoradId, catalog]);

  // Pulsing pixel size: 18..36 over ~1.2s
  const pulseSize = useMemo(
    () =>
      new CallbackProperty(() => {
        const t = (Date.now() % 1200) / 1200;
        return 20 + Math.sin(t * Math.PI * 2) * 10;
      }, false),
    []
  );
  const pulseColor = useMemo(
    () =>
      new CallbackProperty(() => {
        const t = (Date.now() % 1200) / 1200;
        const a = 0.35 + Math.sin(t * Math.PI * 2) * 0.3;
        return Color.fromCssColorString("#facc15").withAlpha(a);
      }, false),
    []
  );

  const baseLayer = useMemo(
    () =>
      new ImageryLayer(
        new UrlTemplateImageryProvider({
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          credit:
            "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
          maximumLevel: 18,
        }),
        { brightness: 0.9, contrast: 1.1, saturation: 1.05 }
      ),
    []
  );

  const terrainProvider = useMemo(() => new EllipsoidTerrainProvider(), []);

  // Point cloud — imperative render + per-point norad_id for picking.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    if (pointsRef.current) {
      viewer.scene.primitives.remove(pointsRef.current);
      pointsRef.current = null;
    }
    catalogIndex.current.clear();
    if (!catalog || !showPointCloud) return;

    const collection = new PointPrimitiveCollection();
    for (const p of catalog.positions) {
      const regime = altKmToRegime(p.alt_km);
      if (!regimes.has(regime)) continue;
      const prim = collection.add({
        position: Cartesian3.fromDegrees(p.lon_deg, p.lat_deg, p.alt_km * 1000),
        color: regimeColor(p.alt_km),
        pixelSize: 2.5,
        outlineWidth: 0,
      });
      // attach norad_id for picking
      (prim as { id?: unknown }).id = { type: "sat", norad_id: p.norad_id };
      catalogIndex.current.set(p.norad_id, {
        lat: p.lat_deg,
        lon: p.lon_deg,
        alt: p.alt_km,
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

  // Dark space scene.
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
    scene.globe.atmosphereLightIntensity = 3.0;
  }, []);

  // Hover + click pick handler.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;
    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);

    const onMove = (evt: { endPosition: Cartesian2 }) => {
      const picked = viewer.scene.pick(evt.endPosition);
      const pickedId = picked?.id as { type?: string; norad_id?: number } | undefined;
      if (pickedId?.type === "sat" && pickedId.norad_id !== undefined) {
        const pos = catalogIndex.current.get(pickedId.norad_id);
        if (!pos) {
          setHoveredSat(null);
          return;
        }
        setHoveredSat({
          norad_id: pickedId.norad_id,
          name: null,
          object_type: null,
          country: null,
          alt_km: pos.alt,
          lat_deg: pos.lat,
          lon_deg: pos.lon,
          regime: altKmToRegime(pos.alt),
          screenX: evt.endPosition.x,
          screenY: evt.endPosition.y,
        });
        (viewer.canvas as HTMLCanvasElement).style.cursor = "pointer";
      } else {
        setHoveredSat(null);
        (viewer.canvas as HTMLCanvasElement).style.cursor = "default";
      }
    };

    const onClick = (evt: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(evt.position);
      const pickedId = picked?.id as { type?: string; norad_id?: number } | undefined;
      if (pickedId?.type === "sat" && pickedId.norad_id !== undefined) {
        focusOnSat(pickedId.norad_id);
      }
    };

    handler.setInputAction(onMove, ScreenSpaceEventType.MOUSE_MOVE);
    handler.setInputAction(onClick, ScreenSpaceEventType.LEFT_CLICK);

    return () => handler.destroy();
  }, [setHoveredSat, focusOnSat]);

  // Camera fly-to when focus changes.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer || focusNoradId === null) return;
    const pos = catalogIndex.current.get(focusNoradId);
    if (!pos) return;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(pos.lon, pos.lat, (pos.alt + 8000) * 1000),
      duration: 1.8,
    });
  }, [focusNoradId]);

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
      {focusPos && (
        <Entity key={`focus-halo-${focusNoradId}`} position={focusPos}>
          <PointGraphics
            pixelSize={pulseSize as unknown as number}
            color={pulseColor as unknown as Color}
            outlineColor={Color.fromCssColorString("#facc15")}
            outlineWidth={2}
            heightReference={HeightReference.NONE}
          />
          <LabelGraphics
            text="◎ SEARCHED"
            font="10px Inter, sans-serif"
            fillColor={Color.fromCssColorString("#facc15")}
            outlineColor={Color.BLACK}
            outlineWidth={2}
            style={LabelStyle.FILL_AND_OUTLINE}
            verticalOrigin={VerticalOrigin.BOTTOM}
            pixelOffset={new Cartesian2(0, -24)}
            showBackground
            backgroundColor={Color.fromCssColorString("#0a101c").withAlpha(0.9)}
            backgroundPadding={new Cartesian2(6, 4)}
          />
        </Entity>
      )}
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

          // Current position is positions[0] (epoch = now)
          const current = positions[0];
          const satName =
            conjForSat?.primary_norad_id === sat.norad_id
              ? conjForSat?.primary_name
              : conjForSat?.secondary_name;
          const label = satName || `#${sat.norad_id}`;

          return (
            <>
              {/* Orbit polyline (no position — uses positions[] from polyline graphics) */}
              <Entity
                key={`line-${sat.norad_id}`}
                name={`Orbit #${sat.norad_id}`}
              >
                <PolylineGraphics
                  positions={positions}
                  width={width}
                  material={
                    isSelected ? Color.fromCssColorString("#22d3ee") : color
                  }
                />
              </Entity>
              {/* Current-position dot + label */}
              <Entity
                key={`dot-${sat.norad_id}`}
                name={`Sat #${sat.norad_id}`}
                position={current}
                id={`orbit-dot-${sat.norad_id}`}
              >
                <PointGraphics
                  pixelSize={isSelected ? 14 : 10}
                  color={isSelected ? Color.fromCssColorString("#22d3ee") : color}
                  outlineColor={Color.WHITE}
                  outlineWidth={1.5}
                  heightReference={HeightReference.NONE}
                />
                <LabelGraphics
                  text={label}
                  font="11px Inter, sans-serif"
                  fillColor={Color.WHITE}
                  outlineColor={Color.BLACK}
                  outlineWidth={2}
                  style={LabelStyle.FILL_AND_OUTLINE}
                  verticalOrigin={VerticalOrigin.BOTTOM}
                  pixelOffset={new Cartesian2(0, -14)}
                  showBackground
                  backgroundColor={Color.fromCssColorString(
                    "#0a101c"
                  ).withAlpha(0.85)}
                  backgroundPadding={new Cartesian2(6, 4)}
                />
              </Entity>
            </>
          );
        })}
    </Viewer>
  );
}

// Suppress unused-import lint
void Cartographic;
void CMath;
