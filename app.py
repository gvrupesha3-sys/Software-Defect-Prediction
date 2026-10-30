import streamlit as st
import pandas as pd
import numpy as np
import ast
import tokenize
import io
import math
import keyword
import joblib
import re

# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Software Defect Prediction",
    page_icon="🐞",
    layout="wide"
)

st.title("🐞 Software Defect Prediction")
st.write(
    "Enter Python code to analyze software metrics and predict "
    "whether the code is defective or non-defective."
)

# ============================================================
# MODEL
# ============================================================

MODEL_FILE = "random_forest_defect_model.pkl"

try:
    model = joblib.load(MODEL_FILE)
except Exception as e:
    st.error("Model could not be loaded.")
    st.code(str(e))
    st.stop()

# ============================================================
# EXACT 21 FEATURES USED BY YOUR TRAINED MODEL
# ============================================================

FEATURES = [
    "loc",
    "cyclomatic_complexity",
    "essential_complexity",
    "design_complexity",
    "halstead_total_operators_operands",
    "halstead_volume",
    "halstead_program_length",
    "halstead_difficulty",
    "halstead_intelligence",
    "halstead_effort",
    "halstead_bugs",
    "halstead_time",
    "loc_code",
    "loc_comment",
    "loc_blank",
    "loc_code_and_comment",
    "unique_operators",
    "unique_operands",
    "total_operators",
    "total_operands",
    "branch_count"
]

# ============================================================
# PYTHON CODE INPUT
# ============================================================

default_code = """def calculate_average(numbers):
    total = 0

    for number in numbers:
        total += number

    if len(numbers) > 0:
        return total / len(numbers)
    else:
        return 0


values = [10, 20, 30, 40]
result = calculate_average(values)
print(result)
"""

code = st.text_area(
    "Enter Python Code",
    value=default_code,
    height=350
)

# ============================================================
# TOKEN ANALYSIS
# ============================================================

PYTHON_KEYWORDS = set(keyword.kwlist)

# Python punctuation is excluded from the software operator count
# because we want meaningful programming operators.
MEANINGFUL_OPERATORS = {
    "+", "-", "*", "/", "//", "%", "**",
    "==", "!=", "<", "<=", ">", ">=",
    "=", "+=", "-=", "*=", "/=", "//=",
    "%=", "**=", "&=", "|=", "^=", ">>=", "<<=",
    "&", "|", "^", "~", "<<", ">>",
    ":=", "@", "@=",
    "and", "or", "not", "in", "is"
}


def tokenize_code(source):
    """
    Extract Python operators and operands using Python's tokenizer.
    """

    operators = []
    operands = []
    comments = []

    try:
        tokens = tokenize.generate_tokens(
            io.StringIO(source).readline
        )

        for tok in tokens:

            tok_type = tok.type
            tok_string = tok.string

            # Comments
            if tok_type == tokenize.COMMENT:
                comments.append(tok_string)
                continue

            # Operators
            if tok_type == tokenize.OP:

                if tok_string in MEANINGFUL_OPERATORS:
                    operators.append(tok_string)

                continue

            # Python keyword operators
            if tok_type == tokenize.NAME:

                if tok_string in {"and", "or", "not", "in", "is"}:
                    operators.append(tok_string)

                elif tok_string not in PYTHON_KEYWORDS:
                    operands.append(tok_string)

                continue

            # Numeric/string constants
            if tok_type in {
                tokenize.NUMBER,
                tokenize.STRING
            }:
                operands.append(tok_string)

    except Exception:
        pass

    return operators, operands, comments


# ============================================================
# AST ANALYSIS
# ============================================================

