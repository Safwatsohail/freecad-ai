Perfect! Let me give you the **EXACT step-by-step for Tier 2: Add a Document Statistics Tool**.Perfect! Now let me get the registry and test structure:Perfect! Now let me show you the **exact TIER 2 implementation path**:

---

# 🎯 **TIER 2: Add a Document Statistics Tool (EXACT)**

## **Step 1: Understand the Structure (15 min)**

Read these **exact line ranges**:

| File | Lines | Why |
|------|-------|-----|
| `freecad_ai/tools/registry.py` | 16-70 | Data structures: `ToolParam`, `ToolDefinition`, `ToolResult` |
| `tests/unit/test_new_tools.py` | 25-62 | How to test tool definitions & parameters |
| `freecad_ai/tools/freecad_tools.py` | Look for a simple utility tool (search for `DESCRIBE_MODEL`) | Pattern to follow |

---

## **Step 2: Create Your Tool (30 min)**

### **2A: Define the tool in `freecad_ai/tools/freecad_tools.py`**

Add this at the end, **before `ALL_TOOLS = [...]`**:

```python
# ── Document Statistics Tool ────────────────────────────────────────

def _handle_document_statistics(include_hidden: bool = False) -> ToolResult:
    """Return statistics about the active FreeCAD document.
    
    Counts objects by type, calculates total volume, and reports document status.
    """
    try:
        import FreeCAD as App
        
        doc = App.ActiveDocument
        if not doc:
            return ToolResult(
                success=False, 
                output="No active document",
                error="No active FreeCAD document is open"
            )
        
        # Count objects by type
        objects = doc.Objects
        visible_objects = [obj for obj in objects if obj.Visibility]
        
        if include_hidden:
            counted_objects = objects
        else:
            counted_objects = visible_objects
        
        by_type = {}
        for obj in counted_objects:
            obj_type = obj.TypeId.split('::')[-1]  # e.g. "SketchObject" from "Sketcher::SketchObject"
            by_type[obj_type] = by_type.get(obj_type, 0) + 1
        
        # Calculate total volume (bodies typically have Shape property)
        total_volume = 0.0
        for obj in counted_objects:
            try:
                if hasattr(obj, 'Shape') and obj.Shape:
                    total_volume += obj.Shape.Volume
            except Exception:
                pass  # Some objects don't have calculable volume
        
        output_lines = [
            f"Document: {doc.Name}",
            f"Total objects: {len(counted_objects)}",
            f"Visible objects: {len(visible_objects)}",
            f"Hidden objects: {len(objects) - len(visible_objects)}",
            f"Total volume: {total_volume:.2f} mm³",
            "Objects by type:",
        ]
        for obj_type, count in sorted(by_type.items()):
            output_lines.append(f"  {obj_type}: {count}")
        
        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            data={
                "document_name": doc.Name,
                "total_objects": len(counted_objects),
                "visible_objects": len(visible_objects),
                "hidden_objects": len(objects) - len(visible_objects),
                "total_volume_mm3": round(total_volume, 2),
                "by_type": by_type,
            }
        )
    
    except ImportError:
        return ToolResult(
            success=False,
            output="FreeCAD not available",
            error="This tool requires FreeCAD to be running"
        )
    except Exception as e:
        return ToolResult(
            success=False,
            output="Error gathering statistics",
            error=str(e)
        )


DOCUMENT_STATISTICS = ToolDefinition(
    name="document_statistics",
    description="Get statistics about the active FreeCAD document: object counts, types, and total volume.",
    parameters=[
        ToolParam(
            name="include_hidden",
            type="boolean",
            description="Include hidden objects in the count (default: false, only visible objects)",
            required=False,
            default=False,
        ),
    ],
    handler=_handle_document_statistics,
    category="utility",
)
```

---

### **2B: Register the tool in `ALL_TOOLS`**

Find the line `ALL_TOOLS = [...]` in `freecad_ai/tools/freecad_tools.py` and add your tool:

