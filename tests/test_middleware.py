import unittest
from middleware.workflow_patcher import patch_workflow

class TestWorkflowPatcher(unittest.TestCase):
    def test_patch_existing_node(self):
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 100,
                    "steps": 20
                }
            }
        }
        params = {
            "3": {
                "seed": 200,
                "steps": 30
            }
        }
        result = patch_workflow(workflow, params)
        self.assertEqual(result["3"]["inputs"]["seed"], 200)
        self.assertEqual(result["3"]["inputs"]["steps"], 30)
        
    def test_patch_new_input_key(self):
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 100
                }
            }
        }
        params = {
            "3": {
                "denoise": 0.5
            }
        }
        result = patch_workflow(workflow, params)
        self.assertEqual(result["3"]["inputs"]["denoise"], 0.5)

    def test_ignore_missing_node(self):
        workflow = {
            "3": {
                "inputs": {"seed": 100}
            }
        }
        params = {
            "99": {
                "seed": 200
            }
        }
        result = patch_workflow(workflow, params)
        self.assertEqual(result["3"]["inputs"]["seed"], 100)
        self.assertNotIn("99", result)

if __name__ == '__main__':
    unittest.main()
