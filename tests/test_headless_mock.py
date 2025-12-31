import unittest
import sys
import os
import uuid

# Ensure project root is in path
sys.path.append(os.getcwd())

import execution
import nodes
from headless_server import HeadlessServer

class TestHeadlessMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize custom nodes
        # This might fail if dependencies are missing, but we added graceful fallbacks in nodes.py
        nodes.init_custom_nodes()

    def test_simple_workflow(self):
        # Create a mock workflow using our custom nodes
        # ID 1: NanoBananaProT2I
        # ID 2: SaveVideoToUpload
        
        workflow = {
            "1": {
                "inputs": {
                    "prompt": "Test Prompt",
                    "seed": 123,
                    "steps": 1
                },
                "class_type": "NanoBananaProT2I"
            },
            "2": {
                "inputs": {
                    "images": ["1", 0],
                    "fps": 24.0,
                    "filename_prefix": "test_vid"
                },
                "class_type": "SaveVideoToUpload"
            }
        }
        
        server = HeadlessServer()
        executor = execution.PromptExecutor(server)
        
        # Execute
        # Note: In a real environment, validation is needed.
        valid, error, outputs, _ = execution.validate_prompt(workflow)
        self.assertTrue(valid, f"Validation failed: {error}")
        
        prompt_id = str(uuid.uuid4())
        # execute is synchronous in standard ComfyUI logic (even if it launches async tasks, it waits? No, PromptExecutor.execute runs the loop)
        executor.execute(workflow, prompt_id)
        
        # Check outputs
        # SaveVideoToUpload outputs a String (URL or Path)
        # HeadlessServer captures it in server.outputs
        
        self.assertIn("2", server.outputs)
        result = server.outputs["2"]
        print(f"Workflow Result: {result}")
        # Expecting a tuple with string path (since Supabase is likely missing in test env)
        self.assertTrue(isinstance(result, tuple))
        self.assertTrue(isinstance(result[0], str))
        self.assertTrue(result[0].endswith(".mp4"))

if __name__ == '__main__':
    unittest.main()
