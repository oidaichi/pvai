import unittest
import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from middleware.workflow_patcher import patch_workflow

class TestWorkflows(unittest.TestCase):
    def load_workflow(self, name):
        path = os.path.join("workflows", name)
        with open(path, 'r') as f:
            return json.load(f)

    def test_case_a_influencer(self):
        workflow = self.load_workflow("case_a_influencer.json")
        
        # Patch seed and ip_adapter_weight
        params = {
            "1": {"seed": 99999, "ip_adapter_weight": 1.5},
            "10": {"url": "https://new-product.com/img.jpg"}
        }
        patched = patch_workflow(workflow, params)
        
        self.assertEqual(patched["1"]["inputs"]["seed"], 99999)
        self.assertEqual(patched["1"]["inputs"]["ip_adapter_weight"], 1.5)
        self.assertEqual(patched["10"]["inputs"]["url"], "https://new-product.com/img.jpg")

    def test_case_b_lipsync(self):
        workflow = self.load_workflow("case_b_lipsync.json")
        
        # Patch expression
        params = {
            "3": {"expression_mode": "serious"},
            "2": {"prompt": "New script content"}
        }
        patched = patch_workflow(workflow, params)
        
        self.assertEqual(patched["3"]["inputs"]["expression_mode"], "serious")
        self.assertEqual(patched["2"]["inputs"]["prompt"], "New script content")

    def test_case_c_pose(self):
        workflow = self.load_workflow("case_c_pose.json")
        
        # Patch physics
        params = {
            "2": {"motion_scale": 2.0, "physics_bias": -0.5}
        }
        patched = patch_workflow(workflow, params)
        
        self.assertEqual(patched["2"]["inputs"]["motion_scale"], 2.0)
        self.assertEqual(patched["2"]["inputs"]["physics_bias"], -0.5)

if __name__ == '__main__':
    unittest.main()
