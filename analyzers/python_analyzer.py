"""
Python Source Code Static Analyzer
Analyzes Python source code using Python AST, Flake8, Bandit, and Radon.
Detects syntax errors, security vulnerabilities, logical pitfalls,
and complexity hotspots with line numbers and recommended fixes.
"""

import ast
import re
import os
import sys
import tempfile
import subprocess
import json
from typing import List, Dict, Any, Tuple
import radon.complexity as radon_cc
from radon.visitors import ComplexityVisitor


def analyze_python_code(source_code: str, file_name: str = "script.py") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute comprehensive static analysis on Python source code.
    Returns: (list_of_detected_issues, summary_metadata)
    """
    issues: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {
        "syntax_valid": True,
        "cyclomatic_complexity": 1,
        "maintainability_grade": "A",
        "has_critical_security": False
    }

    # -------------------------------------------------------------
    # 1. AST SYNTAX & STRUCTURAL ANALYSIS
    # -------------------------------------------------------------
    try:
        tree = ast.parse(source_code, filename=file_name)
    except SyntaxError as e:
        metadata["syntax_valid"] = False
        issues.append({
            "issue_type": "Syntax Error",
            "severity": "Critical",
            "description": f"Python Syntax Error: {e.msg}",
            "line_number": e.lineno or 1,
            "suggested_solution": "Review syntax around this line. Ensure correct colons, matching brackets, and proper Python indentation.",
            "tool_name": "Python AST"
        })
        # If syntax is completely broken, we return immediately with syntax issue
        return issues, metadata

    # -------------------------------------------------------------
    # 2. ADVANCED AST HEURISTIC & BUG CHECKER
    # -------------------------------------------------------------
    class CodeBugVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_nesting = 0
            self.max_nesting = 0
            self.in_loop = False

        def _enter_nest(self):
            self.current_nesting += 1
            self.max_nesting = max(self.max_nesting, self.current_nesting)

        def _leave_nest(self):
            self.current_nesting = max(0, self.current_nesting - 1)

        def visit_FunctionDef(self, node):
            self._enter_nest()
            # Check for mutable default argument
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append({
                        "issue_type": "Logical Bug / State Leak",
                        "severity": "High",
                        "description": f"Function '{node.name}' uses a mutable default argument (list/dict/set).",
                        "line_number": node.lineno,
                        "suggested_solution": "Use 'None' as the default argument value and initialize the mutable object inside the function body.",
                        "tool_name": "Python AST"
                    })

            # Check unreachable code after return or raise
            has_terminator = False
            for stmt in node.body:
                if has_terminator:
                    issues.append({
                        "issue_type": "Unreachable Code",
                        "severity": "Low",
                        "description": f"Statement in '{node.name}' after return/raise is unreachable.",
                        "line_number": stmt.lineno,
                        "suggested_solution": "Remove or refactor statements positioned after unconditional return or raise statements.",
                        "tool_name": "Python AST"
                    })
                    break
                if isinstance(stmt, (ast.Return, ast.Raise)):
                    has_terminator = True

            self.generic_visit(node)
            self._leave_nest()

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_If(self, node):
            self._enter_nest()
            self.generic_visit(node)
            self._leave_nest()

        def visit_For(self, node):
            self._enter_nest()
            self.generic_visit(node)
            self._leave_nest()

        def visit_While(self, node):
            self._enter_nest()
            self.generic_visit(node)
            self._leave_nest()

        def visit_BinOp(self, node):
            # Check for potential division by zero literal
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if isinstance(node.right, ast.Constant) and node.right.value == 0:
                    issues.append({
                        "issue_type": "Division by Zero",
                        "severity": "Critical",
                        "description": "Division or modulo by literal zero detected.",
                        "line_number": node.lineno,
                        "suggested_solution": "Ensure divisor is non-zero before performing arithmetic division.",
                        "tool_name": "Python AST"
                    })
                elif isinstance(node.right, ast.Name):
                    # Flag division by variable to recommend checking
                    issues.append({
                        "issue_type": "Arithmetic Risk",
                        "severity": "Low",
                        "description": f"Division by variable '{node.right.id}'. Ensure denominator is verified non-zero.",
                        "line_number": node.lineno,
                        "suggested_solution": f"Add guard check: if {node.right.id} != 0: ... else: ...",
                        "tool_name": "Python AST"
                    })
            self.generic_visit(node)

        def visit_ExceptHandler(self, node):
            # Check bare except or broad Exception catching
            if node.type is None:
                issues.append({
                    "issue_type": "Code Quality / Anti-Pattern",
                    "severity": "Medium",
                    "description": "Bare 'except:' caught without specifying exception type.",
                    "line_number": node.lineno,
                    "suggested_solution": "Catch specific exception types (e.g. 'except ValueError:') rather than masking all system errors.",
                    "tool_name": "Python AST"
                })
            elif isinstance(node.type, ast.Name) and node.type.id in ("BaseException", "Exception"):
                # Check if body is just pass
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    issues.append({
                        "issue_type": "Silenced Exception",
                        "severity": "High",
                        "description": f"Broad '{node.type.id}' caught and silently ignored with 'pass'.",
                        "line_number": node.lineno,
                        "suggested_solution": "Log the exception or handle the error condition rather than discarding it silently.",
                        "tool_name": "Python AST"
                    })
            self.generic_visit(node)

        def visit_Call(self, node):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("eval", "exec", "compile", "__import__"):
                metadata["has_critical_security"] = True
                issues.append({
                    "issue_type": "Security Vulnerability",
                    "severity": "Critical",
                    "description": f"Dynamic code execution via '{func_name}()' detected.",
                    "line_number": node.lineno,
                    "suggested_solution": "Avoid eval/exec; use safe alternatives such as ast.literal_eval() or explicit parsers.",
                    "tool_name": "Python AST"
                })
            elif func_name in ("system", "popen"):
                metadata["has_critical_security"] = True
                issues.append({
                    "issue_type": "Security Vulnerability",
                    "severity": "High",
                    "description": f"OS command execution via '{func_name}()' detected.",
                    "line_number": node.lineno,
                    "suggested_solution": "Use Python's subprocess module with shell=False and explicit argument lists.",
                    "tool_name": "Python AST"
                })
            self.generic_visit(node)

    visitor = CodeBugVisitor()
    visitor.visit(tree)

    if visitor.max_nesting >= 4:
        issues.append({
            "issue_type": "Code Complexity",
            "severity": "Medium",
            "description": f"High nesting depth ({visitor.max_nesting} levels) detected.",
            "line_number": 1,
            "suggested_solution": "Refactor nested logic into helper functions or use early return statements to flatten structure.",
            "tool_name": "Python AST"
        })

    # -------------------------------------------------------------
    # 3. RADON COMPLEXITY ANALYSIS
    # -------------------------------------------------------------
    try:
        radon_visitor = ComplexityVisitor.from_code(source_code)
        metadata["cyclomatic_complexity"] = radon_visitor.total_complexity
        for block in radon_visitor.blocks:
            if block.complexity > 10:
                issues.append({
                    "issue_type": "High Cyclomatic Complexity",
                    "severity": "High" if block.complexity > 15 else "Medium",
                    "description": f"Function/method '{block.name}' has cyclomatic complexity of {block.complexity} (Grade {block.letter}).",
                    "line_number": block.lineno,
                    "suggested_solution": "Break complex function into smaller, single-responsibility modular units.",
                    "tool_name": "Radon"
                })
    except Exception:
        pass

    # -------------------------------------------------------------
    # 4. SUBPROCESS TOOLS: FLAKE8 & BANDIT
    # -------------------------------------------------------------
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "analysis_target.py")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        # A. Run Flake8
        try:
            flake_proc = subprocess.run(
                [sys.executable, "-m", "flake8", "--isolated", "--format=%(row)d:%(code)s:%(text)s", temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in flake_proc.stdout.splitlines():
                parts = line.strip().split(":", 2)
                if len(parts) >= 3:
                    try:
                        row = int(parts[0])
                        code = parts[1].strip()
                        msg = parts[2].strip()

                        # Determine severity
                        if code.startswith("F821"):
                            sev = "High"
                            itype = "Undefined Variable"
                        elif code.startswith("F841"):
                            sev = "Medium"
                            itype = "Unused Variable"
                        elif code.startswith("F401"):
                            sev = "Low"
                            itype = "Unused Import"
                        elif code.startswith("E9"):
                            sev = "Critical"
                            itype = "Runtime Syntax Error"
                        elif code.startswith("E1") or code.startswith("W"):
                            sev = "Informational"
                            itype = "Style Violation (PEP8)"
                        else:
                            sev = "Low"
                            itype = "Coding Standard Violation"

                        issues.append({
                            "issue_type": itype,
                            "severity": sev,
                            "description": f"[{code}] {msg}",
                            "line_number": row,
                            "suggested_solution": f"Follow PEP 8 guidelines to correct [{code}].",
                            "tool_name": "Flake8"
                        })
                    except ValueError:
                        pass
        except Exception:
            pass

        # B. Run Bandit (Security Vulnerability Scanner)
        try:
            bandit_proc = subprocess.run(
                [sys.executable, "-m", "bandit", "-f", "json", "-q", temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            if bandit_proc.stdout:
                try:
                    bandit_data = json.loads(bandit_proc.stdout)
                    results = bandit_data.get("results", [])
                    for b_res in results:
                        b_sev = b_res.get("issue_severity", "MEDIUM").capitalize()
                        if b_sev not in ("Critical", "High", "Medium", "Low"):
                            b_sev = "Medium"
                        issues.append({
                            "issue_type": "Security Vulnerability",
                            "severity": b_sev,
                            "description": f"[{b_res.get('test_id')}] {b_res.get('issue_text')}",
                            "line_number": b_res.get("line_number", 1),
                            "suggested_solution": b_res.get("more_info", "Review and remediate security practice."),
                            "tool_name": "Bandit"
                        })
                except Exception:
                    pass
        except Exception:
            pass

    finally:
        # Clean up temporary file and directory safely
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception:
            pass

    # Deduplicate issues by (line_number, description)
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["line_number"], issue["description"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    # Sort issues by severity priority then line number
    severity_order = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4, "Informational": 5}
    unique_issues.sort(key=lambda x: (severity_order.get(x["severity"], 5), x["line_number"] or 0))

    return unique_issues, metadata
