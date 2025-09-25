from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import enum
from flask_login import UserMixin

db = SQLAlchemy()

class Role(enum.Enum):
    admin = 'admin'
    lecturer = 'lecturer'
    student = 'student'

class ClassType(enum.Enum):
    lecture = 'lecture'
    tutorial = 'tutorial'
    practical = 'practical'

class AttendanceStatus(enum.Enum):
    present = 'present'
    absent = 'absent'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=True)  # Nullable for students
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for students
    full_name = db.Column(db.String(100), nullable=False)
    student_number = db.Column(db.String(20), unique=True, nullable=True)  # For students
    role = db.Column(db.Enum(Role), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp(), nullable=False)

    # Relationships
    enrollments = db.relationship('Enrollment', back_populates='student')
    assignments = db.relationship('Assignment', back_populates='lecturer')
    classes = db.relationship('ClassSession', back_populates='lecturer')  
    attendance_records = db.relationship('Attendance', back_populates='student')
    facial_data = db.relationship('FacialData', back_populates='student')

    # Override get_id() method to return user_id instead of id
    def get_id(self):
        return str(self.user_id)

    def __repr__(self):
        return f'<User {self.full_name} - {self.role}>'

class Module(db.Model):
    __tablename__ = 'modules'
    module_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_code = db.Column(db.String(20), unique=True, nullable=False)
    module_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp(), nullable=False)

    # Relationships
    enrollments = db.relationship('Enrollment', back_populates='module')
    assignments = db.relationship('Assignment', back_populates='module')
    classes = db.relationship('ClassSession', back_populates='module')

    def __repr__(self):
        return f'<Module {self.module_code} - {self.module_name}>'

class ClassSession(db.Model):  
    __tablename__ = 'classes'
    class_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.module_id'), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    class_type = db.Column(db.Enum(ClassType), nullable=False)
    class_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp(), nullable=False)

    # Relationships
    module = db.relationship('Module', back_populates='classes')
    lecturer = db.relationship('User', back_populates='classes')
    attendance_records = db.relationship('Attendance', back_populates='class_session')

    def __repr__(self):
        return f'<ClassSession {self.class_id} - {self.class_type} for Module {self.module_id}>'

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    enrollment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.module_id'), nullable=False)
    enrollment_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('User', back_populates='enrollments')
    module = db.relationship('Module', back_populates='enrollments')

    def __repr__(self):
        return f'<Enrollment Student {self.student_id} in Module {self.module_id}>'

class Assignment(db.Model):
    __tablename__ = 'assignments'
    assignment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.module_id'), nullable=False)
    assigned_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)

    # Relationships
    lecturer = db.relationship('User', back_populates='assignments')
    module = db.relationship('Module', back_populates='assignments')

    def __repr__(self):
        return f'<Assignment Lecturer {self.lecturer_id} to Module {self.module_id}>'

class Attendance(db.Model):
    __tablename__ = 'attendance'
    attendance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.class_id'), nullable=False)
    attendance_status = db.Column(db.Enum(AttendanceStatus), default=AttendanceStatus.absent, nullable=False)
    timestamp = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    student = db.relationship('User', back_populates='attendance_records')
    class_session = db.relationship('ClassSession', back_populates='attendance_records')

    def __repr__(self):
        return f'<Attendance {self.attendance_id} - Student {self.student_id} in Class {self.class_id}>'

class FacialData(db.Model):
    __tablename__ = 'facial_data'
    facial_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)

    # Relationships
    student = db.relationship('User', back_populates='facial_data')

    def __repr__(self):
        return f'<FacialData for Student {self.student_id}>'