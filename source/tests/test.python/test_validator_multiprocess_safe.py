# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import multiprocessing
import pathlib
from unittest import TestCase, skipUnless

import usd_validation_nvidia
from usd_optimize.validators import _RULE_CATEGORIES, base_usd_optimize_checker, register_all
from usd_optimize.validators.base_usd_optimize_checker import BaseUsdOptimizeChecker
from usd_validation_nvidia import ValidationEngine

try:
    from usd_validation_nvidia import is_multiprocess_safe
except ImportError:  # predates 1.21.0 -- importing at module scope would hide the
    is_multiprocess_safe = None  # diagnostic in test_marker_is_the_real_decorator

_needs_marker = skipUnless(is_multiprocess_safe is not None, "usd-validation-nvidia < 1.21.0")

# Fixture that makes each rule report, keyed by class name without the
# ``UsdOptimize`` prefix that ``register_all`` applies. Mirrors the asset each
# rule is exercised with in test_checkers.py; PrimitiveFitChecker, whose
# test_checkers case is commented out, is mapped here by hand.
_FIXTURES = {
    "CoincidingGeometryChecker": "coincidingMeshes.usda",
    "ColocatedVerticesChecker": "mergeColocatedVertices_input.usd",
    "DuplicateFaceChecker": "cubeDegenerateFaces.usda",
    "DuplicateGeometryChecker": "fuzzyDedupTest.usda",
    "DuplicateMaterialsChecker": "optimizeMaterials.usda",
    "EmptyLeafChecker": "pruneLeaves.usda",
    "FindOverlappingMeshesChecker": "coincidingMeshes.usda",
    "FlatHierarchiesChecker": "flatHierarchies.usd",
    "FuzzyDuplicateGeometryChecker": "fuzzyDedupTest.usda",
    "HighVertexCountChecker": "countVerts.usd",
    "IndexedPrimvarChecker": "validatePrimvars.usda",
    "InvisiblePrimsChecker": "invisiblePrims.usda",
    "IsolatedVerticesChecker": "cubeDegenerateFaces.usda",
    "NonManifoldChecker": "cubeDegenerateFaces.usda",
    "NormalsChecker": "invalidNormals.usda",
    "OccludedMeshesChecker": "hidden_cubes.usda",
    "PrimitiveFitChecker": "primitiveFit.usda",
    "RedundantTimeSamplesChecker": "optimizeTimeSamples.usda",
    "RtxMeshCountChecker": "validate_rtxMeshCount.usda",
    "SmallMeshChecker": "smallMeshCubes.usda",
    "SparseMeshChecker": "sparseMeshes.usda",
    "UnusedUVsChecker": "unusedUVs.usda",
    "WindingsChecker": "geometryWindings.usda",
    "ZeroAreaFacesChecker": "cubeDegenerateFaces.usda",
    "ZeroExtentChecker": "smallMeshes.usda",
}


# Each rule's class-level config as declared, captured at import. unittest imports
# every test module before running any of them, so this snapshot predates the
# class-attribute tuning other tests perform.
_PRISTINE = {rule.__name__: {n: v for n, v in vars(rule).items() if n.isupper()} for rule, _ in _RULE_CATEGORIES}


def _data(name):
    # Resolved locally rather than via test_utils: that import is package-relative
    # and the test directory name contains a dot, so importing it would stop this
    # module from running in place against a source checkout.
    return str((pathlib.Path(__file__).resolve().parent / ".." / "data" / name).resolve())


