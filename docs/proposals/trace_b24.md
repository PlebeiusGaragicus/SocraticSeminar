# Analysis and Fixes for Trace b24a9983-d59a-4a0b-a578-a80c4ca6d94f

## Problem Analysis

The trace shows the agent failed to create a 5th grade math quiz due to repeated "title is required" errors when attempting file creation. The workflow got stuck in a loop trying to execute `write_file` operations without proper title parameters.

## Exact Fixes Required

### 1. Middleware Parameter Validation Enhancement
**File**: `agents/src/deeptutor/middleware/client_tools.py`

Add validation logic to check for required parameters before file operations:
```python
def validate_write_file_params(params):
    """Validate write_file parameters and provide defaults or suggestions."""
    if not params.get('title'):
        # Provide a default title based on content context
        if 'quiz' in params.get('content', '').lower():
            params['title'] = "5th Grade Math Quiz"
        elif 'essay' in params.get('content', '').lower():
            params['title'] = "Essay Draft"
        else:
            params['title'] = "Untitled Document"
    return params
```

### 2. Enhanced Error Recovery in ClientToolsMiddleware
**File**: `deepagents/libs/deepagents/deepagents/middleware/filesystem.py`

Update error handling to provide fallback strategies:
```python
# In the write_file execution handler, add try/catch with recovery
try:
    # existing file creation logic
except Exception as e:
    if "title is required" in str(e).lower():
        # Fallback: create file with default title
        params['title'] = generate_default_title(params.get('content'))
        # retry file creation with default title
    else:
        raise e  # re-raise other errors
```

### 3. System Prompt Enhancement
**File**: `agents/src/deeptutor/graph.py`

Update the system prompt to include better guidance for handling parameter issues:
```markdown
## Parameter Handling Guidelines

When creating files, if a required parameter like 'title' is missing:
1. Generate an appropriate default title based on content context
2. Proceed with file creation using the generated title
3. Inform user that a default title was used if appropriate

## Fallback Strategies for File Operations
- If write_file fails due to missing parameters, automatically generate defaults
- For simple content (like quizzes), consider direct response instead of file creation when parameters are problematic
```

### 4. Default Title Generation Function
**File**: `agents/src/deeptutor/middleware/utils.py` (create new file)
```python
def generate_default_title(content: str, fallback_prefix="Untitled") -> str:
    """Generate a sensible default title based on content context."""
    if not content:
        return fallback_prefix
    
    # Extract keywords to suggest appropriate title
    content_lower = content.lower()
    
    if "quiz" in content_lower or "test" in content_lower:
        return "Quiz"
    elif "essay" in content_lower or "paper" in content_lower:
        return "Essay"
    elif "math" in content_lower or "grade" in content_lower:
        return "Math Assignment"
    elif "research" in content_lower:
        return "Research Document"
    else:
        # For generic content, create title from first few words
        words = content.strip()[:100].split()
        return " ".join(words[:5]) + "..." if len(words) > 5 else " ".join(words)
```

### 5. Improved ClientToolsMiddleware Error Handling
**File**: `agents/src/deeptutor/middleware/client_tools.py`

Enhance the interrupt handling to be more user-friendly:
```python
def handle_tool_execution_interrupt(tool_call):
    """Enhanced interrupt handling with parameter validation."""
    try:
        # Validate parameters before proceeding
        if tool_call.name == "write_file":
            validated_params = validate_write_file_params(tool_call.args)
            tool_call.args.update(validated_params)
        
        # Proceed with normal execution
        return execute_tool_call(tool_call)
        
    except Exception as e:
        # Provide more helpful error messages
        if "title is required" in str(e).lower():
            return {
                "type": "client_tool_execution",
                "tool_calls": [tool_call],
                "auto_approve": False,
                "requires_approval": True,
                "action_requests": [{
                    "name": tool_call.name,
                    "args": tool_call.args,
                    "description": f"File creation failed: {str(e)}. Would you like to use a default title?"
                }],
                "review_configs": [{
                    "action_name": tool_call.name,
                    "allowed_decisions": ["approve", "edit", "reject"]
                }]
            }
        raise e
```

## Implementation Sequence

1. Create the utils.py file with default title generation function
2. Update client_tools.py with enhanced validation and error handling  
3. Modify filesystem middleware to handle parameter recovery
4. Update system prompt in graph.py with better guidance
5. Add fallback strategies for common parameter issues

These changes will prevent the infinite retry loops seen in the trace by automatically handling missing title parameters and providing better user feedback.
