#!/usr/bin/env python3
"""Independent mutation tests for the draft QCHAIN contract's dispatch validator."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_qchain_contract as validation

class ContractTeeth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_path = validation.PATH
        cls.base = json.loads(cls.original_path.read_text())

    @classmethod
    def tearDownClass(cls):
        validation.PATH = cls.original_path

    def check_rejected(self, mutate):
        example = deepcopy(self.base)
        mutate(example)
        with tempfile.TemporaryDirectory() as root:
            validation.PATH = Path(root) / "dispatch.json"
            validation.PATH.write_text(json.dumps(example))
            with self.assertRaises(ValueError):
                validation.validate()
        validation.PATH = self.original_path

    def test_a_draft_contract_is_not_a_success_claim(self):
        validation.PATH = self.original_path
        self.assertEqual(validation.validate()["operator_ratification"], "PENDING")

    def test_false_pixel_uniqueness_is_rejected(self):
        self.check_rejected(lambda s: s["baseline"].update(distinct_f4_pixel_buffers=5))

    def test_unratified_gate_pass_is_rejected(self):
        self.check_rejected(lambda s: s["gates"][0].update(status="PASS"))

    def test_undeclared_publication_is_rejected(self):
        self.check_rejected(lambda s: s.update(publication="PUBLIC"))

    def test_gate_dependency_cycle_is_rejected(self):
        self.check_rejected(lambda s: s["gates"][0].update(depends_on=["G10"]))

    def test_missing_sabotage_law_is_rejected(self):
        self.check_rejected(lambda s: s["negative_laws"].pop())

    def test_orphaned_worker_is_rejected(self):
        self.check_rejected(lambda s: s["workers"].pop())

    def test_gpu_masquerade_as_cp03_is_rejected(self):
        self.check_rejected(lambda s: s.update(cp03_hybrid60="PASS"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
