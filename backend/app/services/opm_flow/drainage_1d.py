from __future__ import annotations

import importlib.util
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.services.opm_flow.schemas import (
    ContactInterval,
    Drainage1DConnection,
    Drainage1DModelSpec,
    Drainage1DPrepareRequest,
    Drainage1DPrepareResponse,
)


@dataclass(frozen=True)
class _TrajectoryPoint:
    well_name: str
    md: float
    x: float
    y: float
    z: float


class Drainage1DPreparationService:
    """Prepare reviewable 1D injector-producer model specs for Module B.

    The service does not launch OPM Flow. It converts normalized trajectories,
    perforations and histories into contact intervals, participation priors and
    one straight-corridor OPM model specification per injector-producer link.
    """

    def prepare(self, payload: Drainage1DPrepareRequest) -> Drainage1DPrepareResponse:
        trajectory_by_well = self._group_trajectories(payload.trajectories)
        contact_intervals = self._build_contact_intervals(
            payload.perforations,
            trajectory_by_well,
            self._well_group_lookup(payload.well_groups),
        )
        producer_names = self._producer_names(payload.production_history)
        injector_names = self._injector_names(payload.injection_history)
        contact_wells = {item.well_name for item in contact_intervals}

        if not producer_names:
            producer_names = contact_wells - injector_names
        if not injector_names:
            injector_names = contact_wells - producer_names

        connections = self._build_connections(
            scenario_id=payload.scenario_id,
            injectors=injector_names,
            producers=producer_names,
            intervals=contact_intervals,
            radius_m=payload.influence_radius_m,
            kernel_power=payload.distance_kernel_power,
        )
        model_specs = [self._model_spec(connection, payload) for connection in connections if connection.active]
        return Drainage1DPrepareResponse(
            scenario_id=payload.scenario_id,
            contact_intervals=contact_intervals,
            connections=connections,
            model_specs=model_specs,
            diagnostics=self._diagnostics(payload, contact_intervals, connections, model_specs),
        )

    def _group_trajectories(self, rows: list[dict[str, Any]]) -> dict[str, list[_TrajectoryPoint]]:
        grouped: dict[str, list[_TrajectoryPoint]] = defaultdict(list)
        for row in rows:
            well_name = self._well_name(row)
            md = self._number(row.get("md") or row.get("measured_depth") or row.get("measured_depth_m"))
            x = self._number(row.get("x"))
            y = self._number(row.get("y"))
            z = self._number(row.get("z") or row.get("tvd"))
            if not well_name or md is None or x is None or y is None or z is None:
                continue
            grouped[well_name].append(_TrajectoryPoint(well_name=well_name, md=md, x=x, y=y, z=z))
        for points in grouped.values():
            points.sort(key=lambda item: item.md)
        return grouped

    def _build_contact_intervals(
        self,
        perforations: list[dict[str, Any]],
        trajectory_by_well: dict[str, list[_TrajectoryPoint]],
        well_group_by_well: dict[str, dict[str, Any]],
    ) -> list[ContactInterval]:
        intervals: list[ContactInterval] = []
        for index, row in enumerate(perforations, start=1):
            well_name = self._well_name(row)
            top_md = self._number(row.get("top_md") or row.get("top") or row.get("md_top"))
            bottom_md = self._number(row.get("bottom_md") or row.get("bottom") or row.get("md_bottom"))
            if not well_name or top_md is None or bottom_md is None:
                continue
            if bottom_md < top_md:
                top_md, bottom_md = bottom_md, top_md

            points = trajectory_by_well.get(well_name, [])
            group = well_group_by_well.get(well_name, {})
            center_md = (top_md + bottom_md) / 2.0
            top_xyz = self._interpolate(points, top_md)
            bottom_xyz = self._interpolate(points, bottom_md)
            center_xyz = self._interpolate(points, center_md)
            intervals.append(
                ContactInterval(
                    contact_id=str(row.get("contact_id") or row.get("perforation_id") or f"contact::{index}"),
                    well_name=well_name,
                    lu_id=self._text(row.get("lu_id") or row.get("lu") or group.get("lu_id")),
                    sloy_id=self._text(row.get("sloy_id") or row.get("sloy") or group.get("sloy_id")),
                    well_pad_id=self._text(row.get("well_pad_id") or row.get("well_pad") or group.get("well_pad_id")),
                    top_md=top_md,
                    bottom_md=bottom_md,
                    center_md=center_md,
                    top_x=top_xyz[0],
                    top_y=top_xyz[1],
                    top_z=top_xyz[2],
                    bottom_x=bottom_xyz[0],
                    bottom_y=bottom_xyz[1],
                    bottom_z=bottom_xyz[2],
                    center_x=center_xyz[0],
                    center_y=center_xyz[1],
                    center_z=center_xyz[2],
                    metadata={
                        "source_row_number": row.get("source_row_number"),
                        "group_path": group.get("group_path"),
                        "infrastructure_object_id": group.get("infrastructure_object_id"),
                    },
                )
            )
        return intervals

    def _well_group_lookup(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for row in rows:
            well_name = self._well_name(row)
            if not well_name:
                continue
            lookup[well_name] = row
        return lookup

    def _build_connections(
        self,
        *,
        scenario_id: str,
        injectors: set[str],
        producers: set[str],
        intervals: list[ContactInterval],
        radius_m: float,
        kernel_power: float,
    ) -> list[Drainage1DConnection]:
        by_well: dict[str, list[ContactInterval]] = defaultdict(list)
        for interval in intervals:
            by_well[interval.well_name].append(interval)

        raw_connections: list[tuple[float, Drainage1DConnection]] = []
        for injector in sorted(injectors):
            injector_center = self._well_center(by_well.get(injector, []))
            if injector_center is None:
                continue
            for producer in sorted(producers):
                if producer == injector:
                    continue
                producer_center = self._well_center(by_well.get(producer, []))
                if producer_center is None:
                    continue
                distance = self._distance_2d(injector_center, producer_center)
                inside = distance <= radius_m
                weight = max(0.0, 1.0 - distance / radius_m) ** kernel_power if inside else 0.0
                if weight <= 0:
                    continue
                connection = Drainage1DConnection(
                    connection_id=f"conn::{self._safe_name(injector)}::{self._safe_name(producer)}",
                    scenario_id=scenario_id,
                    injector_name=injector,
                    producer_name=producer,
                    distance_m=distance,
                    inside_influence_radius=inside,
                    active=inside,
                    alpha_prior=0.0,
                    alpha=0.0,
                    eta=1.0,
                    tau_days=10.0 + distance / 5.0,
                    pv=0.0,
                    link_type="unknown",
                    prior_source="distance_3000m",
                    metadata={"raw_distance_weight": weight},
                )
                raw_connections.append((weight, connection))

        weight_by_injector: dict[str, float] = defaultdict(float)
        for weight, connection in raw_connections:
            weight_by_injector[connection.injector_name] += weight

        connections: list[Drainage1DConnection] = []
        for weight, connection in raw_connections:
            total = weight_by_injector[connection.injector_name]
            alpha = weight / total if total > 0 else 0.0
            pv = self._edge_pv(connection.distance_m, alpha)
            connections.append(connection.model_copy(update={"alpha_prior": alpha, "alpha": alpha, "pv": pv}))
        return connections

    def _model_spec(self, connection: Drainage1DConnection, payload: Drainage1DPrepareRequest) -> Drainage1DModelSpec:
        nx = max(1, math.ceil(connection.distance_m / payload.grid_block_length_m))
        model_name = f"model_{self._safe_name(connection.injector_name)}_{self._safe_name(connection.producer_name)}"
        return Drainage1DModelSpec(
            model_id=f"opm-1d::{self._safe_name(connection.injector_name)}::{self._safe_name(connection.producer_name)}",
            model_name=model_name,
            connection_id=connection.connection_id,
            injector_name=connection.injector_name,
            producer_name=connection.producer_name,
            nx=nx,
            ny=1,
            nz=1,
            dx_m=payload.grid_block_length_m,
            dy_m=payload.grid_block_width_m,
            dz_m=payload.grid_thickness_m,
            length_m=connection.distance_m,
            pore_volume=connection.pv,
            allocated_ooip=None,
            opm_case_name=model_name.upper()[:48],
            metadata={
                "geometry": "straight_1d_corridor",
                "alpha_prior": connection.alpha_prior,
                "eta": connection.eta,
                "tau_days": connection.tau_days,
            },
        )

    def _diagnostics(
        self,
        payload: Drainage1DPrepareRequest,
        intervals: list[ContactInterval],
        connections: list[Drainage1DConnection],
        model_specs: list[Drainage1DModelSpec],
    ) -> dict[str, Any]:
        pywaterflood_available = importlib.util.find_spec("pywaterflood") is not None
        return {
            "trajectory_rows": len(payload.trajectories),
            "well_group_rows": len(payload.well_groups),
            "perforation_rows": len(payload.perforations),
            "contact_interval_count": len(intervals),
            "connection_count": len(connections),
            "active_model_count": len(model_specs),
            "injector_count": len({item.injector_name for item in connections}),
            "producer_count": len({item.producer_name for item in connections}),
            "influence_radius_m": payload.influence_radius_m,
            "crm_adapter": "pywaterflood" if pywaterflood_available else "distance_fallback",
            "external_tools": {"pywaterflood_available": pywaterflood_available},
            "warnings": self._warnings(payload, intervals, connections),
        }

    def _warnings(
        self,
        payload: Drainage1DPrepareRequest,
        intervals: list[ContactInterval],
        connections: list[Drainage1DConnection],
    ) -> list[str]:
        warnings: list[str] = []
        if not payload.trajectories:
            warnings.append("No trajectories supplied; 1D geometry cannot be built.")
        if not payload.well_groups:
            warnings.append("No well_groups/GRUP supplied; contact intervals will not have pad/layer hierarchy.")
        if not payload.perforations:
            warnings.append("No perforations supplied; contact intervals cannot be built.")
        if not payload.production_history:
            warnings.append("No production history supplied; producer set is inferred from perforations only.")
        if not payload.injection_history:
            warnings.append("No injection history supplied; injector-producer links cannot be initialized reliably.")
        if intervals and not connections:
            warnings.append("No injector-producer links inside influence radius.")
        return warnings

    def _well_center(self, intervals: list[ContactInterval]) -> tuple[float, float, float] | None:
        coords = [(item.center_x, item.center_y, item.center_z) for item in intervals if item.center_x is not None and item.center_y is not None]
        if not coords:
            return None
        count = len(coords)
        return (
            sum(float(item[0]) for item in coords if item[0] is not None) / count,
            sum(float(item[1]) for item in coords if item[1] is not None) / count,
            sum(float(item[2] or 0.0) for item in coords) / count,
        )

    def _interpolate(self, points: list[_TrajectoryPoint], md: float) -> tuple[float | None, float | None, float | None]:
        if not points:
            return (None, None, None)
        if md <= points[0].md:
            return (points[0].x, points[0].y, points[0].z)
        if md >= points[-1].md:
            return (points[-1].x, points[-1].y, points[-1].z)
        for left, right in zip(points, points[1:]):
            if left.md <= md <= right.md:
                span = right.md - left.md
                fraction = 0.0 if span == 0 else (md - left.md) / span
                return (
                    left.x + (right.x - left.x) * fraction,
                    left.y + (right.y - left.y) * fraction,
                    left.z + (right.z - left.z) * fraction,
                )
        return (points[-1].x, points[-1].y, points[-1].z)

    def _producer_names(self, rows: list[dict[str, Any]]) -> set[str]:
        return {self._well_name(row) for row in rows if self._well_name(row)}

    def _injector_names(self, rows: list[dict[str, Any]]) -> set[str]:
        return {self._well_name(row) for row in rows if self._well_name(row)}

    def _edge_pv(self, distance_m: float, alpha: float) -> float:
        phi = 0.20
        width_m = 50.0
        thickness_m = 5.0
        return phi * max(distance_m, 50.0) * width_m * thickness_m * max(alpha, 0.05)

    def _distance_2d(self, left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
        return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2)

    def _well_name(self, row: dict[str, Any]) -> str:
        return (self._text(row.get("well_name") or row.get("well") or row.get("well_id") or row.get("producer_id") or row.get("injector_id")) or "").upper()

    def _number(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    def _text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _safe_name(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
        return safe or "well"
