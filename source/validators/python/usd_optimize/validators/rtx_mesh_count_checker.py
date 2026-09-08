# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from typing import ClassVar, Mapping

from pxr import Usd
from usd_validation_nvidia import capabilities, register_requirements

from .base_usd_optimize_checker import BaseUsdOptimizeChecker, Parameter

# Key under which RTX_UNIQUE_MESH_COUNT_LIMIT's effective value is stored in
# _effective_args(). Unlike the other checkers' parameters this is a checker-side
# threshold, not a backing operation argument, so it is never forwarded to the op.
_LIMIT_KEY = "rtxUniqueMeshCountLimit"


@register_requirements(capabilities.GeometryRequirements.VG_RTX_002)
class RtxMeshCountChecker(BaseUsdOptimizeChecker):
    """
    Check if the number of RTX meshes exceeds recommended limits.
    """

    OPERATION_NAME: str = "rtxMeshCount"
    PARAMETERS: ClassVar[Mapping[str, Parameter]] = {
        # Not sourced from an op arg: the rtxMeshCount operation takes no such
        # argument. It tunes the checker's recommended-limit comparison only.
        "RTX_UNIQUE_MESH_COUNT_LIMIT": Parameter(
            default=438000,
            op_arg=_LIMIT_KEY,
            description="The recommended limit for the number of unique RTX meshes in a scene. If the number of unique RTX meshes exceeds this limit, a warning will be issued.",
        ),
    }

    def _GetArgs(self):
        """The rtxMeshCount operation takes no parameter-derived args.

        RTX_UNIQUE_MESH_COUNT_LIMIT is a checker-side threshold rather than an op
        arg, so it must not be forwarded to the operation; its effective value is
        read from :meth:`_effective_args` in :meth:`_CheckStage` instead.
        """
        return {}

    def _CheckStage(self, usdStage: Usd.Stage, analysis_data: dict):
        # verify that the analysis data contains the number of unique RTX meshes
        rtx_unique_mesh_count = analysis_data.get("rtxUniqueMeshCount")
        if rtx_unique_mesh_count is None:
            self._AddFailedCheck(message="Analysis data does not contain RTX unique mesh count")
            return

        # resolve the (possibly user-overridden) recommended limit
        limit = self._effective_args()[_LIMIT_KEY]

        # exceeds recommended limit?
        if rtx_unique_mesh_count > limit:
            self._AddWarning(
                message=f"Number of unique RTX meshes ({rtx_unique_mesh_count}) exceeds the recommended limit of {limit}.",
            )