class Test_ValidatorMultiprocessSafe(TestCase):
    """Validate the ``@multiprocess_safe`` marker on the Usd Optimize rule family.

    ``BaseUsdOptimizeChecker.CheckStage`` carries the marker, so every rule
    inherits it. That is what lets the ``usd-validation-nvidia`` engine dispatch
    our rules to its process pool (``nvidia_usd_validate --process N``), which
    only pools tasks reporting ``is_multiprocess_safe_task()``.
    """

    @classmethod
    def setUpClass(cls):
        cls.rules = register_all()

    def test_marker_is_the_real_decorator(self):
        # base_usd_optimize_checker falls back to a no-op decorator on installs
        # predating the marker, which degrades silently -- rules stay unmarked and
        # never reach the pool. Assert by identity that the fallback did not fire,
        # rather than inferring it from the module's exports.
        self.assertIs(
            base_usd_optimize_checker.multiprocess_safe,
            getattr(usd_validation_nvidia, "multiprocess_safe", None),
            "usd-validation-nvidia < 1.21.0 installed; reinstall to satisfy the declared floor",
        )

    @_needs_marker
    def test_base_check_stage_is_marked(self):
        self.assertTrue(is_multiprocess_safe(BaseUsdOptimizeChecker.CheckStage))

    @_needs_marker
    def test_every_registered_rule_inherits_the_marker(self):
        unmarked = sorted(r.__name__ for r in self.rules if not is_multiprocess_safe(r.CheckStage))
        self.assertEqual(unmarked, [])


@_needs_marker
class Test_ValidatorMultiprocessParity(TestCase):
    """Every rule must report the same issues pooled as it does inline.

    The marker asserts a rule is safe to run in a spawned worker. That is a claim
    about behavior, not just labelling, so run each rule both ways and compare.
    Issues are keyed on (rule, severity, message, location) rather than ``repr``,
    which embeds a per-stage-open ``stage_id`` that legitimately differs.

    Parity is asserted at each rule's declared configuration. A worker is spawned,
    not forked, so it re-imports the rule module and sees the class as written --
    tuning applied by assigning to a class attribute in this process (which other
    tests in this suite do) does **not** reach it, and would diverge. Class-level
    config is therefore restored before each check so this measures the rule
    logic rather than whatever ran earlier.
    """

    # Rules whose fixture yields no issues under default parameters, so their
    # comparison is empty-vs-empty. Tracked so the suite fails loudly if the
    # parity check ever goes vacuous for a rule that used to report.
    MAX_SILENT_RULES = 3

    @classmethod
    def setUpClass(cls):
        # ProcessPoolExecutor inherits the platform default start method, which is
        # fork on Linux; a forked worker inherits the parent's initialized CUDA
        # context and GPU-backed rules die with "initialization error".
        multiprocessing.set_start_method("spawn", force=True)
        cls.rules = {r.__name__: r for r in register_all()}

    def setUp(self):
        # Undo any class-level tuning left behind by earlier tests, so each rule
        # is compared as declared -- see the class docstring.
        for rule in self.rules.values():
            pristine = _PRISTINE[rule.__name__]
            for name in [n for n in vars(rule) if n.isupper() and n not in pristine]:
                delattr(rule, name)
            for name, value in pristine.items():
                setattr(rule, name, value)

    @staticmethod
    def _issues(asset, rule, processes):
        engine = ValidationEngine(init_rules=False, processes=processes)
        engine.enable_rule(rule)
        return sorted(
            (str(i.rule), str(i.severity), str(i.message), str(i.at)) for i in engine.validate(asset).issues()
        )

    def test_pooled_matches_inline_for_every_rule(self):
        silent = []
        for name in sorted(self.rules):
            base = name.removeprefix("UsdOptimize")
            with self.subTest(rule=base):
                asset = _data(_FIXTURES[base])
                inline = self._issues(asset, self.rules[name], 0)
                pooled = self._issues(asset, self.rules[name], 2)
                self.assertEqual(inline, pooled)
                if not inline:
                    silent.append(base)
        self.assertLessEqual(len(silent), self.MAX_SILENT_RULES, f"parity is vacuous for {silent}")

    def test_every_rule_has_a_fixture(self):
        bases = {n.removeprefix("UsdOptimize") for n in self.rules}
        self.assertEqual(sorted(bases - _FIXTURES.keys()), [])
