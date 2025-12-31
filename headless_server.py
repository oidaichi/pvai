import uuid
import logging

class HeadlessServer:
    """
    Mocks the ComfyUI PromptServer for headless execution.
    Captures events that would normally be sent via WebSockets.
    """
    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self.sockets_metadata = {} # No connected clients, so empty metadata
        self.last_node_id = None
        self.outputs = {} # Capture outputs
        self.logger = logging.getLogger("HeadlessServer")
        self.logger.setLevel(logging.INFO)

    def send_sync(self, event, data, sid=None):
        """
        Mock implementation of send_sync.
        Instead of sending to a websocket, we log the event.
        """
        if event == "progress":
            # data is typically {"value": x, "max": y}
            # Reduce log noise for progress
            pass 
        elif event == "execution_start":
            self.logger.info(f"Execution Started: {data}")
            self.outputs = {} # Reset outputs on new execution
        elif event == "execution_error":
            self.logger.error(f"Execution Error: {data}")
        elif event == "executed":
            self.logger.info(f"Node Executed: {data}")
            self.last_node_id = data.get("node")
            if "output" in data:
                self.outputs[self.last_node_id] = data["output"]
        else:
            # self.logger.debug(f"Event: {event}, Data: {data}")
            pass

    def get_pixel_value(self, node_id):
        # Used by some preview nodes?
        return None
