from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange
import re

class LoginForm(FlaskForm):
    username_or_email = StringField("Username or Email", validators=[DataRequired(message="Please enter your username or email.")])
    password = PasswordField("Password", validators=[DataRequired(message="Please enter your password.")])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=60, message="Full name must be between 2 and 60 characters.")
    ])
    username = StringField("Username", validators=[
        DataRequired(message="Username is required."),
        Length(min=3, max=30, message="Username must be between 3 and 30 characters.")
    ])
    email = StringField("Email Address", validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField("Password", validators=[
        DataRequired(message="Password is required."),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    confirm_password = PasswordField("Confirm Password", validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo("password", message="Passwords must match.")
    ])
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        if not re.match(r"^[a-zA-Z0-9_]+$", field.data.strip()):
            raise ValidationError("Username can only contain letters, numbers, and underscores.")

    def validate_password(self, field):
        pwd = field.data
        if not any(c.isalpha() for c in pwd):
            raise ValidationError("Password must contain at least one letter.")
        if not any(c.isdigit() for c in pwd):
            raise ValidationError("Password must contain at least one number.")


class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[
        DataRequired(message="Full name is required."),
        Length(min=2, max=60)
    ])
    email = StringField("Email Address", validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid email address.")
    ])
    submit = SubmitField("Update Profile")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters.")
    ])
    confirm_new_password = PasswordField("Confirm New Password", validators=[
        DataRequired(),
        EqualTo("new_password", message="Passwords must match.")
    ])
    submit = SubmitField("Change Password")


class CodeAnalysisForm(FlaskForm):
    language = SelectField("Programming Language", choices=[
        ("Python", "Python (.py)"),
        ("Java", "Java (.java)"),
        ("C", "C / C++ (.c, .h)")
    ], default="Python")
    file_name = StringField("File Name", default="source_code.py")
    source_code = TextAreaField("Source Code")
    code_file = FileField("Upload Source Code File", validators=[
        FileAllowed(['py', 'java', 'c', 'h', 'cpp'], "Only Python, Java, and C source files are allowed.")
    ])
    threshold = FloatField("Decision Threshold", default=0.30, validators=[
        NumberRange(min=0.05, max=0.95, message="Threshold must be between 0.05 and 0.95.")
    ])
    submit = SubmitField("Analyze Source Code")


class DirectPredictionForm(FlaskForm):
    dataset_preset = SelectField("Load NASA Dataset Preset", choices=[
        ("custom", "-- Manual Input / Custom Values --"),
        ("CM1_sample", "NASA CM1 (Spacecraft Instrument - C)"),
        ("JM1_sample", "NASA JM1 (Ground System Flight Sim - C)"),
        ("KC1_sample", "NASA KC1 (Storage Management - C++)"),
        ("KC2_sample", "NASA KC2 (Science Data Processing - C++)"),
        ("PC1_sample", "NASA PC1 (Earth Orbiting Satellite - C)")
    ], default="custom")
    language = SelectField("Target Language Profile", choices=[
        ("C", "C / C++ (NASA MDP Direct Baseline)"),
        ("Java", "Java (Metric Approximation)"),
        ("Python", "Python (Metric Approximation)")
    ], default="C")
    threshold = FloatField("Classification Decision Threshold", default=0.30, validators=[
        NumberRange(min=0.05, max=0.95)
    ])
    # 21 NASA Features
    loc = FloatField("loc (Lines of Code)", default=25.0)
    cyclomatic_complexity = FloatField("cyclomatic_complexity (v(g))", default=4.0)
    essential_complexity = FloatField("essential_complexity (ev(g))", default=1.0)
    design_complexity = FloatField("design_complexity (iv(g))", default=3.0)
    halstead_total_operators_operands = FloatField("halstead_total_operators_operands (N)", default=60.0)
    halstead_volume = FloatField("halstead_volume (V)", default=250.0)
    halstead_program_length = FloatField("halstead_program_length", default=60.0)
    halstead_difficulty = FloatField("halstead_difficulty (D)", default=12.0)
    halstead_intelligence = FloatField("halstead_intelligence (I)", default=20.0)
    halstead_effort = FloatField("halstead_effort (E)", default=3000.0)
    halstead_bugs = FloatField("halstead_bugs (B)", default=0.08)
    halstead_time = FloatField("halstead_time (T)", default=166.0)
    loc_code = FloatField("loc_code", default=20.0)
    loc_comment = FloatField("loc_comment", default=3.0)
    loc_blank = FloatField("loc_blank", default=2.0)
    loc_code_and_comment = FloatField("loc_code_and_comment", default=0.0)
    unique_operators = FloatField("unique_operators (mu1)", default=14.0)
    unique_operands = FloatField("unique_operands (mu2)", default=12.0)
    total_operators = FloatField("total_operators (N1)", default=35.0)
    total_operands = FloatField("total_operands (N2)", default=25.0)
    branch_count = FloatField("branch_count", default=7.0)
    submit = SubmitField("Predict Software Defect Likelihood")
