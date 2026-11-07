"""Headless tests for the import_model tool.

Verifies the agent can import a model from a local file or a step.parts URL
*without* opening FreeCAD. FreeCAD / Import / requests are all mocked.
"""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

from freecad_ai.tools.freecad_tools import _handle_import_model


def test_import_model_requires_a_source():
    result = _handle_import_model()
    assert not result.success
    assert result.error == "Provide filename or step_url"


def test_import_model_rejects_missing_local_file(tmp_path, monkeypatch):
    fake_app = types.ModuleType("FreeCAD")
    monkeypatch.setitem(sys.modules, "FreeCAD", fake_app)
    result = _handle_import_model(filename=str(tmp_path / "missing.step"))
    assert not result.success
    assert "File not found" in result.error


def test_import_model_imports_local_file(monkeypatch, tmp_path):
    source = tmp_path / "part.step"
    source.write_text("step")
    doc = MagicMock()
    doc.Name = "Doc"
    doc.Objects = []
    app = types.ModuleType("FreeCAD")
    app.ActiveDocument = doc
    import_module = types.ModuleType("Import")
    import_module.insert = MagicMock()
    monkeypatch.setitem(sys.modules, "FreeCAD", app)
    monkeypatch.setitem(sys.modules, "Import", import_module)
    monkeypatch.setattr("freecad_ai.core.active_document.get_synced_active_document", lambda: doc)

    result = _handle_import_model(filename=str(source))
    assert result.success
    import_module.insert.assert_called_once_with(str(source), "Doc")