class CodeAnalyzer(ast.NodeVisitor):

    def __init__(self):

        self.functions = 0
        self.classes = 0

        self.loops = 0
        self.conditions = 0
        self.branches = 0

        self.try_blocks = 0
        self.exceptions = 0

        self.calls = 0
        self.recursion = 0

        self.max_nesting = 0
        self.current_nesting = 0

        self.divisions = 0
        self.dangerous_calls = 0

        self.return_count = 0
        self.import_count = 0

        self.function_names = set()

    # -------------------------
    # Nesting
    # -------------------------

    def enter_nesting(self):

        self.current_nesting += 1

        self.max_nesting = max(
            self.max_nesting,
            self.current_nesting
        )

    def leave_nesting(self):

        self.current_nesting = max(
            0,
            self.current_nesting - 1
        )

    # -------------------------
    # Functions
    # -------------------------

    def visit_FunctionDef(self, node):

        self.functions += 1

        self.function_names.add(node.name)

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    def visit_AsyncFunctionDef(self, node):

        self.functions += 1

        self.function_names.add(node.name)

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    # -------------------------
    # Classes
    # -------------------------

    def visit_ClassDef(self, node):

        self.classes += 1

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    # -------------------------
    # Loops
    # -------------------------

    def visit_For(self, node):

        self.loops += 1
        self.branches += 1

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    def visit_AsyncFor(self, node):

        self.loops += 1
        self.branches += 1

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    def visit_While(self, node):

        self.loops += 1
        self.branches += 1

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    # -------------------------
    # Conditions
    # -------------------------

    def visit_If(self, node):

        self.conditions += 1
        self.branches += 1

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    def visit_IfExp(self, node):

        self.conditions += 1
        self.branches += 1

        self.generic_visit(node)

    # -------------------------
    # Match
    # -------------------------

    def visit_Match(self, node):

        self.branches += len(node.cases)

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    # -------------------------
    # Try / Except
    # -------------------------

    def visit_Try(self, node):

        self.try_blocks += 1

        self.branches += len(node.handlers)

        self.exceptions += len(node.handlers)

        self.enter_nesting()

        self.generic_visit(node)

        self.leave_nesting()

    # -------------------------
    # Calls
    # -------------------------

    def visit_Call(self, node):

        self.calls += 1

        function_name = ""

        if isinstance(node.func, ast.Name):
            function_name = node.func.id

        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr

        dangerous = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "system",
            "popen"
        }

        if function_name in dangerous:
            self.dangerous_calls += 1

        self.generic_visit(node)

    # -------------------------
    # Division
    # -------------------------

    def visit_BinOp(self, node):

        if isinstance(
            node.op,
            (
                ast.Div,
                ast.FloorDiv
            )
        ):
            self.divisions += 1

        self.generic_visit(node)

    # -------------------------
    # Return
    # -------------------------

    def visit_Return(self, node):

        self.return_count += 1

        self.generic_visit(node)

    # -------------------------
    # Imports
    # -------------------------

    def visit_Import(self, node):

        self.import_count += 1

        self.generic_visit(node)

    def visit_ImportFrom(self, node):

        self.import_count += 1

        self.generic_visit(node)


# ============================================================
# HALSTEAD METRICS
# ============================================================

def calculate_halstead(operators, operands):

    total_operators = len(operators)
    total_operands = len(operands)

    unique_operators = len(set(operators))
    unique_operands = len(set(operands))

    program_length = (
        total_operators +
        total_operands
    )

    vocabulary = (
        unique_operators +
        unique_operands
    )

    if vocabulary > 0 and program_length > 0:

        volume = (
            program_length *
            math.log2(vocabulary)
        )

    else:

        volume = 0.0

    if unique_operators > 0:

        difficulty = (
            (unique_operators / 2)
            *
            (
                total_operands /
                max(unique_operands, 1)
            )
        )

    else:

        difficulty = 0.0

    effort = volume * difficulty

    if difficulty > 0:

        intelligence = volume / difficulty

    else:

        intelligence = 0.0

    time_required = effort / 18

    # Halstead estimated delivered bugs
    bugs = volume / 3000

    return {
        "program_length": program_length,
        "volume": volume,
        "difficulty": difficulty,
        "intelligence": intelligence,
        "effort": effort,
        "time": time_required,
        "bugs": bugs,
        "unique_operators": unique_operators,
        "unique_operands": unique_operands,
        "total_operators": total_operators,
        "total_operands": total_operands
    }


