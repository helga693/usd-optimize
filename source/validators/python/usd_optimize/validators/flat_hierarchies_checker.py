# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from typing import ClassVar, Mapping

from pxr import Usd
from usd_validation_nvidia import capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker, Parameter, ParameterFromOpArg


@register_requirements(capabilities.HierarchyRequirements.HI_011)
class FlatHierarchiesChecker(BaseUsdOptimizeChecker):
    """
    Reports prims with a large number of children (a flat hierarchy).
    """

    OPERATION_NAME: str = "findFlatHierarchies"
    PARAMETERS: ClassVar[Mapping[str, Parameter]] = {
        "MAX_CHILDREN": ParameterFromOpArg("maxChildren"),
        "CONSIDER_ALL_CHILDREN": ParameterFromOpArg("considerAllChildren"),
    }

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        # verify that the analysis data contains the flat hierarchies
        flat_hierarchies = analysis_data.get("flatHierarchies")
        if flat_hierarchies is None:
            self._AddFailedCheck(message="Analysis data does not contain flat hierarchies")
            return

        # create any issues
        for prim_path, num_children in flat_hierarchies.items():
            self._AddWarning(
                message=f"Found {num_children} children under prim '{prim_path}'",
                at=usdStage.GetPrimAtPath(prim_path),
            )
