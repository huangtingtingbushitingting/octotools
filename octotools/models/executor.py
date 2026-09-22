import importlib
import os
import re
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional

from octotools.engine.factory import create_llm_engine
from octotools.models.formatters import ToolCommand

try:
    TimeoutError#寻找是否有TimeoutError这个变量，在模块导入是一次性执行
except NameError:
    class TimeoutError(Exception):#                                                                                             继承python的基类Exception
        pass
#实现跨版本兼容，python3.2中没有内置TimeoutError这个异常

def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")

class Executor:
    def __init__(self, llm_engine_name: str, workspace_dir: str = "runs/agent-work",  num_threads: int = 1, max_time: int = 120, max_output_length: int = 100000, verbose: bool = False):
        self.llm_engine_name = llm_engine_name#部分工具需要llm
        self.workspace_dir = str(Path(workspace_dir).resolve())
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        self._tool_instances = {}
        self.num_threads = num_threads
        self.max_time = max_time
        self.max_output_length = max_output_length
        self.verbose = verbose

    def set_workspace_dir(self, workspace_dir: str) -> None:
        """Set the per-run artifact directory."""
        self.workspace_dir = str(Path(workspace_dir).resolve())
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        for tool in self._tool_instances.values():
            tool.set_custom_output_dir(self.workspace_dir)

    @staticmethod
    def _tool_module_name(tool_name: str) -> str:
        base = re.sub(r"(?i)_?tool$", "", tool_name)
        if "_" not in base:
            base = re.sub(r"(?<!^)(?=[A-Z])", "_", base)
        return f"octotools.tools.{base.lower()}.tool"

    def _load_tool(self, tool_name: str):
        if tool_name in self._tool_instances:
            return self._tool_instances[tool_name]
        module = importlib.import_module(self._tool_module_name(tool_name))
        tool_class = getattr(module, tool_name)
        if getattr(tool_class, "require_llm_engine", False):
            tool = tool_class(model_string=self.llm_engine_name)
        else:
            tool = tool_class()
        tool.set_custom_output_dir(self.workspace_dir)
        self._tool_instances[tool_name] = tool
        return tool

    def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a registered tool directly without model-generated Python/eval."""
        try:
            return self._load_tool(tool_name).execute(**kwargs)
        except Exception as error:
            return {
                "success": False,
                "tool": tool_name,
                "error": f"{type(error).__name__}: {error}",
            }

    def generate_tool_command(self, question: str, image: str, context: str, sub_goal: str, tool_name: str, tool_metadata: Dict[str, Any]) -> Any:
        prompt_generate_tool_command = f"""
Task: Generate a precise command to execute the selected tool based on the given information.

Query: {question}
Image: {image}
Context: {context}
Sub-Goal: {sub_goal}
Selected Tool: {tool_name}
Tool Metadata: {tool_metadata}

Instructions:
1. Carefully review all provided information: the query, image path, context, sub-goal, selected tool, and tool metadata.
2. Analyze the tool's input_types from the metadata to understand required and optional parameters.
3. Construct a command or series of commands that aligns with the tool's usage pattern and addresses the sub-goal.
4. Ensure all required parameters are included and properly formatted.
5. Use appropriate values for parameters based on the given context, particularly the `Context` field which may contain relevant information from previous steps.
6. If multiple steps are needed to prepare data for the tool, include them in the command construction.

Output Format:
Provide your response in the following structure:

Analysis: <analysis>
Command Explanation: <explanation>
Generated Command:
```python
<command>
```

Where:
- <analysis> is a step-by-step analysis of the context, sub-goal, and selected tool to guide the command construction.
- <explanation> is a detailed explanation of the constructed command(s) and their parameters.
- <command> is the Python code to execute the tool, which can be one of the following types:
    a. A single line command with `execution = tool.execute()`.
    b. A multi-line command with complex data preparation, ending with `execution = tool.execute()`.
    c. Multiple lines of `execution = tool.execute()` calls for processing multiple items.

Rules:
1. The command MUST be valid Python code and include at least one call to `tool.execute()`.
2. Each `tool.execute()` call MUST be assigned to the 'execution' variable in the format `execution = tool.execute(...)`.
3. For multiple executions, use separate `execution = tool.execute()` calls for each execution.
4. The final output MUST be assigned to the 'execution' variable, either directly from `tool.execute()` or as a processed form of multiple executions.
5. Use the exact parameter names as specified in the tool's input_types.
6. Enclose string values in quotes, use appropriate data types for other values (e.g., lists, numbers).
7. Do not include any code or text that is not part of the actual command.
8. Ensure the command directly addresses the sub-goal and query.
9. Include ALL required parameters, data, and paths to execute the tool in the command itself.
10. If preparation steps are needed, include them as separate Python statements before the `tool.execute()` calls.

Examples (Not to use directly unless relevant):

Example 1 (Single line command):
Analysis: The tool requires an image path and a list of labels for object detection.
Command Explanation: We pass the image path and a list containing "baseball" as the label to detect.
Generated Command:
```python
execution = tool.execute(image="path/to/image", labels=["baseball"])
```

Example 2 (Multi-line command with data preparation):
Analysis: The tool requires an image path, multiple labels, and a threshold for object detection.
Command Explanation: We prepare the data by defining variables for the image path, labels, and threshold, then pass these to the tool.execute() function.
Generated Command:
```python
image = "path/to/image"
labels = ["baseball", "football", "basketball"]
threshold = 0.5
execution = tool.execute(image=image, labels=labels, threshold=threshold)
```

