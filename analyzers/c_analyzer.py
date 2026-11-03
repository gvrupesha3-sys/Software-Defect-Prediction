"""
C Source Code Static Analyzer
Analyzes C source code using GCC syntax diagnostics, Cppcheck static analysis,
Lizard cyclomatic complexity, and memory/buffer safety heuristics.
Never executes uploaded C programs.
"""

import os
import re
import shutil
import tempfile
import subprocess
from typing import List, Dict, Any, Tuple
import lizard


def analyze_c_code(source_code: str, file_name: str = "program.c") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Perform deep static analysis of C source code without program execution.
    Returns: (list_of_detected_issues, summary_metadata)
    """
    issues: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {
        "syntax_valid": True,
        "cyclomatic_complexity": 1,
        "memory_safety_warning": False
    }

    lines = source_code.splitlines()

    # -------------------------------------------------------------
    # 1. HEURISTIC SAFETY & MEMORY AUDIT
    # -------------------------------------------------------------
    has_malloc = bool(re.search(r'\b(malloc|calloc|realloc)\b', source_code))
    has_free = bool(re.search(r'\bfree\s*\(', source_code))
    if has_malloc and not has_free:
        metadata["memory_safety_warning"] = True
        issues.append({
            "issue_type": "Memory Leak Hazard",
            "severity": "High",
            "description": "Dynamic memory allocation detected (malloc/calloc) without any corresponding call to free().",
            "line_number": 1,
            "suggested_solution": "Ensure all dynamically allocated memory buffers are freed before exiting or going out of scope.",
            "tool_name": "Memory Safety Auditor"
        })

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # A. Extremely dangerous deprecated functions: gets()
        if re.search(r'\bgets\s*\(', stripped):
            metadata["memory_safety_warning"] = True
            issues.append({
                "issue_type": "Buffer Overflow Vulnerability",
                "severity": "Critical",
                "description": "Use of 'gets()' is inherently insecure and prone to buffer overflow exploits.",
                "line_number": idx,
                "suggested_solution": "Replace 'gets(buf)' with safe alternative: 'fgets(buf, sizeof(buf), stdin)'.",
                "tool_name": "Security Auditor"
            })

        # B. Unbounded string copy: strcpy / strcat
        if re.search(r'\b(strcpy|strcat)\s*\(', stripped):
            issues.append({
                "issue_type": "Buffer Overflow Risk",
                "severity": "High",
                "description": f"Unbounded string operation '{re.findall(r'strcpy|strcat', stripped)[0]}' detected.",
                "line_number": idx,
                "suggested_solution": "Use bounded equivalents like strncpy, strncat, or snprintf with buffer size limits.",
                "tool_name": "Security Auditor"
            })

        # C. sprintf without bounds
        if re.search(r'\bsprintf\s*\(', stripped):
            issues.append({
                "issue_type": "Buffer Overflow Risk",
                "severity": "Medium",
                "description": "Use of sprintf() does not check destination buffer boundaries.",
                "line_number": idx,
                "suggested_solution": "Use 'snprintf(buffer, sizeof(buffer), ...)' to prevent buffer overruns.",
                "tool_name": "Security Auditor"
            })

        # D. Division by literal zero
        if re.search(r'/\s*0\b', stripped):
            issues.append({
                "issue_type": "Division by Zero",
                "severity": "Critical",
                "description": "Division by literal 0 causes CPU floating point exception / crash.",
                "line_number": idx,
                "suggested_solution": "Ensure denominator expression is non-zero before dividing.",
                "tool_name": "Static Pattern Analyzer"
            })

        # E. malloc without NULL check on the same or adjacent line
        if re.search(r'=\s*\(\w+\s*\*?\)\s*malloc\s*\(', stripped) or re.search(r'=\s*malloc\s*\(', stripped):
            issues.append({
                "issue_type": "Unchecked Memory Allocation",
                "severity": "Medium",
                "description": "Memory allocation via malloc() without immediate NULL pointer validation.",
                "line_number": idx,
                "suggested_solution": "Always verify allocation success: 'if (ptr == NULL) { /* handle error */ }'.",
                "tool_name": "Memory Safety Auditor"
            })

    # -------------------------------------------------------------
    # 2. LIZARD CYCLOMATIC COMPLEXITY
    # -------------------------------------------------------------
    try:
        liz_res = lizard.analyze_file.analyze_source_code(file_name, source_code)
        if liz_res.function_list:
            for f in liz_res.function_list:
                if f.cyclomatic_complexity > 10:
                    issues.append({
                        "issue_type": "High Cyclomatic Complexity",
                        "severity": "High" if f.cyclomatic_complexity > 15 else "Medium",
                        "description": f"Function '{f.name}' cyclomatic complexity is {f.cyclomatic_complexity}.",
                        "line_number": f.start_line,
                        "suggested_solution": "Simplify function logic and extract helper functions to reduce decision branches.",
                        "tool_name": "Lizard"
                    })
    except Exception:
        pass

    # -------------------------------------------------------------
    # 3. CPPCHECK INTEGRATION (ADVANCED STATIC C ANALYZER)
    # -------------------------------------------------------------
    # Find cppcheck in PATH or known location
    cppcheck_path = shutil.which("cppcheck")
    if not cppcheck_path:
        possible = r"C:\Users\rupes\Downloads\rcb logo - Copy\mingw64\bin\cppcheck.EXE"
        if os.path.exists(possible):
            cppcheck_path = possible

    temp_dir = tempfile.mkdtemp()
    temp_c_file = os.path.join(temp_dir, "analysis_target.c")

    try:
        with open(temp_c_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        if cppcheck_path:
            try:
                cpp_proc = subprocess.run(
                    [
                        cppcheck_path,
                        "--enable=all",
                        "--inconclusive",
                        "--quiet",
                        "--template={line}:{severity}:{id}:{message}",
                        temp_c_file
                    ],
                    capture_output=True,
                    text=True,
                    timeout=8
                )

                output = cpp_proc.stdout + "\n" + cpp_proc.stderr
                for line in output.splitlines():
                    parts = line.strip().split(":", 3)
                    if len(parts) >= 4:
                        try:
                            line_no = int(parts[0]) if parts[0].isdigit() else 1
                            c_sev = parts[1].strip()
                            c_id = parts[2].strip()
                            msg = parts[3].strip()

                            if c_sev in ("error",):
                                sev = "Critical"
                                itype = "Memory / Pointer Error"
                            elif c_sev in ("warning",):
                                sev = "High"
                                itype = "Cppcheck Warning"
                            elif c_sev in ("performance",):
                                sev = "Medium"
                                itype = "Performance Optimization"
                            else:
                                sev = "Low"
                                itype = "Code Quality / Style"

                            issues.append({
                                "issue_type": itype,
                                "severity": sev,
                                "description": f"[{c_id}] {msg}",
                                "line_number": line_no,
                                "suggested_solution": "Review Cppcheck diagnostic advice to resolve pointer/memory constraint.",
                                "tool_name": "Cppcheck"
                            })
                        except Exception:
                            pass
            except Exception:
                pass

        # -------------------------------------------------------------
        # 4. GCC COMPILER SYNTAX DIAGNOSTICS (-fsyntax-only)
        # -------------------------------------------------------------
        gcc_path = shutil.which("gcc")
        if not gcc_path:
            possible_gcc = r"C:\Users\rupes\Downloads\rcb logo - Copy\mingw64\bin\gcc.EXE"
            if os.path.exists(possible_gcc):
                gcc_path = possible_gcc

        if gcc_path:
            try:
                # -fsyntax-only checks syntax and semantics WITHOUT producing object code or executing
                gcc_proc = subprocess.run(
                    [gcc_path, "-fsyntax-only", "-Wall", "-Wextra", temp_c_file],
                    capture_output=True,
                    text=True,
                    timeout=6
                )
                output = gcc_proc.stderr

                if gcc_proc.returncode != 0:
                    metadata["syntax_valid"] = False

                for line in output.splitlines():
                    match = re.search(r'analysis_target\.c:(\d+):(?:\d+:)?\s*(error|warning):\s*(.*)', line)
                    if match:
                        line_no, kind, desc = match.groups()
                        sev = "Critical" if kind == "error" else "Medium"
                        itype = "Compilation Error" if kind == "error" else "Compiler Warning"

                        issues.append({
                            "issue_type": itype,
                            "severity": sev,
                            "description": desc.strip(),
                            "line_number": int(line_no),
                            "suggested_solution": "Verify syntax, function prototypes, variable declarations, and type signatures.",
                            "tool_name": "GCC"
                        })
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