# ============================================================
# METRIC EXTRACTION
# ============================================================

def extract_metrics(source):

    lines = source.splitlines()

    total_lines = len(lines)

    blank_lines = 0
    comment_lines = 0
    code_lines = 0
    code_comment_lines = 0

    for line in lines:

        stripped = line.strip()

        if not stripped:

            blank_lines += 1

        elif stripped.startswith("#"):

            comment_lines += 1

        else:

            code_lines += 1

            # Inline comment
            if "#" in line:

                code_comment_lines += 1

    # -------------------------
    # Syntax
    # -------------------------

    try:

        tree = ast.parse(source)

        syntax_error = None

    except SyntaxError as e:

        tree = None

        syntax_error = e

    # -------------------------
    # Token analysis
    # -------------------------

    operators, operands, comments = tokenize_code(source)

    halstead = calculate_halstead(
        operators,
        operands
    )

    # -------------------------
    # AST analysis
    # -------------------------

    analyzer = CodeAnalyzer()

    if tree is not None:

        analyzer.visit(tree)

    # -------------------------
    # McCabe-like complexity
    # -------------------------

    cyclomatic = (
        1
        +
        analyzer.conditions
        +
        analyzer.loops
        +
        analyzer.exceptions
    )

    # Approximation of essential complexity
    essential = max(
        1,
        cyclomatic
    )

    # Approximation of design complexity
    design = max(
        1,
        analyzer.functions +
        analyzer.classes
    )

    # -------------------------
    # 21 MODEL FEATURES
    # -------------------------

    metrics = {

        "loc":
            float(total_lines),

        "cyclomatic_complexity":
            float(cyclomatic),

        "essential_complexity":
            float(essential),

        "design_complexity":
            float(design),

        "halstead_total_operators_operands":
            float(
                halstead["program_length"]
            ),

        "halstead_volume":
            float(
                halstead["volume"]
            ),

        "halstead_program_length":
            float(
                halstead["program_length"]
            ),

        "halstead_difficulty":
            float(
                halstead["difficulty"]
            ),

        "halstead_intelligence":
            float(
                halstead["intelligence"]
            ),

        "halstead_effort":
            float(
                halstead["effort"]
            ),

        "halstead_bugs":
            float(
                halstead["bugs"]
            ),

        "halstead_time":
            float(
                halstead["time"]
            ),

        "loc_code":
            float(code_lines),

        "loc_comment":
            float(comment_lines),

        "loc_blank":
            float(blank_lines),

        "loc_code_and_comment":
            float(code_comment_lines),

        "unique_operators":
            float(
                halstead["unique_operators"]
            ),

        "unique_operands":
            float(
                halstead["unique_operands"]
            ),

        "total_operators":
            float(
                halstead["total_operators"]
            ),

        "total_operands":
            float(
                halstead["total_operands"]
            ),

        "branch_count":
            float(analyzer.branches)
    }

    extra = {

        "functions":
            analyzer.functions,

        "classes":
            analyzer.classes,

        "loops":
            analyzer.loops,

        "conditions":
            analyzer.conditions,

        "branches":
            analyzer.branches,

        "calls":
            analyzer.calls,

        "max_nesting":
            analyzer.max_nesting,

        "dangerous_calls":
            analyzer.dangerous_calls,

        "divisions":
            analyzer.divisions,

        "syntax_error":
            syntax_error,

        "operators":
            operators,

        "operands":
            operands
    }

    return metrics, extra


# ============================================================
# CODE-LEVEL RISK SCORE
# ============================================================

