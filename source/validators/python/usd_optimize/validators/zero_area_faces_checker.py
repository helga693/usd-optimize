# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_019, override=True)
class ZeroAreaFacesChecker(BaseUsdOptimizeChecker):
    """
    Check mesh prims for any zero area faces, returns all prims that have zero
    area faces as a single warning with an option to fix using a Usd Optimize
    operation.
    """

    OPERATION_NAME: str = "meshCleanup"

    # omo::Defect::DegenerateFaces is topological ("fewer than 3 distinct vertex references"), and
    # checkClean validates each defect against the progressively fixed mesh, so zero-area faces are
    # only counted once mergeVertices+mergeNeighbors has collapsed their coincident points.
    # contractDegenerateEdges must stay False: paired with the merge it corrupts the heap in
    # omo::checkClean. Dropping only that half keeps the detection and clears the crash.
    OPERATION_ARGS = {
        "mergeVertices": True,
        "tolerance": 0.0,
        "contractDegenerateEdges": False,
        "removeDegenerateFaces": True,
        "makeManifold": False,
        "removeIsolatedVertices": False,
        "mergeBoundaries": False,
        "mergeNeighbors": True,
        "removeDuplicateFaces": False,
    }

    @classmethod
    def _mesh_remove_zero_area_faces(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Cleanup meshes by removing zero area faces using Usd Optimize
        """

        # TODO: Configure settings to remove zero area faces

        # Configure mesh cleanup
        operations: List[analysis.OperationConfig] = [
            analysis.OperationConfig(
                cls.OPERATION_NAME,
                args={
                    "mergeVertices": False,
                    "tolerance": 0.0,
                    "contractDegenerateEdges": True,
                    "removeDegenerateFaces": True,
                    "makeManifold": False,
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
        meshesWithDegenerateFaces = analysis_data["meshesWithDegenerateFaces"]

        if meshesWithDegenerateFaces > 0:
            suffix = "es" if meshesWithDegenerateFaces > 1 else ""
            message: str = f"Found {meshesWithDegenerateFaces} zero area faces mesh{suffix} to fix"
            self._AddWarning(
                # requirement=cap.GeometryRequirements.VG_019,
                message=message,
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Fix zero area faces meshes using Usd Optimize",
                    callable=partial(self._mesh_remove_zero_area_faces),
                ),
            )

            # In verbose mode, list each mesh with zero area faces individually.
            self._AddVerbosePrimWarnings(
                usdStage,
                analysis_data.get("meshesWithDegenerateFacesPaths", []),
                "Mesh with zero area faces found",
            )
