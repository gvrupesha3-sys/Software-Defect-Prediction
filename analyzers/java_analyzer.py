"""
Java Source Code Static Analyzer
Analyzes Java source code using javac compiler diagnostics (syntax and linting only;
never executes code), Lizard complexity metrics, and static pattern heuristics.
Detects compilation errors, null dereference risks, exception handling flaws,
resource leaks, and security risks with line numbers and recommended fixes.
"""

import os
import re
import shutil
import tempfile
import subprocess
from typing import List, Dict, Any, Tuple
import lizard


def analyze_java_code(source_code: str, file_name: str = "Main.java") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Perform deep static analysis of Java source code without program execution.
    Returns: (list_of_detected_issues, summary_metadata)
    """
    issues: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {
        "compiles_cleanly": True,
        "cyclomatic_complexity": 1,
        "has_critical_error": False
    }

    lines = source_code.splitlines()

    # -------------------------------------------------------------
    # 1. STATIC PATTERN HEURISTICS & DEFECT INSPECTION
    # -------------------------------------------------------------
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comment lines
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # A. Potential Null Pointer Dereference risks
        # e.g., str.equals("literal") instead of "literal".equals(str)
        if re.search(r'\b\w+\.equals\(', stripped) and not re.search(r'"[^"]*"\.equals\(', stripped):
            match = re.search(r'(\b\w+)\.equals\(', stripped)
            var_name = match.group(1) if match else "variable"
            if var_name not in ("String", "Integer", "Boolean", "Object", "this", "super"):
                issues.append({
                    "issue_type": "Null Pointer Risk",
                    "severity": "Medium",
                    "description": f"Calling '{var_name}.equals(...)'. If '{var_name}' is null, this throws NullPointerException.",
                    "line_number": idx,
                    "suggested_solution": f"Use Objects.equals({var_name}, ...) or invert comparison: \"constant\".equals({var_name}).",
                    "tool_name": "Static Pattern Analyzer"
                })

        # B. Incorrect Exception Handling: Empty catch block
        if re.search(r'catch\s*\([^)]+\)\s*\{\s*\}', stripped) or (
            "catch" in stripped and idx < len(lines) and lines[idx].strip() == "}"
        ):
            issues.append({
                "issue_type": "Empty Exception Catch",
                "severity": "High",
                "description": "Empty catch block detected. Swallowing exceptions hides runtime failures.",
                "line_number": idx,
                "suggested_solution": "Log the caught exception or rethrow a descriptive domain exception.",
                "tool_name": "Static Pattern Analyzer"
            })

        # C. Generic Throwable or Exception caught
        if re.search(r'catch\s*\(\s*(Throwable|Exception)\s+\w+\s*\)', stripped):
            issues.append({
                "issue_type": "Overly Broad Exception Handling",
                "severity": "Low",
                "description": "Catching overly broad 'Exception' or 'Throwable' masks programming errors like OutOfMemoryError.",
                "line_number": idx,
                "suggested_solution": "Catch specific checked/unchecked exception subclasses instead.",
                "tool_name": "Static Pattern Analyzer"
            })

        # D. Security: Dangerous runtime calls
        if "Runtime.getRuntime().exec(" in stripped:
            issues.append({
                "issue_type": "Security Risk (Command Injection)",
                "severity": "Critical",
                "description": "Executing system commands via Runtime.getRuntime().exec() creates command injection hazards.",
                "line_number": idx,
                "suggested_solution": "Avoid executing OS commands or use ProcessBuilder with sanitized argument lists.",
                "tool_name": "Security Auditor"
            })

        if "System.exit(" in stripped:
            issues.append({
                "issue_type": "Abrupt JVM Termination",
                "severity": "Medium",
                "description": "Calling System.exit() forcibly stops the JVM and prevents orderly shutdown/cleanup.",
                "line_number": idx,
                "suggested_solution": "Throw an exception or return cleanly from the application entry point.",
                "tool_name": "Static Pattern Analyzer"
            })

        # E. Resource Leaks: Unclosed streams without try-with-resources
        if re.search(r'\b(FileInputStream|FileOutputStream|BufferedReader|Scanner|Connection|Statement)\s+\w+\s*=\s*new\b', stripped):
            if "try (" not in stripped and "try(" not in stripped:
                issues.append({
                    "issue_type": "Resource Leak Risk",
                    "severity": "Medium",
                    "description": "I/O resource instantiated without try-with-resources statement.",
                    "line_number": idx,
                    "suggested_solution": "Wrap I/O streams in a try-with-resources block: 'try (Resource r = ...) { ... }' to guarantee cleanup.",
                    "tool_name": "Static Pattern Analyzer"
                })

        # F. Arithmetic: Division by zero risk
        if re.search(r'/\s*0\b', stripped):
            issues.append({
                "issue_type": "Division by Zero",
                "severity": "Critical",
                "description": "Division by literal 0 will throw java.lang.ArithmeticException at runtime.",
                "line_number": idx,
                "suggested_solution": "Verify divisor is non-zero before arithmetic operations.",
                "tool_name": "Static Pattern Analyzer"
            })

        # G. Code Quality: public non-final field
        if re.search(r'\bpublic\s+(?!static\s+final\b|final\s+static\b|class\b|interface\b|enum\b|void\b|\w+\s*\()\w+\s+\w+\s*;', stripped):
            issues.append({
                "issue_type": "Encapsulation Violation",
                "severity": "Low",
                "description": "Public non-final field exposes internal class state.",
                "line_number": idx,
                "suggested_solution": "Make field private and provide getter/setter methods if external access is needed.",
                "tool_name": "Static Pattern Analyzer"
            })

    # -------------------------------------------------------------
    # 2. LIZARD COMPLEXITY ANALYSIS
    # -------------------------------------------------------------
    try:
        liz_res = lizard.analyze_file.analyze_source_code(file_name, source_code)
        if liz_res.function_list:
            for f in liz_res.function_list:
                if f.cyclomatic_complexity > 10:
                    issues.append({
                        "issue_type": "High Cyclomatic Complexity",
                        "severity": "High" if f.cyclomatic_complexity > 15 else "Medium",
                        "description": f"Method '{f.name}' has high cyclomatic complexity of {f.cyclomatic_complexity}.",
                        "line_number": f.start_line,
                        "suggested_solution": "Refactor method into smaller helper functions with fewer decision branches.",
                        "tool_name": "Lizard"
                    })
    except Exception:
        pass

    # -------------------------------------------------------------
    # 3. JAVAC COMPILER DIAGNOSTICS (SYNTAX & LINTING ONLY)
    # -------------------------------------------------------------
    javac_path = shutil.which("javac")
    if javac_path:
        temp_dir = tempfile.mkdtemp()
        try:
            # Extract class name or default to Main
            class_match = re.search(r'\b(?:public\s+)?class\s+([A-Za-z0-9_]+)', source_code)
            actual_class_name = class_match.group(1) if class_match else "Main"
            target_java_file = os.path.join(temp_dir, f"{actual_class_name}.java")

            with open(target_java_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            # Invoke javac in syntax & lint check mode (never execute code)
            javac_proc = subprocess.run(
                [javac_path, "-Xlint:all", "-d", temp_dir, target_java_file],
                capture_output=True,
                text=True,
                timeout=6
            )

            # Javac writes errors and warnings to stderr
            output = javac_proc.stderr + "\n" + javac_proc.stdout
            if javac_proc.returncode != 0:
                metadata["compiles_cleanly"] = False
                metadata["has_critical_error"] = True

            # Parse javac diagnostic lines: e.g. "Main.java:12: error: cannot find symbol"
            for line in output.splitlines():
                diag_match = re.search(r'([A-Za-z0-9_]+\.java):(\d+):\s*(error|warning):\s*(.*)', line)
                if diag_match:
                    _, line_no, kind, desc = diag_match.groups()
                    sev = "Critical" if kind == "error" else "Medium"
                    itype = "Compilation Error" if kind == "error" else "Compiler Warning"

                    issues.append({
                        "issue_type": itype,
                        "severity": sev,
                        "description": desc.strip(),
                        "line_number": int(line_no),
                        "suggested_solution": "Check type definitions, import declarations, and method signatures.",
                        "tool_name": "javac"
                    })

        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Deduplicate issues
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
