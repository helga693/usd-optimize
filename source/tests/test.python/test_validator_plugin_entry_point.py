# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import importlib
import importlib.metadata
from unittest import TestCase

# Private, but intentionally imported: the entry-point tests assert the plugin
# registers exactly the rules in this list.
from usd_optimize.validators import (
    _RULE_CATEGORIES,
    UsdOptimizeValidatorPlugin,
    register_all,
    unregister_all,
)
from usd_validation_nvidia import (
    CategoryRuleRegistry,
    PluginManager,
    PluginProtocol,
    register_rule,
)


class Test_ValidatorPluginEntryPoint(TestCase):
    """Validate the ``usd-validation-nvidia`` plugin entry point.

    The entry point is declared in ``tools/pyproject/pyproject.toml`` under the
    ``omni.asset_validator`` group as
    ``usd_optimize.validators:UsdOptimizeValidatorPlugin``. These tests cover
    the object that string resolves to and its plugin contract (always
    available), plus -- when the ``usd-optimize`` wheel is installed --
    discoverability via ``importlib.metadata``. The latter is skipped in
    source-tree test runs, which register no entry-point metadata.
    """

    # Must match the entry-point value declared in tools/pyproject/pyproject.toml.
    ENTRY_POINT_VALUE = "usd_optimize.validators:UsdOptimizeValidatorPlugin"

    def setUp(self):
        # Snapshot the global registry so registry-mutating tests below leave it
        # exactly as they found it, regardless of test execution order.
        registry = CategoryRuleRegistry()
        self._saved = {rule: registry.get_category(rule) for rule, _ in _RULE_CATEGORIES}

    def tearDown(self):
        registry = CategoryRuleRegistry()
        for rule, _ in _RULE_CATEGORIES:
            if registry.get_category(rule) is not None:
                registry.remove(rule)
        for rule, category in self._saved.items():
            if category is not None:
                register_rule(category)(rule)

    def test_entry_point_target_resolves_to_plugin(self):
        """The ``module:attr`` entry-point string resolves to the plugin class."""
        module_name, _, attr = self.ENTRY_POINT_VALUE.partition(":")
        resolved = getattr(importlib.import_module(module_name), attr)
        self.assertIs(resolved, UsdOptimizeValidatorPlugin)

    def test_plugin_conforms_to_plugin_protocol(self):
        """The plugin satisfies the framework's runtime-checkable PluginProtocol."""
        self.assertIsInstance(UsdOptimizeValidatorPlugin(), PluginProtocol)

    def test_on_startup_registers_all_rules(self):
        """``on_startup()`` registers every rule under its declared category."""
        registry = CategoryRuleRegistry()
        unregister_all()
        self.assertTrue(all(registry.get_category(rule) is None for rule, _ in _RULE_CATEGORIES))

        UsdOptimizeValidatorPlugin().on_startup()
        for rule, category in _RULE_CATEGORIES:
            self.assertEqual(registry.get_category(rule), category, msg=f"{rule.__name__} not registered correctly")

    def test_on_shutdown_unregisters_all_rules(self):
        """``on_shutdown()`` removes every rule the plugin registered."""
        registry = CategoryRuleRegistry()
        register_all()

        UsdOptimizeValidatorPlugin().on_shutdown()
        for rule, _ in _RULE_CATEGORIES:
            self.assertIsNone(registry.get_category(rule), msg=f"{rule.__name__} still registered after shutdown")

    def test_all_rules_have_usdoptimize_name_prefix(self):
        """Every registered rule is surfaced under a ``UsdOptimize``-prefixed name.

        usd-validation-nvidia reports rules by class ``__name__`` (the CLI
        ``--help`` rule list, the CSV ``rule`` column, family classification),
        so the prefix keeps Usd Optimize rules attributable and clear of
        identically named upstream rules (e.g. ``IndexedPrimvarChecker``).

        ``__qualname__`` is deliberately left un-prefixed so each class stays
        resolvable by pickle (``__module__`` + ``__qualname__``) against its real
        module attribute; the framework reads ``__name__`` and never ``__qualname__``.
        """
        for rule, _ in _RULE_CATEGORIES:
            self.assertTrue(
                rule.__name__.startswith("UsdOptimize"),
                msg=f"{rule.__name__} is not UsdOptimize-prefixed",
            )
            self.assertFalse(
                rule.__qualname__.startswith("UsdOptimize"),
                msg=f"{rule.__name__}: __qualname__ must stay un-prefixed to remain pickle-resolvable",
            )

    def test_entry_point_discoverable_when_installed(self):
        """When the wheel is installed, the entry point is discoverable and loads the plugin.

        Skipped in source-tree runs (PYTHONPATH alone registers no entry-point
        metadata).
        """
        entry_points = importlib.metadata.entry_points()
        matches = [
            ep
            for group in PluginManager.ENTRYPOINT_GROUPS
            for ep in entry_points.select(group=group)
            if ep.value == self.ENTRY_POINT_VALUE
        ]
        if not matches:
            self.skipTest("usd-optimize entry-point metadata not installed (source-tree run)")
        for ep in matches:
            self.assertIs(ep.load(), UsdOptimizeValidatorPlugin)
