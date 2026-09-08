# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from pxr import Sdf, Usd, UsdGeom, UsdShade
from usd_optimize.core.operation import Operation

# Top level prims whose materials are left where they are. These hold lighting and staging rigs
# rather than asset materials, so consolidating them into /Looks would change how a scene renders.
_EXCLUDED_ROOT_NAMES = ("Environment", "LightRig", "TeleportTools")


def _get_root_path(path):
    """Return the top most component of a prim path, e.g. "/World" for "/World/Looks"."""
    root = path
    parent = root
    while parent and parent != Sdf.Path.absoluteRootPath:
        root = parent
        parent = root.GetParentPath()

    return root


def _is_excluded(path):
    """Whether a material sits under one of the top level prims we leave alone.

    Matched on the exact root prim name: a scene that happens to name a root "EnvironmentSetup"
    is not an environment rig and its materials should still be consolidated.
    """
    prefixes = path.GetPrefixes()
    if not prefixes:
        return False

    return prefixes[0].name in _EXCLUDED_ROOT_NAMES


def _is_movable(prim, edit_layer):
    """Whether a material prim can be reparented on the layer we are authoring to.

    Materials pulled in across a composition arc (a reference, a payload, or instancing) have no
    spec on the edit layer, so a namespace edit cannot relocate them. Attempting it would either
    fail outright or author an override that leaves the original in place.
    """
    if prim.IsInstanceProxy() or prim.IsInPrototype():
        return False

    return edit_layer.GetPrimAtPath(prim.GetPath()) is not None


def _reserve_name(name, used_names):
    """Return a name unique within the destination scope, suffixing on collision."""
    candidate = name
    index = 1
    while candidate in used_names:
        candidate = "{}_{}".format(name, index)
        index += 1

    used_names.add(candidate)
    return candidate


def _make_edit(old_path, new_path):
    """Build the namespace edit that relocates a single material."""
    return Sdf.NamespaceEdit.ReparentAndRename(
        old_path, new_path.GetParentPath(), new_path.name, Sdf.NamespaceEdit.atEnd
    )


def _apply_moves(edit_layer, moves):
    """Reparent the material specs, returning only the moves that were actually applied."""
    batch = Sdf.BatchNamespaceEdit()
    for old_path, new_path in moves:
        batch.Add(_make_edit(old_path, new_path))

    if edit_layer.Apply(batch):
        return moves

    # A single invalid edit aborts the whole batch, so retry one at a time and keep what succeeds
    # rather than losing every move to one bad material.
    applied = []
    for old_path, new_path in moves:
        single = Sdf.BatchNamespaceEdit()
        single.Add(_make_edit(old_path, new_path))
        if edit_layer.Apply(single):
            applied.append((old_path, new_path))

    return applied


def _repath_moved_subtree(stage, moves):
    """Repoint the paths inside a moved material at its new location.

    Sdf relocates the specs but leaves paths that point within the moved subtree — such as a
    material's ``outputs:surface`` connection to its shader — aimed at the old location. Left
    alone, the material would relocate with no surface output and render as though unbound.
    """
    for old_path, new_path in moves:
        material = stage.GetPrimAtPath(new_path)
        if not material:
            continue

        for prim in Usd.PrimRange(material):
            for attribute in prim.GetAttributes():
                sources = attribute.GetConnections()
                repathed = [source.ReplacePrefix(old_path, new_path) for source in sources]
                if repathed != sources:
                    attribute.SetConnections(repathed)

            for relationship in prim.GetRelationships():
                targets = relationship.GetTargets()
                repathed = [target.ReplacePrefix(old_path, new_path) for target in targets]
                if repathed != targets:
                    relationship.SetTargets(repathed)


def _retarget_bindings(stage, path_map):
    """Repoint material bindings that referenced a moved material at its new path.

    Sdf fixes up targets authored on the layer it edited, but bindings authored on any other layer
    of the stage still point at the old paths, which would leave those prims unbound.
    """
    for prim in stage.Traverse():
        for relationship in prim.GetRelationships():
            if not relationship.GetName().startswith(UsdShade.Tokens.materialBinding):
                continue

            targets = relationship.GetTargets()
            new_targets = [path_map.get(target, target) for target in targets]
            if new_targets != targets:
                relationship.SetTargets(new_targets)


class MoveMaterialsOperation(Operation):
    """Consolidates the stage's materials under a single scope, such as /World/Looks."""

    def __init__(self):
        super().__init__(
            "moveMaterials",
            "Move Materials",
            'Moves all materials under a prim location such as "/World/Looks" and can also set the root prim of '
            + 'the path (e.g. "/World") as the default prim',
        )
        self.add_argument(
            "materialsPath",
            "Materials Root",
            Operation.ArgumentDisplayTypePrimPath,
            "The prim path that all materials will be moved under.",
            "/World/Looks",
        )
        self.add_argument(
            "makeRootDefault",
            "Make Root Default",
            Operation.ArgumentDisplayTypeBool,
            "Whether the root of materialsPath should be set as the default prim if the stage has no defaultPrim set.",
            True,
        )

    @property
    def author(self):
        return "Usd Optimize (Internal)"

    @property
    def version(self):
        return (1, 0, 0)

    @property
    def visible(self):
        return False

    def _plan_moves(self, stage, materials_path, edit_layer):
        """Work out the destination path for every material that should move."""
        destination = stage.GetPrimAtPath(materials_path)
        used_names = {child.GetName() for child in destination.GetChildren()}

        moves = []
        for prim in stage.Traverse():
            if not prim.IsA(UsdShade.Material):
                continue

            path = prim.GetPath()

            # Already in the destination scope, or deliberately left alone.
            if path.GetParentPath() == materials_path or _is_excluded(path):
                continue

            if not _is_movable(prim, edit_layer):
                continue

            name = _reserve_name(prim.GetName(), used_names)
            moves.append((path, materials_path.AppendChild(name)))

        return moves

    def execute(self, args):
        """Move every eligible material under the materials path and fix up what pointed at them."""
        stage = self.get_usd_stage()
        materials_path = Sdf.Path(args["materialsPath"])

        # Set the root of the materials path as the default prim if the stage has none. Reuse the
        # prim if it is already there: defining it would retype an existing Scope (or anything else)
        # to an Xform.
        if args["makeRootDefault"] and not stage.GetDefaultPrim():
            root_path = _get_root_path(materials_path)
            root = stage.GetPrimAtPath(root_path)
            if not root or not root.IsDefined():
                root = UsdGeom.Xform.Define(stage, root_path).GetPrim()

            stage.SetDefaultPrim(root)

        UsdGeom.Scope.Define(stage, materials_path)

        edit_layer = stage.GetEditTarget().GetLayer()
        moves = self._plan_moves(stage, materials_path, edit_layer)
        if not moves:
            return True

        applied = _apply_moves(edit_layer, moves)
        _repath_moved_subtree(stage, applied)
        _retarget_bindings(stage, dict(applied))

        return True


#####################################
# Register Usd Optimize Plugin
#####################################


def usdOptimizePluginInit():
    return MoveMaterialsOperation()
