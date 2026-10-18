"""Application defaults: opencode first, embedding evaluation, mock as fallback."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from cli import build_parser as build_cli_parser
from llm.defaults import DEFAULT_EVAL_MODE, DEFAULT_OPENCODE_MODEL, DEFAULT_PROVIDER
from llm.opencode_provider import OpenCodeProvider
from world_studio import build_parser as build_ws_parser


class DefaultsTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(DEFAULT_PROVIDER, "opencode")
        self.assertEqual(DEFAULT_EVAL_MODE, "embedding")
        self.assertTrue(DEFAULT_OPENCODE_MODEL.startswith("opencode-go/"))

    def test_cli_defaults(self):
        parser = build_cli_parser()
        self.assertEqual(parser.get_default("provider"), "opencode")
        self.assertEqual(parser.get_default("eval_mode"), "embedding")

    def test_world_studio_default_provider(self):
        args = build_ws_parser().parse_args(["list"])
        self.assertEqual(args.provider, "opencode")

    def test_opencode_provider_default_model(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NJE_OPENCODE_MODEL", None)
            self.assertEqual(OpenCodeProvider().model, "opencode-go/deepseek-v4.1-flash")

    def test_opencode_model_env_override(self):
        with mock.patch.dict(os.environ, {"NJE_OPENCODE_MODEL": "opencode-go/other-model"}):
            self.assertEqual(OpenCodeProvider().model, "opencode-go/other-model")


if __name__ == "__main__":
    unittest.main()
