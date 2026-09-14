# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from pxr import Usd
from usd_validation_nvidia import capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_006)
class FindOverlappingMeshesChecker(BaseUsdOptimizeChecker):
    """
    Reports meshes that overlap one another in the scene.
    """

    OPERATION_NAME: str = "findOverlappingMeshes"
    OPERATION_ARGS = {"fullStageReport": True}

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        """
        Process the Usd Optimize mesh overlap detection analysis.

        Args:
            usdStage: The USD stage being validated.
            analysis_data: Dictionary containing overlap analysis results from the
                findOverlappingMeshes operation.
        """

        # Retrieve analysis data
        suppressed_overlaps = analysis_data.get("suppressedOverlaps", 0)
        overlapping_meshes = analysis_data.get("overlappingMeshes", [])

        # If the analysis is suppressed, add a warning and return
        if suppressed_overlaps:
            self._AddWarning(
                message=(
                    f"Found {suppressed_overlaps} overlapping meshes in the stage."
                    "\nSelect the meshes in the viewer to visualize and eliminate overlaps.\n"
                )
            )
            return

        if len(overlapping_meshes) == 0:
            return

        # Workaround for usd-validation-nvidia 1.21.0, whose CLI renders `at` only as
        # a tuple and raises on the list its own _AddWarning documents, losing the
        # whole run. Drop the tuple once the floor moves to 1.22.0, which carries the
        # upstream fix.
        all_prims = tuple(usdStage.GetPrimAtPath(path) for path in overlapping_meshes)

        self._AddWarning(
            message=f"Found {len(overlapping_meshes)} overlapping meshes in the stage.",
            at=all_prims,
        )
