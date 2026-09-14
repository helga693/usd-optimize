# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from pxr import UsdShade

from .test_utils import Test_Operation

LOOKS_PATH = "/World/Looks"


def _bound_material(stage, mesh_path):
    """Return the material currently bound to a mesh."""
    prim = stage.GetPrimAtPath(mesh_path)
    return UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]


def _bound_color(stage, mesh_path):
    """Return the diffuse colour of the material bound to a mesh.

    Materials are matched by colour rather than by path so the assertions stay independent of the
    order in which colliding names get suffixed.
    """
    material = _bound_material(stage, mesh_path)
    shader = UsdShade.Shader(material.GetPrim().GetChild("Shader"))
    return shader.GetInput("diffuseColor").Get()


class Test_Operation_Move_Materials(Test_Operation):

    OPERATION = "moveMaterials"

    def test_move_materials(self):
        """Materials are consolidated under the materials path and their bindings follow them"""

        stage = self._open_stage("moveMaterials.usda")

        self.assertFalse(stage.GetPrimAtPath(LOOKS_PATH).IsValid())

        _, result = self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})
        self.assertTrue(result[0])

        # Both materials moved, and the name collision was resolved rather than dropping one.
        looks = stage.GetPrimAtPath(LOOKS_PATH)
        self.assertTrue(looks.IsValid())
        self.assertEqual(sorted(child.GetName() for child in looks.GetChildren()), ["Mat", "Mat_1", "SetupMat"])

        # The originals are gone.
        self.assertFalse(stage.GetPrimAtPath("/World/Group_A/Looks/Mat").IsValid())
        self.assertFalse(stage.GetPrimAtPath("/World/Group_B/Looks/Mat").IsValid())

        # Each mesh still resolves to the material it started with.
        self.assertEqual(_bound_color(stage, "/World/Group_A/CubeA"), (1, 0, 0))
        self.assertEqual(_bound_color(stage, "/World/Group_B/CubeB"), (0, 0, 1))

    def test_move_materials_preserves_shader_connections(self):
        """Surface connections inside a moved material are repathed along with it"""

        stage = self._open_stage("moveMaterials.usda")

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})

        for name in ("Mat", "Mat_1"):
            material = UsdShade.Material(stage.GetPrimAtPath("{}/{}".format(LOOKS_PATH, name)))
            self.assertTrue(material)

            source = material.ComputeSurfaceSource()[0]
            self.assertTrue(source, "surface connection broke for {}".format(name))

    def test_move_materials_skips_excluded_roots(self):
        """Materials under the environment/rig roots are left where they are"""

        stage = self._open_stage("moveMaterials.usda")

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})

        self.assertTrue(stage.GetPrimAtPath("/Environment/EnvMat").IsValid())
        self.assertEqual(_bound_color(stage, "/Environment/EnvMesh"), (0, 1, 0))
        self.assertEqual(
            _bound_material(stage, "/Environment/EnvMesh").GetPath(),
            "/Environment/EnvMat",
        )

    def test_excluded_roots_match_on_exact_name(self):
        """A root that merely starts with an excluded name is not treated as a rig"""

        stage = self._open_stage("moveMaterials.usda")

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})

        # /Environment is excluded, /EnvironmentSetup only shares a prefix with it.
        self.assertTrue(stage.GetPrimAtPath("/Environment/EnvMat").IsValid())
        self.assertFalse(stage.GetPrimAtPath("/EnvironmentSetup/SetupMat").IsValid())

        self.assertEqual(
            _bound_material(stage, "/EnvironmentSetup/SetupMesh").GetPath(),
            "{}/SetupMat".format(LOOKS_PATH),
        )

    def test_retargets_bindings_authored_on_another_layer(self):
        """Bindings living on a weaker layer than the material follow it to the new path

        Sdf only fixes targets on the layer it edits, so a binding authored on a sublayer is left
        dangling by the namespace edit and has to be repointed explicitly.
        """

        stage = self._open_stage("moveMaterialsSublayer.usda")

        mesh_path = "/World/Group_A/CubeA"
        self.assertEqual(_bound_material(stage, mesh_path).GetPath(), "/World/Group_A/Looks/Mat")

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})

        self.assertTrue(stage.GetPrimAtPath("{}/Mat".format(LOOKS_PATH)).IsValid())
        self.assertEqual(_bound_material(stage, mesh_path).GetPath(), "{}/Mat".format(LOOKS_PATH))

    def test_make_root_default(self):
        """The root of the materials path becomes the default prim when the stage has none"""

        stage = self._open_stage("moveMaterials.usda")
        stage.ClearDefaultPrim()
        self.assertFalse(stage.HasDefaultPrim())

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": True})

        self.assertTrue(stage.HasDefaultPrim())
        self.assertEqual(stage.GetDefaultPrim().GetPath(), "/World")

    def test_make_root_default_reuses_existing_root(self):
        """An existing root prim becomes the default prim without being retyped to an Xform"""

        stage = self._open_stage("moveMaterials.usda")
        stage.ClearDefaultPrim()
        stage.DefinePrim("/Staging", "Scope")

        self._execute_command({"materialsPath": "/Staging/Looks", "makeRootDefault": True})

        default_prim = stage.GetDefaultPrim()
        self.assertEqual(default_prim.GetPath(), "/Staging")
        self.assertEqual(default_prim.GetTypeName(), "Scope")

    def test_make_root_default_disabled(self):
        """A stage without a default prim is left alone when makeRootDefault is off"""

        stage = self._open_stage("moveMaterials.usda")
        stage.ClearDefaultPrim()

        self._execute_command({"materialsPath": LOOKS_PATH, "makeRootDefault": False})

        self.assertFalse(stage.HasDefaultPrim())
        self.assertTrue(stage.GetPrimAtPath(LOOKS_PATH).IsValid())

    def test_move_materials_is_idempotent(self):
        """Running twice leaves the materials where the first run put them"""

        stage = self._open_stage("moveMaterials.usda")

        args = {"materialsPath": LOOKS_PATH, "makeRootDefault": True}
        self._execute_command(args)
        self._execute_command(args)

        looks = stage.GetPrimAtPath(LOOKS_PATH)
        self.assertEqual(sorted(child.GetName() for child in looks.GetChildren()), ["Mat", "Mat_1", "SetupMat"])
