# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Guards for the bundled dev/test BPMN fixtures under ``wf/testdata/processes``."""

from actidoo_wfe.wf.constants import BPMN_DIRECTORY


def test_every_bundled_bpmn_has_diagram_interchange():
    """Each bundled .bpmn must carry diagram layout (``<bpmndi:BPMNDiagram>``).

    The engine executes a BPMN from its semantic model alone, but the frontend
    viewer (bpmn-js) needs the DI/layout section to render it — a BPMN without it
    fails to display. Guards against re-introducing a DI-less demo BPMN.
    """
    bpmn_files = sorted(BPMN_DIRECTORY.glob("**/*.bpmn"))
    assert bpmn_files, f"no bundled BPMN files found under {BPMN_DIRECTORY}"

    missing = [str(f.relative_to(BPMN_DIRECTORY)) for f in bpmn_files if "<bpmndi:BPMNDiagram" not in f.read_text(encoding="utf-8")]
    assert not missing, f"BPMN files without diagram interchange (won't render in the viewer): {missing}"
