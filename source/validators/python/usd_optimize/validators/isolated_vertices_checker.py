# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_018, override=True)
class IsolatedVerticesChecker(BaseUsdOptimizeChecker):
    """
    Check mesh prims for isolated vertices, returns all prims as a single warning with an option to fix via a Usd Optimize operation.
    """

    OPERATION_NAME: str = "meshCleanup"

    # Analysis must request only the isolated-vertex fix: the gated checkClean reports a defect only if its fix is
    # enabled, and isolating it keeps the fix-then-recheck convergent (sibling fixes like degenerate-face removal can
    # otherwise re-expose isolated vertices). Mirrors _mesh_fix_isolated_vertices.
    OPERATION_ARGS = {
        "mergeVertices": False,
        "tolerance": 0.0,
        "contractDegenerateEdges": False,
        "removeDegenerateFaces": False,
        "makeManifold": False,
        "removeIsolatedVertices": True,
        "mergeBoundaries": False,
        "mergeNeighbors": False,
        "removeDuplicateFaces": False,
    }

    @classmethod
    def _mesh_fix_isolated_vertices(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Cleanup meshes by removing isolated vertices using Usd Optimize
        """

        # Configure mesh cleanup
        operations: List[analysis.OperationConfig] = [
            analysis.OperationConfig(
                cls.OPERATION_NAME,
                args={
                    "mergeVertices": False,
                    "tolerance": 0.0,
                    "contractDegenerateEdges": False,
                    "removeDegenerateFaces": False,
                    "makeManifold": False,
                    "removeIsolatedVertices": True,
                    "mergeBoundaries": False,
                    "mergeNeighbors": False,
                    "removeDuplicateFaces": False,
                },
            ),
        ]

        # Execute the optimization via Usd Optimize.
        analysis.optimize(usdStage, operations)

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        """
        Process the Usd Optimize analysis of mesh cleanups
        """

        # Retrieve problem count
        meshesWithIsolatedVertices = analysis_data["meshesWithIsolatedVertices"]

        if meshesWithIsolatedVertices > 0:
            suffix = "es" if meshesWithIsolatedVertices > 1 else ""
            message: str = f"Found {meshesWithIsolatedVertices} mesh{suffix} with isolated vertices to fix"
            self._AddWarning(
                # requirement=cap.GeometryRequirements.VG_018,
                message=message,
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Fix isolated vertices using Usd Optimize",
                    callable=partial(self._mesh_fix_isolated_vertices),
                ),
            )

            # In verbose mode, list each mesh with isolated vertices individually.
            self._AddVerbosePrimWarnings(
                usdStage,
                analysis_data.get("meshesWithIsolatedVerticesPaths", []),
                "Mesh with isolated vertices found",
            )