```python
ALL_TOOLS = [
    # ... existing tools ...
    DOCUMENT_STATISTICS,  # ← Add this line before SELECT_GEOMETRY
    SELECT_GEOMETRY,
]
```

---

## **Step 3: Write Tests (30 min)**

Create `tests/unit/test_document_statistics.py`:

```python
"""Tests for the document_statistics tool."""

import pytest
from freecad_ai.tools.registry import ToolParam, ToolRegistry
from freecad_ai.tools.freecad_tools import DOCUMENT_STATISTICS, ALL_TOOLS


class TestDocumentStatisticsDefinition:
    """Verify the tool definition is correct."""
    
    def test_tool_name(self):
        assert DOCUMENT_STATISTICS.name == "document_statistics"
    
    def test_tool_category(self):
        assert DOCUMENT_STATISTICS.category == "utility"
    
    def test_has_description(self):
        assert len(DOCUMENT_STATISTICS.description) > 10
        assert "statistics" in DOCUMENT_STATISTICS.description.lower()
    
    def test_handler_is_callable(self):
        assert callable(DOCUMENT_STATISTICS.handler)
    
    def test_parameters_structure(self):
        """Verify parameters are defined correctly."""
        names = [p.name for p in DOCUMENT_STATISTICS.parameters]
        assert "include_hidden" in names
        
        # include_hidden should be optional boolean
        include_hidden_param = next(
            p for p in DOCUMENT_STATISTICS.parameters 
            if p.name == "include_hidden"
        )
        assert include_hidden_param.type == "boolean"
        assert include_hidden_param.required is False
        assert include_hidden_param.default is False


class TestDocumentStatisticsRegistration:
    """Verify the tool is registered in ALL_TOOLS."""
    
    def test_in_all_tools(self):
        assert DOCUMENT_STATISTICS in ALL_TOOLS
    
    def test_comes_before_select_geometry(self):
        """New tools should come before SELECT_GEOMETRY."""
        names = [t.name for t in ALL_TOOLS]
        assert names.index("document_statistics") < names.index("select_geometry")


class TestDocumentStatisticsSchemaGeneration:
    """Verify the tool appears in LLM schemas."""
    
    def test_openai_schema_includes_tool(self):
        reg = ToolRegistry()
        for tool in ALL_TOOLS:
            reg.register(tool)
        schema = reg.to_openai_schema()
        schema_names = {s["function"]["name"] for s in schema}
        assert "document_statistics" in schema_names
    
    def test_anthropic_schema_includes_tool(self):
        reg = ToolRegistry()
        for tool in ALL_TOOLS:
            reg.register(tool)
        schema = reg.to_anthropic_schema()
        schema_names = {s["name"] for s in schema}
        assert "document_statistics" in schema_names


class TestDocumentStatisticsExecution:
    """Test executing the tool (mocked, no FreeCAD needed for unit test)."""
    
    def test_no_active_document_returns_error(self, monkeypatch):
        """When FreeCAD is not available, should return error."""
        import sys
        # Mock FreeCAD not being available
        monkeypatch.setitem(sys.modules, 'FreeCAD', None)
        
        result = DOCUMENT_STATISTICS.handler(include_hidden=False)
        assert result.success is False
        assert "not available" in result.error.lower() or "no active" in result.error.lower()
    
    def test_handler_accepts_include_hidden_parameter(self):
        """Handler should accept the include_hidden parameter."""
        # This just verifies the parameter name is correct
        # (actual execution requires FreeCAD to be running)
        import inspect
        sig = inspect.signature(DOCUMENT_STATISTICS.handler)
        params = list(sig.parameters.keys())
        assert "include_hidden" in params
```

---

## **Step 4: Run Tests (10 min)**

