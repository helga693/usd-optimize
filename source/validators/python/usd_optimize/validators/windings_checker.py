# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_029, override=True)
class WindingsChecker(BaseUsdOptimizeChecker):
    """
    Finds and fixes meshes with inconsistent windings.
    """

    OPERATION_NAME: str = "meshCleanup"

    # Analysis needs no fix enabled: the winding/normal comparison runs unconditionally in analysis
    # mode (MeshCleanup.cpp, windingsDisagreeWithNormals), outside the gated checkClean defect set.
    # Leaving this unset falls through to the operation's C++ ctor defaults, which enable six defect
    # categories at once -- and CoincidentNeighborVertices together with DegenerateEdges corrupts the
    # heap inside omo::checkClean.
    OPERATION_ARGS = {
        "mergeVertices": False,
        "tolerance": 0.0,
        "contractDegenerateEdges": False,
        "removeDegenerateFaces": False,
        "makeManifold": False,
        "removeIsolatedVertices": False,
        "mergeBoundaries": False,
        "mergeNeighbors": False,
        "removeDuplicateFaces": False,
    }

    @classmethod
    def _mesh_coorient(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Reverse the winding order of the mesh in question
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
                    "removeDuplicateFaces": False,
                    "coorientFaces": True,
                    "paths": [str(prim.GetPath())],
                },
            ),
        ]

        # Execute the optimization via Usd Optimize.
        analysis.optimize(usdStage, operations)

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):

        # verify that the analysis data contains the meshes with inconsistent windings
        inconsistent_meshes = analysis_data.get("meshesWithInconsistentWindings")
        if inconsistent_meshes is None:
            self._AddFailedCheck(message="Analysis data does not contain any meshes with inconsistent windings")
            return

        # sort for consistency
        inconsistent_meshes.sort()

        # create the issues
        for prim_path in inconsistent_meshes:
            self._AddError(
                message="Mesh has inconsistent windings",
                at=usdStage.GetPrimAtPath(prim_path),
                suggestion=Suggestion(
                    message="Fix windings using Usd Optimize",
                    callable=partial(self._mesh_coorient),
                ),
            )
