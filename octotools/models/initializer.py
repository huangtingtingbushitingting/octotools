import os
import sys
import importlib
import inspect
import traceback
from typing import Dict, Any, List, Tuple
import time
class Initializer:
    def __init__(self, enabled_tools: List[str] = [], model_string: str = None, verbose: bool = False, vllm_config_path: str = None):
        self.toolbox_metadata = {}# Where metadata will be stored
        self.available_tools = []#Final list of usable tools
        self.enabled_tools =enabled_tools # List from user/construct_solver
        self.load_all = self.enabled_tools == ["all"]
        self.model_string = model_string # llm model string获取要使用的LLM引擎
        self.verbose = verbose
        self.vllm_server_process = None
        self.vllm_config_path = vllm_config_path#本地大模型部署地址
        self.tool_directory_mapping = {}  # Maps tool class names to their directory names
        print("\n==> Initializing octotools...")
        print(f"Enabled tools: {self.enabled_tools}")
        print(f"LLM engine name: {self.model_string}")
        self._set_up_tools()

        # OctoVerilog normally connects to an already running OpenAI-compatible
        # vLLM endpoint. Only start a local server when a config was explicitly
        # supplied; implicit startup caused duplicate servers and GPU OOMs.
        if model_string.startswith("vllm-") and vllm_config_path:
            self.setup_vllm_server()

    def get_project_root(self):#动态地向上递归查找文件系统的父目录，直到找到包含octotools子文件夹的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))#获取当前文件所在的绝对路径目录
        while current_dir != '/':#只要没找到Linux系统的的根目录，就不断的向上迭代
            if os.path.exists(os.path.join(current_dir, 'octotools')):#判断当前所在的目录是否存在一个octotool的子文件夹
                return os.path.join(current_dir, 'octotools')#返回的是源代码路径
            current_dir = os.path.dirname(current_dir)
        raise Exception("Could not find project root")
        
    def load_tools_and_get_metadata(self) -> Dict[str, Any]:
        # Implementation of load_tools_and_get_metadata function
        print("Loading tools and getting metadata...")
        self.toolbox_metadata = {}
        octotools_dir = self.get_project_root()
        tools_dir = os.path.join(octotools_dir, 'tools')        
        # print(f"octotools directory: {octotools_dir}")
        # print(f"Tools directory: {tools_dir}")
        
        # 强行把项目目录塞进python的模块路径中，从而在不运行pip install -e.也可以直接使用from octotool.slover import的导入语句
        sys.path.insert(0, octotools_dir)#源代码本身目录
        sys.path.insert(0, os.path.dirname(octotools_dir))#源代码父级目录
        print(f"Updated Python path: {sys.path}")
        
        if not os.path.exists(tools_dir):
            print(f"Error: Tools directory does not exist: {tools_dir}")
            return self.toolbox_metadata

        for root, dirs, files in os.walk(tools_dir):#扫描、加载并注册所有的可用工具
            #root:当前正在遍历的文件夹的完整路径
            #dirs:当前文件夹的所有子文件夹名称
            #file当前文件下所有的文件名称
            # print(f"\nScanning directory: {root}")
            if 'tool.py' in files and (self.load_all or os.path.basename(root) in self.available_tools):#要么全量加载，要么当前文件夹的名字在self.available_tools 白名单里
                #结合第13行的代码，当enabled_tools时，直接使用enabled_tools中的工具，
                # 没有提供时，使用tool.py中全部的工具
                file = 'tool.py'
                module_path = os.path.join(root, file)
                module_name = os.path.splitext(file)[0]
                relative_path = os.path.relpath(module_path, octotools_dir)
                import_path = '.'.join(os.path.split(relative_path)).replace(os.sep, '.')[:-3]
            #路径翻译翻译成python可以识别的模块导入路径
                print(f"\n==> Attempting to import: {import_path}")
                try:
                    module = importlib.import_module(import_path)
                    for name, obj in inspect.getmembers(module):
                        #name:module中的对象名
                        #obj:module中的实际对象
                        if inspect.isclass(obj) and name.endswith('Tool') and name != 'BaseTool':
                            print(f"Found tool class: {name}")
                            # Store the directory mapping for later use in run_demo_commands
                            directory_name = os.path.basename(root)
                            self.tool_directory_mapping[name] = directory_name#{工具名：工具在的文件夹路径}
                            try:
                                # Check if the tool requires an LLM engine
                                if hasattr(obj, 'require_llm_engine') and obj.require_llm_engine:
                                    tool_instance = obj(model_string=self.model_string)
                                else:
                                    tool_instance = obj()

                                self.toolbox_metadata[name] = {
                                    'tool_name': getattr(tool_instance, 'tool_name', 'Unknown'),
                                    'tool_description': getattr(tool_instance, 'tool_description', 'No description'),
                                    'tool_version': getattr(tool_instance, 'tool_version', 'Unknown'),
                                    'input_types': getattr(tool_instance, 'input_types', {}),
                                    'output_type': getattr(tool_instance, 'output_type', 'Unknown'),
                                    'demo_commands': getattr(tool_instance, 'demo_commands', []),
                                    'user_metadata': getattr(tool_instance, 'user_metadata', {}), # This is a placeholder for user-defined metadata
                                    'require_llm_engine': getattr(obj, 'require_llm_engine', False),
                                }
                                #填写工具卡，元数据提取与缓存
                                print(f"Metadata for {name}: {self.toolbox_metadata[name]}")
                            except Exception as e:
                                print(f"Error instantiating {name}: {str(e)}")
                except Exception as e:
                    print(f"Error loading module {module_name}: {str(e)}")
                    
        print(f"\n==> Total number of tools imported: {len(self.toolbox_metadata)}")

        return self.toolbox_metadata

    def run_demo_commands(self) -> List[str]:#工具健康检查与白名单过滤
        print("\n==> Running demo commands for each tool...")
        self.available_tools = []

        for tool_name, tool_data in self.toolbox_metadata.items():
            print(f"Checking availability of {tool_name}...")

            try:
                # Import the tool module using the stored directory mapping
                directory_name = self.tool_directory_mapping.get(tool_name)#找到工具所在的文件夹名
                if directory_name is None:
                    # Fallback to the old logic if mapping is not found
                    directory_name = tool_name.lower().replace('_tool', '')
                module_name = f"tools.{directory_name}.tool"#拼接出模块导入路径
                module = importlib.import_module(module_name)

                # Get the tool class，从模块中取出类对象
                tool_class = getattr(module, tool_name)

                # Instantiate the tool
                if getattr(tool_class, 'require_llm_engine', False):
                    tool_instance = tool_class(model_string=self.model_string)
                else:
                    tool_instance = tool_class()

                #执行每个工具的demo_cimmands,验证工具在真是的API调用下是否可用
                """
                try:
                    if tool_instance.check_availability():
                        self.available_tools.append(tool_instance)
                        print(f"工具 {tool_class.__name__} 加载成功并验证通过。")
                    else:
                        print(f"工具 {tool_class.__name__} 验证失败（可能API不可用），跳过加载。")
                    except Exception as e:
                        print(f"验证工具 {tool_class.__name__} 时发生异常: {e}，跳过加载。")
                """

                # FIXME This is a temporary workaround to avoid running demo commands
                self.available_tools.append(tool_name)#available_tools只保存了tool_name

            except Exception as e:
                print(f"Error checking availability of {tool_name}: {str(e)}")
                print(traceback.format_exc())

        # update the tool metadata with the available tools,toolbox_metadata可能存在不健康的函数
        self.toolbox_metadata = {tool: self.toolbox_metadata[tool] for tool in self.available_tools}
        print("\n✅ Finished running demo commands for each tool.")
        # print(f"Updated total number of available tools: {len(self.toolbox_metadata)}")
        # print(f"Available tools: {self.available_tools}")
        return self.available_tools
    
    def _set_up_tools(self) -> None:#创建工具实列
        print("\n==> Setting up tools...")

        # Keep enabled tools，enabled tools：用户在初始化时传入的期望工具列表
        self.available_tools = [tool.lower().replace('_tool', '') for tool in self.enabled_tools]
        #防御性编程，防止run_demo_commands() 因为某种未知 bug 崩溃，至少可以看到客户原本想用哪些工具记录

        # Load tools and get metadata
        self.load_tools_and_get_metadata()
        
        # Run demo commands to determine available tools
        self.run_demo_commands()
        
        # Filter toolbox_metadata to include only available tools
        self.toolbox_metadata = {tool: self.toolbox_metadata[tool] for tool in self.available_tools}
        print("✅ Finished setting up tools.")
        print(f"✅ Total number of final available tools: {len(self.available_tools)}")
        print(f"✅ Final available tools: {self.available_tools}")

    def setup_vllm_server(self) -> None:#本地部署
        # Check if vllm is installed
        try:
            import vllm
        except ImportError:
            raise ImportError("If you'd like to use VLLM models, please install the vllm package by running `pip install vllm`.")
        
        # Validate config path if provided
        if self.vllm_config_path is not None and not os.path.exists(self.vllm_config_path):
            raise ValueError(f"VLLM config path does not exist: {self.vllm_config_path}")
            
        # Start the VLLM server
        command = ["vllm", "serve", self.model_string.replace("vllm-", ""), "--port", "8888"]
        if self.vllm_config_path is not None:
            command = ["vllm", "serve", "--config", self.vllm_config_path, "--port", "8888"]

        import subprocess#启动本地服务的模型进程
        vllm_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        print("Starting VLLM server...")
        while True:
            output = vllm_process.stdout.readline()
            error = vllm_process.stderr.readline()
            time.sleep(5)
            if output.strip() != "":
                print("VLLM server standard output:", output.strip())
            if error.strip() != "":
                print("VLLM server standard error:", error.strip())

            if "Application startup complete." in output or "Application startup complete." in error:
                print("VLLM server started successfully.")
                break

            if vllm_process.poll() is not None:
                print("VLLM server process terminated unexpectedly. Please check the output above for more information.")
                break

        self.vllm_server_process = vllm_process

if __name__ == "__main__":
    enabled_tools = ["Generalist_Solution_Generator_Tool"]
    initializer = Initializer(enabled_tools=enabled_tools)

    print("\nAvailable tools:")
    print(initializer.available_tools)

    print("\nToolbox metadata for available tools:")
    print(initializer.toolbox_metadata)
