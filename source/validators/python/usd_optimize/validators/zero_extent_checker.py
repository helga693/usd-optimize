# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from functools import partial

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_030)
class ZeroExtentChecker(BaseUsdOptimizeChecker):
    """
    Uses Usd Optimize to analyze a scene checking for geometry that has zero sized extents.
    """

    OPERATION_NAME: str = "removeSmallGeometry"

    OPERATION_ARGS = {
        "threshold": 0.0,
    }

    @classmethod
    def _optimize_stage(cls, usdStage: Usd.Stage, _: Usd.Prim, operation_configs: list) -> None:
        """
        Run Usd Optimize using the results of the remove small geometry analysis
        """
        analysis.optimize(usdStage, operation_configs)

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        """Check a stage for zero extent geometry"""
        # Get the list of zero extent geometry prims
        zero_extent_paths = analysis_data.get("smallGeometry", [])

        if zero_extent_paths:
            self._AddWarning(
                message="Stage contains geometry with zero sized extents",
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Remove zero extent geometry using Usd Optimize",
                    callable=partial(self._optimize_stage, operation_configs=self.suggested_operations),
                ),
            )

        # create issues for the zero extent geometry prims
        for prim_path in zero_extent_paths:
            self._AddWarning(
                message="Zero extent geometry found",
                at=usdStage.GetPrimAtPath(prim_path),
            )
