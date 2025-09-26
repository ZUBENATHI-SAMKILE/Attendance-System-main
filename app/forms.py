from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, StringField, PasswordField, SelectField, SubmitField, DateField, TextAreaField, TimeField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError
from flask_wtf.file import FileField, FileAllowed
from app.models import Role, User, Module, ClassType

def dut_email_domain_check(form, field):
    """Custom validator for DUT email domains"""
    if field.data:
        if not (field.data.endswith('@dut4life.ac.za') or field.data.endswith('@dut.ac.za')):
            raise ValidationError('Please use a valid DUT email address (@dut4life.ac.za or @dut.ac.za)')

def student_number_length_check(form, field):
    """Custom validator for student number length"""
    if form.role.data == Role.student.value and field.data:
        if len(field.data) != 8 or not field.data.startswith('22'):
            raise ValidationError('Student number must be 8 characters long and start with 22')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), dut_email_domain_check])
    role = SelectField('Role', choices=[(Role.student.value, 'Student'), (Role.lecturer.value, 'Lecturer')], 
                       validators=[DataRequired()])
    student_number = StringField('Student Number', validators=[Optional(), student_number_length_check])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class ProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', render_kw={'readonly': True})
    student_number = StringField('Student Number', render_kw={'readonly': True})
    password = PasswordField('New Password', validators=[Optional(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Update Profile')

class FacialDataForm(FlaskForm):
    face_image = FileField('Upload Face Image', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    submit = SubmitField('Upload Image')

class AttendanceFilterForm(FlaskForm):
    class_id = SelectField('Class Session', coerce=int, validators=[Optional()])
    student_number = SelectField('Student', coerce=str, validators=[Optional()], choices=[])
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    submit = SubmitField('Filter')

class MarksForm(FlaskForm):
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Calculate Marks')

class AdminAddUserForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[(Role.student.value, 'Student'), (Role.lecturer.value, 'Lecturer')], 
                       validators=[DataRequired()])
    student_number = StringField('Student Number (for students only)', validators=[Optional()])
    username = StringField('Username (for lecturers only)', validators=[Optional(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Add User')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already exists.')

    def validate_student_number(self, student_number):
        if self.role.data == Role.student.value:
            if not student_number.data:
                raise ValidationError('Student number is required for students.')
            existing = User.query.filter_by(student_number=student_number.data).first()
            if existing:
                raise ValidationError('Student number already exists.')
        else:
            if student_number.data:
                raise ValidationError('Student number should only be provided for students.')

    def validate_username(self, username):
        if self.role.data == Role.lecturer.value:
            if not username.data:
                raise ValidationError('Username is required for lecturers.')
            existing = User.query.filter_by(username=username.data).first()
            if existing:
                raise ValidationError('Username already exists.')
        else:
            if username.data:
                raise ValidationError('Username should only be provided for lecturers.')

class AdminEditUserForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    student_number = StringField('Student Number (for students only)', validators=[Optional()])
    username = StringField('Username (for lecturers only)', validators=[Optional(), Length(min=3, max=50)])
    submit = SubmitField('Update User')

class AdminResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class AddModuleForm(FlaskForm):
    module_code = StringField('Module Code', validators=[DataRequired(), Length(min=3, max=20)])
    module_name = StringField('Module Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Add Module')

    def validate_module_code(self, module_code):
        module = Module.query.filter_by(module_code=module_code.data).first()
        if module:
            raise ValidationError('Module code already exists.')

class EditModuleForm(FlaskForm):
    module_code = StringField('Module Code', validators=[DataRequired(), Length(min=3, max=20)])
    module_name = StringField('Module Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Update Module')

class AddClassForm(FlaskForm):
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    lecturer_id = SelectField('Lecturer', coerce=int, validators=[DataRequired()])
    class_type = SelectField('Class Type', choices=[(ct.value, ct.value.capitalize()) for ct in ClassType], validators=[DataRequired()])
    class_date = DateField('Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Add Class')

class EditClassForm(FlaskForm):
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    lecturer_id = SelectField('Lecturer', coerce=int, validators=[DataRequired()])
    class_type = SelectField('Class Type', choices=[(ct.value, ct.value.capitalize()) for ct in ClassType], validators=[DataRequired()])
    class_date = DateField('Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Update Class')

class EnrollStudentsForm(FlaskForm):
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    student_ids = SelectMultipleField('Students', coerce=int, validators=[Optional()])  # Changed from SelectField
    submit = SubmitField('Enroll Students')

class AdminAttendanceFilterForm(FlaskForm):
    class_id = SelectField('Class', coerce=int, validators=[Optional()])
    student_number = SelectField('Student', coerce=str, validators=[Optional()], choices=[])
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    submit = SubmitField('Filter')

class ReportForm(FlaskForm):
    type = SelectField('Report Type', choices=[
        ('class', 'By Class'), 
        ('student', 'By Student'), 
        ('date', 'By Date Range')
    ], validators=[DataRequired()])
    
    class_id = SelectField('Class', coerce=int, validators=[Optional()])
    student_id = SelectField('Student', coerce=int, validators=[Optional()])
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    submit = SubmitField('Generate Report')

    def validate(self, extra_validators=None):
        # Initial validation
        if not super().validate(extra_validators):
            return False

        # Custom validation based on report type
        if self.type.data == 'class':
            if not self.class_id.data:
                self.class_id.errors.append('Class selection is required for class-based reports.')
                return False
                
        elif self.type.data == 'student':
            if not self.student_id.data:
                self.student_id.errors.append('Student selection is required for student-based reports.')
                return False
                
        elif self.type.data == 'date':
            if not self.date_from.data or not self.date_to.data:
                self.date_from.errors.append('Both start and end dates are required for date range reports.')
                return False
                
            if self.date_from.data > self.date_to.data:
                self.date_to.errors.append('End date must be after start date.')
                return False

        return True
    
class AssignLecturerForm(FlaskForm):
    lecturer_id = SelectField('Lecturer', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Assign Lecturer')

class AssignModulesForm(FlaskForm):
    modules = SelectMultipleField('Modules', coerce=int, validators=[Optional()])  # Changed from SelectField
    submit = SubmitField('Assign Modules')

class EnrollModulesForm(FlaskForm):
    modules = SelectMultipleField('Modules', coerce=int, validators=[DataRequired()])  # Changed from SelectField
    submit = SubmitField('Enroll Student')