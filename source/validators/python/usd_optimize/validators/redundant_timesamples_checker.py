# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from typing import ClassVar, List, Mapping

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker, Parameter, ParameterFromOpArg


@register_requirements(capabilities.GeometryRequirements.VG_015)
class RedundantTimeSamplesChecker(BaseUsdOptimizeChecker):
    """
    Uses Usd Optimize to analyze a scene checking for redundant time samples.
    """

    OPERATION_NAME: str = "optimizeTimeSamples"
    PARAMETERS: ClassVar[Mapping[str, Parameter]] = {
        "EPSILON_DOUBLE": ParameterFromOpArg("epsilonD"),
        "EPSILON_FLOAT": ParameterFromOpArg("epsilonF"),
    }

    def _remove_redundant_timesamples(self, usdStage: Usd.Stage, attr: Usd.Attribute):
        """Use Usd Optimize to fix the specified attribute"""

        # Honor the tuned EPSILON parameters so the fix removes the same samples the
        # analysis pass flagged as redundant.
        args = self._effective_args()
        args["attributePaths"] = [str(attr.GetPath())]

        # Configure operation
        operations: List[analysis.OperationConfig] = [
            analysis.OperationConfig(self.OPERATION_NAME, args=args),
        ]

        # Execute the optimization via Usd Optimize.
        analysis.optimize(usdStage, operations)

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        """Check a stage for redundant time samples"""

        for attr_path, values in analysis_data.items():
            redundant: int = values[0]
            total: int = values[1]

            suffix = "" if redundant == 1 else "s"
            message: str = f"Attribute {attr_path} has {redundant}/{total} redundant time sample{suffix}"
            self._AddWarning(
                message=message,
                at=usdStage.GetAttributeAtPath(attr_path),
                suggestion=Suggestion(
                    message="Remove redundant time samples using Usd Optimize",
                    callable=self._remove_redundant_timesamples,
                ),
            )
