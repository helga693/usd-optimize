# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_007, override=True)
class NonManifoldChecker(BaseUsdOptimizeChecker):
    """
    Check mesh prims for non-manifold geometry, returns all non-manifold prims as a single warning with an option to fix via a Usd Optimize operation.
    """

    OPERATION_NAME: str = "meshCleanup"

    # Analysis must request the manifold check explicitly: the gated checkClean only reports a defect whose fix is
    # enabled, so without makeManifold the analysis never inspects manifold-ness. Mirrors _mesh_fix_nonmanifold.
    OPERATION_ARGS = {
        "mergeVertices": False,
        "tolerance": 0.0,
        "contractDegenerateEdges": False,
        "removeDegenerateFaces": False,
        "makeManifold": True,
        "removeIsolatedVertices": False,
        "mergeBoundaries": False,
        "mergeNeighbors": False,
        "removeDuplicateFaces": False,
    }

    @classmethod
    def _mesh_fix_nonmanifold(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Cleanup meshes by fixing nonmanifold geometry using Usd Optimize
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
                    "makeManifold": True,
                    "removeIsolatedVertices": False,
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
        meshesThatAreNonManifolds = analysis_data["meshesThatAreNonManifolds"]

        if meshesThatAreNonManifolds > 0:
            suffix = "es" if meshesThatAreNonManifolds > 1 else ""
            message: str = f"Found {meshesThatAreNonManifolds} nonManifold mesh{suffix} to fix"
            self._AddWarning(
                # requirement=cap.GeometryRequirements.VG_007,
                message=message,
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Fix nonmanifold meshes using Usd Optimize",
                    callable=partial(self._mesh_fix_nonmanifold),
                ),
            )

            # In verbose mode, list each nonManifold mesh individually.
            self._AddVerbosePrimWarnings(
                usdStage,
                analysis_data.get("meshesThatAreNonManifoldsPaths", []),
                "NonManifold mesh found",
            )
