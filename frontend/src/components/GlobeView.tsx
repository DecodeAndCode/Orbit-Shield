import { useMemo } from "react";
import { Viewer, Entity, PolylineGraphics } from "resium";
import {
  Cartesian3,
  Color,
  UrlTemplateImageryProvider,
  ImageryLayer,
} from "cesium";
import { usePropagate, useConjunctions } from "../api/client";
import { useColliderStore } from "../stores/colliderStore";

function riskCesiumColor(pc: number | null): Color {
  if (pc === null) return Color.GRAY;
  if (pc >= 1e-4) return Color.RED.withAlpha(0.9);
  if (pc >= 1e-6) return Color.YELLOW.withAlpha(0.8);
  return Color.GREEN.withAlpha(0.7);
}

export default function GlobeView() {
  const { data: conjunctions } = useConjunctions();
  const selectedId = useColliderStore((s) => s.selectedConjunctionId);

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
      ImageryLayer.fromProviderAsync(
        Promise.resolve(
          new UrlTemplateImageryProvider({
            url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            credit: "© OpenStreetMap contributors",
            maximumLevel: 18,
          })
        ),
        {}
      ),
    []
  );

  return (
    <Viewer
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