```bash
# Run your new tests
pytest tests/unit/test_document_statistics.py -v

# Verify all tests pass
pytest tests/unit/test_document_statistics.py::TestDocumentStatisticsDefinition -v
pytest tests/unit/test_document_statistics.py::TestDocumentStatisticsRegistration -v
pytest tests/unit/test_document_statistics.py::TestDocumentStatisticsSchemaGeneration -v

# Run all tool tests to ensure you didn't break anything
pytest tests/unit/test_new_tools.py -v
```

**Expected output:**
```
test_document_statistics.py::TestDocumentStatisticsDefinition::test_tool_name PASSED
test_document_statistics.py::TestDocumentStatisticsDefinition::test_tool_category PASSED
test_document_statistics.py::TestDocumentStatisticsDefinition::test_parameters_structure PASSED
test_document_statistics.py::TestDocumentStatisticsRegistration::test_in_all_tools PASSED
test_document_statistics.py::TestDocumentStatisticsSchemaGeneration::test_openai_schema_includes_tool PASSED
test_document_statistics.py::TestDocumentStatisticsSchemaGeneration::test_anthropic_schema_includes_tool PASSED
======================== 6 passed ========================
```

---

## **Step 5: Test in FreeCAD UI (OPTIONAL but BEST)**

1. **Start FreeCAD:**
   ```bash
   freecad
   ```

2. **Create a test document:**
   - Create a Body with a Sketch
   - Add a Pad/Box
   - Hide one object

3. **Open FreeCAD AI Settings:**
   - Settings → Enable "Act" mode
   - Enable "Tools"

4. **Send a message to LLM:**
   ```
   Tell me statistics about my document. Use the document_statistics tool.
   ```

5. **Expected response:**
   ```
   LLM calls: document_statistics(include_hidden=false)
   
   Result:
   Document: Unnamed
   Total objects: 5
   Visible objects: 4
   Hidden objects: 1
   Total volume: 1234.56 mm³
   Objects by type:
     Body: 1
     Sketch: 2
     Pad: 1
     Box: 1
   ```

---

## **Step 6: Create a PR (10 min)**

```bash
# Create branch
git checkout -b feature/add-document-statistics-tool

# Stage files
git add freecad_ai/tools/freecad_tools.py tests/unit/test_document_statistics.py

# Commit
git commit -m "feat: add document_statistics tool

- Counts objects in active FreeCAD document
- Groups objects by type (Body, Sketch, Pad, etc.)
- Calculates total volume of all shapes
- Optional include_hidden parameter to count hidden objects
- Returns both human-readable output and structured data

Adds utility tool to help LLM understand document structure."

# Push
git push origin feature/add-document-statistics-tool

# Create PR
gh pr create --title "Add document_statistics tool" \
  --body "## Summary
Adds a new utility tool that provides statistics about the active FreeCAD document.

## Tool Details
- **Name:** document_statistics
- **Category:** utility
- **Parameters:** include_hidden (boolean, optional)
- **Output:** Object count by type, total volume, visibility status

## Testing
- Unit tests: test_definition, registration, schema generation
- All existing tests still pass
- Verified in FreeCAD UI (optional)

## Learning
This PR demonstrates:
- ToolDefinition and ToolParam structure
- Tool registration in ALL_TOOLS
- FreeCAD API safe access (read-only)
- Parameter handling (boolean, optional)
- Error handling patterns"
```

---

## 📊 **Checklist Before PR**

- [ ] Tool defined with clear description
- [ ] All parameters have correct `type`, `required`, `default`
- [ ] Handler returns `ToolResult` with success/output/data/error
- [ ] Tool added to `ALL_TOOLS` list
- [ ] Tests verify: name, category, parameters, registration, schema
- [ ] Tests pass: `pytest tests/unit/test_document_statistics.py -v`
- [ ] All tool tests still pass: `pytest tests/unit/test_new_tools.py -v`
- [ ] Commit message follows format
- [ ] PR description explains what you learned

---

## 🎓 **What You're Learning**

