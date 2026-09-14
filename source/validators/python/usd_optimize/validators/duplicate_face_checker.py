# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_032)
class DuplicateFaceChecker(BaseUsdOptimizeChecker):
    """
    Check mesh prims for duplicate faces, returns all prims as a single warning with an option to fix via a Usd Optimize operation.
    """

    OPERATION_NAME: str = "meshCleanup"

    # Analysis must request only the duplicate-face fix: the gated checkClean reports a defect only if its fix is
    # enabled, and isolating it stops sibling fixes (e.g. degenerate-face removal) from masking the duplicates before
    # the duplicate check runs. Mirrors _mesh_fix_duplicate_faces.
    OPERATION_ARGS = {
        "mergeVertices": False,
        "tolerance": 0.0,
        "contractDegenerateEdges": False,
        "removeDegenerateFaces": False,
        "makeManifold": False,
        "removeIsolatedVertices": False,
        "mergeBoundaries": False,
        "mergeNeighbors": False,
        "removeDuplicateFaces": True,
    }

    @classmethod
    def _mesh_fix_duplicate_faces(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Cleanup meshes by fixing duplicate faces geometry using Usd Optimize
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
                    "removeIsolatedVertices": False,
                    "mergeBoundaries": False,
                    "mergeNeighbors": False,
                    "removeDuplicateFaces": True,
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
        meshesWithDuplicateFaces = analysis_data["meshesWithDuplicateFaces"]

        if meshesWithDuplicateFaces > 0:
            suffix = "es" if meshesWithDuplicateFaces > 1 else ""
            message: str = f"Found {meshesWithDuplicateFaces} mesh{suffix} with duplicate faces to fix"
            self._AddWarning(
                # requirement=cap.GeometryRequirements.VG_032,
                message=message,
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Fix duplicate faces using Usd Optimize",
                    callable=partial(self._mesh_fix_duplicate_faces),
                ),
            )

            # In verbose mode, list each mesh with duplicate faces individually.
            self._AddVerbosePrimWarnings(
                usdStage,
                analysis_data.get("meshesWithDuplicateFacesPaths", []),
                "Mesh with duplicate faces found",
            )
