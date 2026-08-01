# Chapter 4: Memory

Welcome back! In the last chapter, we learned about **[Tool](03_tool_.md)s**, the specialized pieces of equipment `octotools` uses to perform specific actions like searching the web or analyzing images.

Now, imagine the [Solver](01_solver_.md) is working on a complex problem. It uses a tool to find some information, then uses another tool to process that information. How does it keep track of what it did in the first step so it can use that information in the second step? How does it avoid repeating the same work? It needs a way to *remember*.

This is where the **Memory** component comes in!

## What is Memory?

Think of the **Memory** like a **Project Logbook** or a **Scratchpad**. As the [Solver](01_solver_.md) works through the problem, step-by-step, the `Memory` component carefully records everything important that happens.

What exactly does it record?

1.  **The Original Request:** It remembers the initial question (the `query`) you asked the [Solver](01_solver_.md).
2.  **Any Files:** If you provided any files (like images or documents) along with your query, the `Memory` keeps track of them and their descriptions.
3.  **The Action History:** This is the most detailed part. For every single step the [Solver](01_solver_.md) takes, the `Memory` logs:
    *   Which [Tool](03_tool_.md) was used (e.g., `Web_Search_Tool`).
    *   What the specific goal for that step was (e.g., "Find current weather in Paris").
    *   The exact command given to the tool (e.g., `execute(query="current weather in Paris")`).
    *   The result obtained from the tool (e.g., `["Paris: Currently 15°C, partly cloudy..."]`).

Essentially, `Memory` builds a complete history of the problem-solving journey. It doesn't do any thinking itself, but it holds all the context and past results.

## Why is Memory Important? Context is Key!

This logbook is crucial for the smart parts of the system, especially the [Planner](05_planner_.md). When the [Planner](05_planner_.md) needs to decide the *next* step, it doesn't just look at the original query. It looks at the **entire history** stored in `Memory`.

Imagine you ask: "Search for the latest AI papers on arXiv. Then, summarize the first result."

1.  **Step 1:** The [Planner](05_planner_.md) decides to use an `ArXiv_Search_Tool`. The [Executor](06_executor_.md) runs it.
2.  **Update Memory:** The [Solver](01_solver_.md) records in `Memory`: "Used `ArXiv_Search_Tool`, searched for 'latest AI papers', got results: [Paper A, Paper B, ...]".
3.  **Step 2:** The [Planner](05_planner_.md) looks at the `Memory`. It sees the original goal ("summarize the first result") and the result from Step 1 ("Paper A, Paper B, ...").
4.  **Informed Decision:** Based on this history, the [Planner](05_planner_.md) knows it needs to take "Paper A" and use a `Summarizer_Tool` on it.

Without the `Memory`, the [Planner](05_planner_.md) would have no idea what "the first result" refers to. `Memory` provides the necessary **context** built up over previous steps.

## How is Memory Used? (Behind the Scenes)

As a user of `octotools`, you typically don't interact with the `Memory` object directly when using the main [Solver](01_solver_.md). The `Solver` manages it internally.

Here's a conceptual idea of how the `Solver` updates the `Memory` after a step is completed:

```python
# --- This happens inside the Solver's loop ---

# Let's say Step 1 just finished...
step_number = 1
tool_used = "Web_Search_Tool"
goal_for_step = "Find the capital of France"
command_run = "execute(query='capital of France')"
result_obtained = "Paris"

# The Solver gets the Memory object it's managing
# (Assume 'solver_memory' is the Memory instance)

# The Solver adds the details of this step to the Memory
solver_memory.add_action(
    step_count=step_number,
    tool_name=tool_used,
    sub_goal=goal_for_step,
    command=command_run,
    result=result_obtained
)

print("Action logged in Memory!")

# --- Later, the Planner needs context ---

# The Planner asks the Memory for the history
past_actions = solver_memory.get_actions()
print("\nPlanner checking past actions:")
print(past_actions)

# The Planner uses 'past_actions' to decide the next step...
```

**Explanation:**

1.  After the [Executor](06_executor_.md) runs a [Tool](03_tool_.md) and gets a result, the [Solver](01_solver_.md) gathers all the information about that step.
2.  It calls the `memory.add_action(...)` method, passing in the details: step number, tool name, goal, command, and result.
3.  The `Memory` object stores this information internally.
4.  Later, when the [Planner](05_planner_.md) needs to decide the next step, it can call methods like `memory.get_actions()` to retrieve the history and make an informed choice.

## Under the Hood: How Memory Stores Information

The `Memory` class is essentially a container designed to hold the query, files, and action log in an organized way.

**1. Internal Structure (`octotools/models/memory.py`)**

When a `Memory` object is created, it initializes empty placeholders for the information it will store.

