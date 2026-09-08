# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from usd_validation_nvidia import CategoryRuleRegistry, register_rule

from .base_usd_optimize_checker import set_verbose
from .coinciding_geometry_checker import CoincidingGeometryChecker
from .colocated_vertices_checker import ColocatedVerticesChecker
from .duplicate_face_checker import DuplicateFaceChecker
from .duplicate_geometry_checker import DuplicateGeometryChecker
from .duplicate_geometry_fuzzy_checker import FuzzyDuplicateGeometryChecker
from .duplicate_materials_checker import DuplicateMaterialsChecker
from .empty_leaf_checker import EmptyLeafChecker
from .find_overlapping_meshes_checker import FindOverlappingMeshesChecker
from .flat_hierarchies_checker import FlatHierarchiesChecker
from .high_vertex_count_checker import HighVertexCountChecker
from .indexed_primvars_checker import IndexedPrimvarChecker
from .invisible_prims_checker import InvisiblePrimsChecker
from .isolated_vertices_checker import IsolatedVerticesChecker
from .nonmanifold_checker import NonManifoldChecker
from .normals_checker import NormalsChecker
from .occluded_meshes_checker import OccludedMeshesChecker
from .primitive_fit_checker import PrimitiveFitChecker
from .redundant_timesamples_checker import RedundantTimeSamplesChecker
from .rtx_mesh_count_checker import RtxMeshCountChecker
from .small_mesh_checker import SmallMeshChecker
from .sparse_mesh_checker import SparseMeshChecker
from .unused_uvs_checker import UnusedUVsChecker
from .windings_checker import WindingsChecker
from .zero_area_faces_checker import ZeroAreaFacesChecker
from .zero_extent_checker import ZeroExtentChecker

_RULE_CATEGORIES = (
    (CoincidingGeometryChecker, "Usd:Performance"),
    (ColocatedVerticesChecker, "Omni:Geometry"),
    (DuplicateFaceChecker, "Omni:Geometry"),
    (DuplicateGeometryChecker, "Usd:Performance"),
    (FuzzyDuplicateGeometryChecker, "Usd:Performance"),
    (DuplicateMaterialsChecker, "Usd:Performance"),
    (EmptyLeafChecker, "Usd:Performance"),
    (FindOverlappingMeshesChecker, "Usd:Performance"),
    (FlatHierarchiesChecker, "Usd:Performance"),
    (HighVertexCountChecker, "Usd:Performance"),
    (IndexedPrimvarChecker, "Omni:Geometry"),
    (InvisiblePrimsChecker, "Usd:Performance"),
    (IsolatedVerticesChecker, "Omni:Geometry"),
    (NonManifoldChecker, "Omni:Geometry"),
    (NormalsChecker, "Usd:Performance"),
    (OccludedMeshesChecker, "Usd:Performance"),
    (PrimitiveFitChecker, "Usd:Performance"),
    (RedundantTimeSamplesChecker, "Usd:Performance"),
    (RtxMeshCountChecker, "Usd:Performance"),
    (SmallMeshChecker, "Usd:Performance"),
    (SparseMeshChecker, "Usd:Performance"),
    (UnusedUVsChecker, "Usd:Performance"),
    (WindingsChecker, "Usd:Performance"),
    (ZeroAreaFacesChecker, "Omni:Geometry"),
    (ZeroExtentChecker, "Usd:Performance"),
)

# usd-validation-nvidia surfaces rules by class __name__ (--help, CSV "rule" column,
# family classification), so prefix ours with "UsdOptimize" to keep them attributable
# and clear of identically named upstream rules (e.g. IndexedPrimvarChecker). Rewrite
# __name__ only -- __qualname__ stays intact so classes remain pickle-resolvable; the
# framework never reads it. Idempotent across reloads.
for _rule, _ in _RULE_CATEGORIES:
    if not _rule.__name__.startswith("UsdOptimize"):
        _rule.__name__ = "UsdOptimize" + _rule.__name__


def register_all():
    """Register Usd Optimize rules with Asset Validator."""
    registry = CategoryRuleRegistry()
    for rule, category in _RULE_CATEGORIES:
        if registry.get_category(rule) is None:
            register_rule(category)(rule)
    return [rule for rule, _ in _RULE_CATEGORIES]


def unregister_all():
    """Unregister all Usd Optimize rules from Asset Validator."""

    registry = CategoryRuleRegistry()
    for rule, _ in _RULE_CATEGORIES:
        if registry.get_category(rule) is not None:
            registry.remove(rule)


class UsdOptimizeValidatorPlugin:
    """Asset Validator entry point for Usd Optimize rules."""

    def on_startup(self):
        register_all()

    def on_shutdown(self):
        unregister_all()


__all__ = [
    "CoincidingGeometryChecker",
    "ColocatedVerticesChecker",
    "DuplicateFaceChecker",
    "DuplicateGeometryChecker",
    "FuzzyDuplicateGeometryChecker",
    "DuplicateMaterialsChecker",
    "EmptyLeafChecker",
    "FindOverlappingMeshesChecker",
    "FlatHierarchiesChecker",
    "HighVertexCountChecker",
    "IndexedPrimvarChecker",
    "InvisiblePrimsChecker",
    "IsolatedVerticesChecker",
    "NonManifoldChecker",
    "NormalsChecker",
    "OccludedMeshesChecker",
    "PrimitiveFitChecker",
    "RedundantTimeSamplesChecker",
    "RtxMeshCountChecker",
    "SmallMeshChecker",
    "SparseMeshChecker",
    "UnusedUVsChecker",
    "WindingsChecker",
    "ZeroAreaFacesChecker",
    "ZeroExtentChecker",
    "UsdOptimizeValidatorPlugin",
    "register_all",
    "unregister_all",
    "set_verbose",
]
