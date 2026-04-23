import requests
from langchain_core.tools import tool

class PythonExecutorTool:
    def __init__(self, config):
        self.config = config
        # Default to port 5002 to avoid conflict with MusicGen (which is on 5001)
        self.api_url = getattr(config, "PYTHON_EXEC_URL", "http://127.0.0.1:5002").rstrip("/")
        self.code_executed = False  # State flag to track if code has been executed or tried
        self.code_failed = False

    def get_tool(self):
        @tool
        def run_python(code: str):
            """
            Run Python code to solve math, statistics, or logic problems.
            Available libraries: math, numpy, sympy, statistics.
            Rules:
            1. You MUST print() the final answer.
            2. You CANNOT use 'os', 'open', or 'requests'.
            3. Use this for complex calculations that require high precision.
            """
            try:
                self.code_executed = True
                print(f"DEBUG: Executing python code...\n {code}")

                response = requests.post(
                    f"{self.api_url}/run",
                    json={"code": code},
                    timeout = 15
                )

                if response.status_code != 200:
                    return f"Error: Python service returned {response.status_code}"
                
                result = response.json()

                stdout = result.get("stdout", "").strip()
                stderr = result.get("stderr", "").strip()
                error = result.get("error", "").strip()

                if error:
                    return f"Execution Error: {error}"
                
                output = []
                if stdout:
                    output.append(f"Output from code:\n{stdout}\n")
                if stderr:
                    output.append(f"Warnings/Errors:\n {stderr}\n")

                return "\n".join(output) if output else "Code executed successfully with no output."

            except Exception as e:
                print(f"DEBUG: Exception while connecting to Python Executor: {str(e)}")
                self.code_failed = True
                return "Failed to connect to Python execution service. Perform the calculation manually, but you MUST include a warning that the tool failed and your math solution may be inaccurate in. Tell the user in short."

        return run_python
                    