```python
# Simplified from octotools/models/memory.py
from typing import Dict, Any, List, Optional

class Memory:
    def __init__(self):
        """Initializes an empty memory log."""
        self.query: Optional[str] = None # Placeholder for the user's query
        self.files: List[Dict[str, str]] = [] # List to store file info
        self.actions: Dict[str, Dict[str, Any]] = {} # Dictionary to store action steps
        print("Memory initialized (empty).")

    def set_query(self, query: str) -> None:
        """Stores the initial query."""
        self.query = query
        print(f"Memory: Query set to '{query}'")

    # ... other methods like add_file, add_action ...
```

**Explanation:**

*   The `__init__` method sets up three main attributes:
    *   `self.query`: Will hold the user's question as a string. Starts as `None`.
    *   `self.files`: Will hold a list of files. Each file is represented as a dictionary (e.g., `{'file_name': 'image.jpg', 'description': 'User provided image'}`). Starts as an empty list `[]`.
    *   `self.actions`: Will hold the step-by-step log. It's a dictionary where keys are step names (like "Action Step 1") and values are dictionaries containing details of that action. Starts as an empty dictionary `{}`.

**2. Adding Information**

Methods like `add_file` and `add_action` are used (primarily by the [Solver](01_solver_.md)) to populate these attributes.

```python
# Simplified from octotools/models/memory.py
class Memory:
    # ... __init__ and set_query from above ...

    def add_file(self, file_name: str, description: Optional[str] = None) -> None:
        """Adds a file reference to the memory."""
        if description is None:
            # If no description provided, generate a default one
            description = f"File named {file_name}" # Simplified default
        self.files.append({
            'file_name': file_name,
            'description': description
        })
        print(f"Memory: Added file '{file_name}'")

    def add_action(self, step_count: int, tool_name: str, sub_goal: str, command: str, result: Any) -> None:
        """Adds a completed action step to the memory log."""
        action_details = {
            'tool_name': tool_name,
            'sub_goal': sub_goal,
            'command': command,
            'result': result,
        }
        step_name = f"Action Step {step_count}" # e.g., "Action Step 1"
        self.actions[step_name] = action_details
        print(f"Memory: Logged {step_name} (Tool: {tool_name})")

    # ... methods to retrieve information ...
```

**Explanation:**

*   `add_file`: Takes a file name and an optional description. It creates a dictionary for the file and appends it to the `self.files` list.
*   `add_action`: Takes all the details of a completed step. It bundles them into an `action_details` dictionary and adds that dictionary to the `self.actions` dictionary, using a formatted step name (like "Action Step 1") as the key.

**3. Retrieving Information**

Other components, like the [Planner](05_planner_.md), need to read the information stored in `Memory`.

```python
# Simplified from octotools/models/memory.py
class Memory:
    # ... __init__, set_query, add_file, add_action ...

    def get_query(self) -> Optional[str]:
        """Returns the stored query."""
        return self.query

    def get_files(self) -> List[Dict[str, str]]:
        """Returns the list of stored files."""
        return self.files

    def get_actions(self) -> Dict[str, Dict[str, Any]]:
        """Returns the dictionary of all logged actions."""
        return self.actions
```

**Explanation:**

*   These `get_...` methods simply return the current value of the corresponding attribute (`self.query`, `self.files`, `self.actions`). This allows other parts of the system to access the history.

**4. Diagram: How Memory Gets Updated**

Here's a simplified sequence showing the [Solver](01_solver_.md) updating the `Memory` after the [Executor](06_executor_.md) runs a [Tool](03_tool_.md).

```mermaid
sequenceDiagram
    participant S as Solver
    participant E as Executor
    participant T as Specific Tool
    participant M as Memory

    Note over S, E, T: Inside the Solver's loop...
    S->>E: execute_tool_command(Tool, Command)
    E->>T: execute(Command details)
    T-->>E: Result
    E-->>S: Result
    S->>M: add_action(step, tool, goal, command, result)
    M-->>S: Action logged
    Note over S: Memory is now updated for the next step.
```

This diagram shows the flow: The `Solver` directs the `Executor` to use a `Tool`. Once the result comes back to the `Solver`, it logs the entire action (tool used, command, result, etc.) into the `Memory`. This updated `Memory` is then available for the next planning cycle.

## Conclusion

The `Memory` component is the essential **logbook** for the `octotools` system. It doesn't perform actions or make decisions, but it diligently records the initial request, associated files, and every step taken during the problem-solving process. This recorded history provides the crucial context that allows the [Planner](05_planner_.md) to make intelligent, informed decisions about what to do next. Without `Memory`, the system would be unable to follow multi-step reasoning or build upon previous findings.

## Next Steps

Now that we understand how `octotools` remembers what it has done ([Memory](04_memory_.md)), let's look at the component that uses this memory to figure out the *next* step: the strategist of the operation.

Ready to learn how the system plans its actions? Let's proceed to the next chapter: **[Planner](05_planner_.md)**.

---

Generated by [AI Codebase Knowledge Builder](https://github.com/The-Pocket/Tutorial-Codebase-Knowledge)