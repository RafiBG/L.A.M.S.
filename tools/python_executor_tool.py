import requests
from langchain_core.tools import tool

class PythonExecutorTool:
    def __init__(self, config):
        self.config = config
        # Default to port 5002 to avoid conflict with MusicGen (which is on 5001)
        self.api_url = getattr(config, "PYTHON_EXEC_URL", "http://127.0.0.1:5002").rstrip("/")

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
                return f"Failed to connect to Python Executor: {str(e)}"

        return run_python
                    