Example 3 (Multiple executions):
Analysis: We need to process multiple images for baseball detection.
Command Explanation: We call the tool for each image path, using the same label and threshold for all.
Generated Command:
```python
execution = tool.execute(image="path/to/image1", labels=["baseball"], threshold=0.5)
execution = tool.execute(image="path/to/image2", labels=["baseball"], threshold=0.5)
execution = tool.execute(image="path/to/image3", labels=["baseball"], threshold=0.5)
```

Some Wrong Examples:
Generated Command:
```python
execution1 = tool.execute(query="...")
execution2 = tool.execute(query="...")
```
Reason: only `execution = tool.execute` is allowed, not `execution1` or `execution2`.

Generated Command:
```python
urls = [
    "https://example.com/article1",
    "https://example.com/article2"
]

execution = tool.execute(url=urls[0])
execution = tool.execute(url=urls[1])
```
Reason: The command should process multiple items in a single execution, not separate executions for each item.

Remember: Your response MUST end with the Generated Command, which should be valid Python code including any necessary data preparation steps and one or more `execution = tool.execute(` calls, without any additional explanatory text. The format `execution = tool.execute` must be strictly followed, and the last line must begin with `execution = tool.execute` to capture the final output."""

        llm_generate_tool_command = create_llm_engine(model_string=self.llm_engine_name, use_cache=False, is_multimodal=False)
        tool_command = llm_generate_tool_command(prompt_generate_tool_command, response_format=ToolCommand)
        # 由大模型按照prompt_generate_tool_command生成调用工具的代码和工具执行的代码和工具执行的具体参数
        """ToolCommand规定输出的结构
        analysis:str
        explanation:str
        command:str
        """
        return tool_command

    def extract_explanation_and_command(self, response: Any) -> tuple:
        def normalize_code(code: str) -> str:
            # Remove leading and trailing whitespace and triple backticks
            return re.sub(r'^```python\s*', '', code).rstrip('```').strip()

        if isinstance(response, str):
            # Attempt to parse the response as JSON
            try:
                response_dict = json.loads(response)#将json格式化的数据字符串解析成python队形
                response = ToolCommand(**response_dict)
            except Exception as e:
                print(f"Failed to parse response as JSON: {str(e)}")
        if isinstance(response, ToolCommand):
            analysis = response.analysis.strip()
            explanation = response.explanation.strip()
            command = response.command.strip()
        else:
            # Extract analysis
            analysis_pattern = r"Analysis:(.*?)Command Explanation"
            analysis_match = re.search(analysis_pattern, response, re.DOTALL)
            analysis = analysis_match.group(1).strip() if analysis_match else "No analysis found."
            # Extract explanation
            explanation_pattern = r"Command Explanation:(.*?)Generated Command"
            explanation_match = re.search(explanation_pattern, response, re.DOTALL)
            explanation = explanation_match.group(1).strip() if explanation_match else "No explanation found."
            # Extract command
            command_pattern = r"Generated Command:.*?```python\n(.*?)```"
            command_match = re.search(command_pattern, response, re.DOTALL)
            command = command_match.group(1).strip() if command_match else "No command found."

        command = normalize_code(command)

        return analysis, explanation, command

    def execute_tool_command(self, tool_name: str, command: str) -> Any:#command是字符串的数据格式
        """
        Execute a tool command with timeout protection. If execution exceeds max_time seconds,
        the function will be interrupted and return a timeout message.

        Args:
            tool_name (str): Name of the tool to execute
            command (str): Command string containing tool.execute() calls

        Returns:
            Any: List of execution results or error message
        """

        def split_commands(command: str) -> List[str]:
            # Use regex to find all tool.execute() commands and their surrounding code
            pattern = r'.*?execution\s*=\s*tool\.execute\([^\n]*\)\s*(?:\n|$)'#识别execution = tool.execute(...)的完整语句
            blocks = re.findall(pattern, command, re.DOTALL)
            return [block.strip() for block in blocks if block.strip()]

        def execute_with_timeout(block: str, local_context: dict) -> Optional[str]:
            # Set up the timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_time)

            try:
                # Execute the block in the local context
                print('\n\n ','******local_context.keys()*******:',local_context.keys(),'\n\n')
                exec(block, globals(), local_context)
                print('\n\n ','******local_context*******:',local_context,'\n\n')
                #local_context保存的是tool实例，exec可以动态执行字符串形式的python语句，globals()使得local_context可以使用整个模块的变量
                result = local_context.get('execution')
                """
                每个具体的工具都会设置一个execute函数
                以及execution = tool.execute(相关参数)
                """
                print('\n\n ','******result*******:',result,'\n\n')
                signal.alarm(0)  # Disable the alarm
                return result
            except TimeoutError:
                return f"Execution timed out after {self.max_time} seconds"
            finally:
                signal.alarm(0)  # Ensure alarm is disabled even if other exceptions occur

        # Import the tool module and instantiate it
        module_name = self._tool_module_name(tool_name)#module_name存放具体工具的地址

        try:
            tool = self._load_tool(tool_name)

            # Split the command into blocks, execute each one and store execution results
            command_blocks = split_commands(command)
            executions = []#用于保存单个工具的执行结果

            for block in command_blocks:
                print('\n\n ','******block*******:',block,'\n\n')
                # Create a local context to safely execute the block
                local_context = {'tool': tool}#此时的工具是具体的工具

                # Execute the block with timeout protection
                result = execute_with_timeout(block, local_context)

                if result is not None:
                    executions.append(result)
                else:
                    executions.append(f"No execution captured from block: {block}")

            # Return all the execution results
            return executions
        except Exception as e:
            return f"Error in execute_tool_command: {str(e)}"