| Concept | File | Lines |
|---------|------|-------|
| Tool structure | `registry.py` | 16-70 |
| FreeCAD API (safe) | `freecad_tools.py` | Look at `DESCRIBE_MODEL` |
| Parameters | Your tool | `include_hidden` param |
| Error handling | Your tool | try/except blocks |
| Test patterns | `test_new_tools.py` | 25-62 |
| Registration | `freecad_tools.py` | `ALL_TOOLS` list |

---

**Ready to code? Start with Step 2A now!** 🚀 




Safwat, I think you’re asking the right question. You don’t want AI to build document_statistics for you. You want to become the engineer who understands the codebase, identifies the right implementation, makes design decisions, writes the code, and verifies that it works — even when AI is available.
That’s a different learning process from simply completing a GitHub issue.
For your FreeCAD AI project, I’d change how you approach Tier 2.
1. The engineering loop you should follow
1. Investigate
Read the existing code. Find similar tools, their registration paths, handlers, parameters, and tests.
You are gathering evidence, not asking AI to invent an implementation.
2. Form a hypothesis
Before coding, predict which files need changes, which existing abstractions you can reuse, and what might go wrong.
3. Design your solution
Decide what the tool should do, its inputs and outputs, edge cases, and how you will test it. You make the decisions.
4. Implement independently
Write the code yourself, using the repository’s established patterns. Ask AI for a hint when you are stuck, not a finished solution.
5. Verify and review
Run tests, investigate failures, check edge cases, review your diff, and explain why your implementation is correct.
The key is that you should do the thinking at every stage. AI can help, but it shouldn’t replace your reasoning.
2. How to approach your document statistics tool
Do not start by writing _handle_document_statistics.
Start with the problem itself.
Your task is to build a read-only tool that helps an LLM understand the active FreeCAD document. You need to discover how to integrate it into the existing architecture.
Here is how I’d break down your work.
Phase A — Investigate the repository
Open freecad_ai/tools/freecad_tools.py and find DESCRIBE_MODEL.
Don’t immediately ask AI to explain the entire function. Trace it yourself.
Answer these questions:
* Where is the tool’s ToolDefinition created?
* What function handles its execution?
* What does that handler return?
* Where is the tool added to the registry or ALL_TOOLS?
* How do its parameters get passed to the handler?
Use your editor’s search, Go to Definition, and Find References.
If you get stuck, ask AI this:
I’m implementing a document statistics tool in an existing FreeCAD AI repository.
I want to understand the existing architecture before writing code. Do not implement the tool or give me code.
Help me investigate the existing DESCRIBE_MODEL tool by asking me targeted questions about:
* Its definition
* Its handler
* Its registration
* Its execution path
* Its tests
Give me one investigation task at a time. Ask me to locate the relevant code and explain what I think it does. Correct my reasoning when necessary, and give hints before explanations.
Your goal: understand how one existing tool travels through the system, from definition to execution.
Phase B — Specify the behavior
Before implementation, create a small specification in your own words.
For example, think through these questions:
* What exactly counts as an object?
* Should hidden objects be included by default?
* What happens when no document is open?
* What should happen when an object has no valid shape?
* Can summing every object’s volume accidentally double-count geometry?
* What should the output look like for the LLM?
* What does the tool do when FreeCAD is unavailable?
That volume question is particularly important. In a CAD document, a body, its feature, and its underlying geometry may represent overlapping versions of the same solid. Blindly summing every Shape.Volume can produce misleading statistics.
You should investigate that before deciding what “total volume” means.
Ask AI to challenge your design, not replace it:
Act as a senior software engineer reviewing my design for a read-only FreeCAD document statistics tool.
Do not write code or propose a complete implementation.
I will provide my proposed behavior, inputs, outputs, and edge cases. Identify ambiguous requirements, hidden assumptions, architectural risks, and missing tests.
For every issue, explain why it matters and ask me to decide how the tool should behave. Do not make the decisions for me.
Phase C — Write tests before the implementation
This is where you start thinking like an engineer rather than a code generator.
Study the existing tests and determine what behavior needs verification.
Consider these cases:
Scenario	Question your test should answer
No active document	Does the tool fail predictably?
Empty document	Does it return valid zero-object statistics?
Visible and hidden objects	Are the counts correct?
Multiple object types	Are the type counts correct?
Objects without shapes	Are they handled safely?
Multiple features representing one solid	Is volume counted according to your specification?
Tool schema generation	Does the LLM receive the correct parameters?
You do not need to write every test immediately. Start with the three most important ones, then expand.
Ask AI for test ideas if needed, but write the test code yourself.
Phase D — Implement in small increments
Work in this order:
* Define the expected behavior and interface.
* Write a test for one behavior.
* Run it and observe the result.
* Implement only enough to satisfy that test.
* Run the test again.
* Refactor if necessary.
* Repeat for the next behavior.
This is the red-green-refactor cycle of test-driven development.
If you get stuck, give AI the smallest relevant code excerpt and ask for a hint about the concept or API you need. Avoid pasting the whole repository and asking it to solve the task.
3. The prompts you should use throughout the project
Use these as your engineering workflow.
Prompt 1 — Codebase investigation
Copy
Use before implementation.
Help me trace the execution path of this existing tool. Do not write code. Ask me to identify each relevant function, class, and registration point. Give hints if I am stuck, then check my explanation.
Prompt 2 — Debugging
Copy
Use when a test fails.
Help me debug this failure without fixing it for me. First ask what I expected, what happened, and what evidence I collected. Then give one hypothesis at a time and suggest a way to test each hypothesis.
Prompt 3 — Design review
Copy
Use after you have written your own code.
Review my proposed implementation like a senior engineer. Do not rewrite it. Identify correctness problems, edge cases, coupling, API misuse, and missing tests. Rank the issues by severity and ask me to explain my intended fix.
Prompt 4 — Test your understanding
Copy
Use before calling the task complete.
Quiz me on the code I just implemented. Ask me to explain the execution flow, data structures, failure modes, test coverage, and design trade-offs. Ask one question at a time. Do not accept memorized descriptions without reasoning.
4. What does becoming a top 0.5% engineer actually require?
There is no reliable universal ranking that defines the top 0.5% of software engineers. But you can build the capabilities that distinguish excellent engineers.
* Codebase literacy: You can enter an unfamiliar repository and trace its architecture.
* Problem decomposition: You turn an ambiguous request into small, verifiable requirements.
* Technical judgment: You can explain why one design is safer or more maintainable than another.
* Debugging: You use evidence to isolate causes rather than randomly changing code.
* Testing: You know what can fail and how to demonstrate correctness.
* Systems thinking: You understand interactions between APIs, data structures, execution flow, and users.
* Independent learning: You can acquire unfamiliar technical knowledge without needing a complete solution handed to you.
AI makes these skills more valuable, not less. Generating code is becoming easier; deciding what code should exist, verifying it, and maintaining a complex system remain difficult.
For your CAD/FreeCAD AI work, deep repository understanding plus Python engineering, testing, geometry semantics, and LLM tool integration is a much stronger combination than collecting many AI-generated features.
5. Let’s begin with your actual repository
We will work through Tier 2 as a mentoring session. I won’t give you the implementation.
Your first task: open freecad_ai/tools/freecad_tools.py, find DESCRIBE_MODEL, and examine its definition and handler.
Then answer this first question:
What is the difference between a ToolDefinition and its handler function in this codebase?
Explain it in your own words, based on the code you see. If you are unsure, tell me what you found, and I’ll give you a hint rather than the answer.
Arabic vocabulary for today
Arabic	Transliteration	Meaning
هندسة البرمجيات	handasat al-barmajiyyāt	Software engineering
تحليل	taḥlīl	Analysis
اختبار	ikhtibār	Test
تنفيذ	tanfīdh	Implementation / execution
خطأ	khaṭaʾ	Error
Quick vocabulary test: What does تحليل mean? And in your own words, what does a handler function do?