def calculate_code_risk(metrics, extra, source):

    risk = 0.0

    # --------------------------------
    # Syntax error
    # --------------------------------

    if extra["syntax_error"] is not None:

        return 100.0

    # --------------------------------
    # Complexity
    # --------------------------------

    risk += min(
        extra["max_nesting"] * 4,
        20
    )

    risk += min(
        extra["branches"] * 2,
        20
    )

    risk += min(
        extra["loops"] * 2,
        10
    )

    risk += min(
        extra["conditions"] * 1.5,
        10
    )

    # --------------------------------
    # Code size
    # --------------------------------

    loc = metrics["loc_code"]

    if loc > 50:
        risk += 5

    if loc > 100:
        risk += 5

    if loc > 200:
        risk += 5

    # --------------------------------
    # Operator/operand complexity
    # --------------------------------

    if metrics["total_operators"] > 20:
        risk += 5

    if metrics["total_operators"] > 50:
        risk += 5

    if metrics["total_operands"] > 40:
        risk += 5

    # --------------------------------
    # Dangerous patterns
    # --------------------------------

    risk += min(
        extra["dangerous_calls"] * 15,
        30
    )

    # Division operations
    risk += min(
        extra["divisions"] * 3,
        12
    )

    # --------------------------------
    # Exception handling
    # --------------------------------

    if re.search(
        r"except\s*:",
        source
    ):
        risk += 8

    # --------------------------------
    # TODO / FIXME
    # --------------------------------

    todo_count = len(
        re.findall(
            r"\b(TODO|FIXME|BUG)\b",
            source,
            re.IGNORECASE
        )
    )

    risk += min(
        todo_count * 5,
        15
    )

    # --------------------------------
    # Mutable default arguments
    # --------------------------------

    if re.search(
        r"def\s+\w+\([^)]*=\s*(\[\]|\{\})",
        source
    ):
        risk += 10

    # --------------------------------
    # Very long lines
    # --------------------------------

    long_lines = sum(
        1
        for line in source.splitlines()
        if len(line) > 100
    )

    risk += min(
        long_lines * 2,
        10
    )

    return min(
        round(risk, 2),
        100.0
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.button(
    "🔍 Analyze Code",
    type="primary",
    use_container_width=True
):

    if not code.strip():

        st.warning(
            "Please enter Python code first."
        )

        st.stop()

    # --------------------------------
    # Extract metrics
    # --------------------------------

    metrics, extra = extract_metrics(
        code
    )

    # --------------------------------
    # Syntax error
    # --------------------------------

    if extra["syntax_error"] is not None:

        st.error("❌ Python syntax error detected.")

        st.code(
            str(extra["syntax_error"])
        )

        st.info(
            "Syntax errors are classified as defective "
            "for this demonstration."
        )

        st.metric(
            "Defect Probability",
            "100.00%"
        )

        st.error(
            "🔴 DEFECTIVE"
        )

        st.stop()

    # --------------------------------
    # DataFrame for model
    # --------------------------------

    input_data = pd.DataFrame(
        [
            [
                metrics[feature]
                for feature in FEATURES
            ]
        ],
        columns=FEATURES
    )

    # --------------------------------
    # Random Forest prediction
    # --------------------------------

    probabilities = model.predict_proba(
        input_data
    )[0]

    classes = list(
        model.classes_
    )

    if 1 in classes:

        defect_index = classes.index(1)

        rf_probability = float(
            probabilities[defect_index]
        )

    else:

        rf_probability = 0.0

    # --------------------------------
    # Code-level static risk
    # --------------------------------

    code_risk = calculate_code_risk(
        metrics,
        extra,
        code
    )

    # --------------------------------
    # Hybrid probability
    #
    # 70% ML model
    # 30% static code analysis
    # --------------------------------

    final_probability = (
        (rf_probability * 0.70)
        +
        ((code_risk / 100) * 0.30)
    )

    final_probability = min(
        max(final_probability, 0.0),
        1.0
    )

    # --------------------------------
    # 50% decision threshold
    # --------------------------------

    THRESHOLD = 0.50

    if final_probability >= THRESHOLD:

        prediction = "DEFECTIVE"

    else:

        prediction = "NON-DEFECTIVE"

    # ========================================================
    # RESULT
    # ========================================================

    st.divider()

    st.subheader(
        "Prediction Result"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Defect Probability",
            f"{final_probability * 100:.2f}%"
        )

    with col2:

        st.metric(
            "Static Code Risk",
            f"{code_risk:.2f}%"
        )

    with col3:

        st.metric(
            "Random Forest Probability",
            f"{rf_probability * 100:.2f}%"
        )

    if prediction == "DEFECTIVE":

        st.error(
            "🔴 DEFECTIVE"
        )

    else:

        st.success(
            "🟢 NON-DEFECTIVE"
        )

    st.caption(
        "Decision threshold: 50%"
    )

    # ========================================================
    # BASIC CODE INFORMATION
    # ========================================================

    st.divider()

    st.subheader(
        "Python Code Analysis"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Lines of Code",
            int(metrics["loc_code"])
        )

    with c2:

        st.metric(
            "Operators",
            int(metrics["total_operators"])
        )

    with c3:

        st.metric(
            "Operands",
            int(metrics["total_operands"])
        )

    with c4:

        st.metric(
            "Branches",
            int(metrics["branch_count"])
        )

    c5, c6, c7, c8 = st.columns(4)

    with c5:

        st.metric(
            "Functions",
            extra["functions"]
        )

    with c6:

        st.metric(
            "Conditions",
            extra["conditions"]
        )

    with c7:

        st.metric(
            "Loops",
            extra["loops"]
        )

    with c8:

        st.metric(
            "Max Nesting",
            extra["max_nesting"]
        )

    # ========================================================
    # OPERATOR / OPERAND DETAILS
    # ========================================================

    st.divider()

    st.subheader(
        "Operators and Operands"
    )

    op1, op2 = st.columns(2)

    with op1:

        st.write(
            "**Operators found**"
        )

        if extra["operators"]:

            st.code(
                ", ".join(
                    extra["operators"]
                )
            )

        else:

            st.write(
                "No operators detected."
            )

    with op2:

        st.write(
            "**Operands found**"
        )

        if extra["operands"]:

            st.code(
                ", ".join(
                    extra["operands"]
                )
            )

        else:

            st.write(
                "No operands detected."
            )

    # ========================================================
    # 21 METRICS
    # ========================================================

    st.divider()

    st.subheader(
        "21 Features"
    )

    feature_table = pd.DataFrame(
        {
            "Metric": FEATURES,
            "Value": [
                round(
                    metrics[feature],
                    4
                )
                for feature in FEATURES
            ]
        }
    )

    st.dataframe(
        feature_table,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # RISK FINDINGS
    # ========================================================

    st.divider()

    st.subheader(
        "Code Quality Findings"
    )

    findings = []

    if extra["max_nesting"] >= 4:

        findings.append(
            "⚠️ High nesting depth detected."
        )

    if extra["branches"] >= 8:

        findings.append(
            "⚠️ Large number of branches detected."
        )

    if extra["loops"] >= 4:

        findings.append(
            "⚠️ Multiple loops detected."
        )

    if extra["dangerous_calls"] > 0:

        findings.append(
            "🔴 Potentially dangerous function call detected."
        )

    if extra["divisions"] > 0:

        findings.append(
            "⚠️ Division operation detected; zero-denominator "
            "handling should be checked."
        )

    if re.search(
        r"\b(TODO|FIXME|BUG)\b",
        code,
        re.IGNORECASE
    ):

        findings.append(
            "⚠️ TODO/FIXME/BUG marker detected."
        )

    if not findings:

        findings.append(
            "✅ No major static-risk patterns detected."
        )

    for finding in findings:

        st.write(
            finding
        )

    # ========================================================
    # MODEL INPUT
    # ========================================================

    with st.expander(
        "View values sent to Random Forest"
    ):

        st.dataframe(
            input_data,
            use_container_width=True,
            hide_index=True
        )

  
