# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from functools import partial
from typing import List

from pxr import Usd
from usd_optimize.core import analysis
from usd_validation_nvidia import Suggestion, capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker


@register_requirements(capabilities.GeometryRequirements.VG_028, override=True)
class NormalsChecker(BaseUsdOptimizeChecker):
    """
    Checks mesh prims for normals aligned to face orientation.

    Returns all prims with normals not aligned with face winding order as a single warning, with an option
    to fix using Usd Optimize operations.

    """

    OPERATION_NAME: str = "generateNormals"

    @classmethod
    def _mesh_generate_normals(cls, usdStage: Usd.Stage, prim: Usd.Prim) -> None:
        """
        Generate normals using Usd Optimize
        """

        # TODO: Configure settings to fix invalid normals
        #
        # NOTE: We can generate new normals, but it's not guaranteed to always give the result the user desired.

        # Configure generateNormals
        operations: List[analysis.OperationConfig] = [
            analysis.OperationConfig(
                cls.OPERATION_NAME,
                args={
                    "binding": 3,  # auto
                    "existingNormals": 0,  # fix
                    "sharpnessAngle": 60.0,
                    "weightmode": 0,  # weight by angle
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
        totalNonUnitLengthStrict = analysis_data["totalNonUnitLengthStrict"]

        if totalNonUnitLengthStrict > 0:
            suffix = "es" if totalNonUnitLengthStrict > 1 else ""
            message: str = (
                f"Found {totalNonUnitLengthStrict} mesh{suffix} with normals that are not of length 1 within a tolerance of 1e-4"
            )
            self._AddWarning(
                # requirement=cap.GeometryRequirements.VG_028,
                message=message,
                at=usdStage.GetPrimAtPath("/"),
                suggestion=Suggestion(
                    message="Fix normals using Usd Optimize",
                    callable=partial(self._mesh_generate_normals),
                ),
            )

            # In verbose mode, list each mesh with non-unit-length normals individually.
            self._AddVerbosePrimWarnings(
                usdStage,
                analysis_data.get("nonUnitLengthStrictPaths", []),
                "Mesh with normals that are not of length 1 found",
            )
