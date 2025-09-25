from flask import jsonify, render_template, redirect, url_for, flash, request, send_file, make_response
import pandas as pd
from app import app, db
from app.models import ClassType, User, Role, FacialData, ClassSession, Module, Attendance, AttendanceStatus, Assignment, Enrollment
from app.forms import LoginForm, SignupForm, ProfileForm, AttendanceFilterForm, MarksForm, AdminAddUserForm, AdminEditUserForm, AdminResetPasswordForm, BulkImportForm, AddModuleForm, EditModuleForm, AddClassForm, EditClassForm, EnrollStudentsForm, AdminAttendanceFilterForm, ReportForm, AssignLecturerForm, AssignModulesForm, EnrollModulesForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from app.facial_recognition import recognize_face_from_image, verify_face
from datetime import datetime, timezone, date
from config import Config
import base64
from sqlalchemy import case, func, extract
import calendar
from collections import defaultdict
import io
import csv
import json
from sqlalchemy.exc import IntegrityError

# Get the absolute path to the facial_data folder
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, Config.UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = Config.ALLOWED_EXTENSIONS

# Make sure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_face', methods=['POST'])
@login_required
def upload_face_route():
    if current_user.role != Role.student:
        flash('Only students can upload facial data.', 'danger')
        return redirect(url_for('profile'))
    
    if not current_user.student_number:
        flash('Student number is required for facial data upload.', 'danger')
        return redirect(url_for('profile'))
    
    if 'face_image' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('profile'))
    
    file = request.files['face_image']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename):
        filename = f"student_{current_user.student_number}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        file.save(filepath)
        
        # Verify the image contains a face
        is_valid, message = verify_face(filepath, current_user.student_number, UPLOAD_FOLDER)
        
        if is_valid:
            existing_data = FacialData.query.filter_by(student_id=current_user.user_id).first()
            
            if existing_data:
                if existing_data.image_path != filename:
                    old_filepath = os.path.join(UPLOAD_FOLDER, existing_data.image_path)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)

                existing_data.image_path = filename
                existing_data.uploaded_at = datetime.now(timezone.utc).astimezone()
                db.session.commit()
                flash('Facial data updated successfully!', 'success')
            else:
                facial_data = FacialData(
                    student_id=current_user.user_id,
                    image_path=filename,
                    uploaded_at=datetime.now(timezone.utc).astimezone()
                )
                db.session.add(facial_data)
                db.session.commit()
                flash('Facial data saved successfully!', 'success')
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash(f'Invalid image: {message}', 'danger')
    else:
        flash('Invalid file type. Please upload PNG, JPG, or JPEG.', 'danger')
    
    return redirect(url_for('profile'))

@app.route('/view_face/<int:student_id>')
@login_required
def view_face(student_id):
    if current_user.role != Role.admin and current_user.user_id != student_id:
        flash('You do not have permission to view this image.', 'danger')
        return redirect(url_for('profile'))
    
    facial_data = FacialData.query.filter_by(student_id=student_id).first()
    if not facial_data:
        flash('No facial data found.', 'danger')
        return redirect(url_for('profile'))
    
    filepath = os.path.join(UPLOAD_FOLDER, facial_data.image_path)
    if not os.path.exists(filepath):
        flash('Image file not found.', 'danger')
        return redirect(url_for('profile'))
    
    return send_file(filepath, mimetype='image/jpeg')

@app.route('/get_face_image/<int:student_id>')
@login_required
def get_face_image(student_id):
    if current_user.role != Role.admin and current_user.user_id != student_id:
        return jsonify({'error': 'Permission denied'}), 403
    
    facial_data = FacialData.query.filter_by(student_id=student_id).first()
    if not facial_data:
        return jsonify({'error': 'No facial data found'}), 404
    
    filepath = os.path.join(UPLOAD_FOLDER, facial_data.image_path)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Image file not found'}), 404

    try:
        with open(filepath, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return jsonify({'image': f"data:image/jpeg;base64,{encoded_string}"})
    except Exception as e:
        return jsonify({'error': f'Error reading image: {str(e)}'}), 500

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            
            # Redirect based on role
            if user.role == Role.admin:
                return redirect(next_page) if next_page else redirect(url_for('admin_dashboard'))
            elif user.role == Role.lecturer:
                return redirect(next_page) if next_page else redirect(url_for('lecturer_dashboard'))
            else:  # student
                return redirect(next_page) if next_page else redirect(url_for('student_dashboard'))
        else:
            flash('Login failed. Check your email and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Check if email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please login instead.', 'danger')
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(form.password.data)
        
        user = User(
            full_name=form.full_name.data,  
            email=form.email.data,          
            password_hash=hashed_password,
            role=Role(form.role.data)       
        )
        
        # Add student number if role is student
        if form.role.data == Role.student.value:
            # Check if student number already exists
            existing_student = User.query.filter_by(student_number=form.student_number.data).first()
            if existing_student:
                flash('Student number already registered.', 'danger')
                return render_template('signup.html', form=form)
            user.student_number = form.student_number.data  
        
        db.session.add(user)
        db.session.commit()
        
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# UPDATED ADMIN DASHBOARD ROUTE WITH STATISTICS
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    # Calculate stats for the dashboard
    total_students = User.query.filter_by(role=Role.student).count()
    total_lecturers = User.query.filter_by(role=Role.lecturer).count()
    total_classes = ClassSession.query.count()
    total_modules = Module.query.count()
    
    return render_template('admin_dashboard.html', 
                         total_students=total_students,
                         total_lecturers=total_lecturers,
                         total_classes=total_classes,
                         total_modules=total_modules)

@app.route('/lecturer/dashboard')
@login_required
def lecturer_dashboard():
    if current_user.role != Role.lecturer:
        flash('Access denied. Lecturer privileges required.', 'danger')
        return redirect(url_for('home'))
    
    # Calculate stats
    total_classes = ClassSession.query.filter_by(lecturer_id=current_user.user_id).count()
    
    # Total unique students
    module_ids = [a.module_id for a in Assignment.query.filter_by(lecturer_id=current_user.user_id).all()]
    total_students = db.session.query(func.count(func.distinct(User.user_id))).join(Enrollment).filter(
        Enrollment.module_id.in_(module_ids), User.role == Role.student
    ).scalar()
    
    # Average attendance
    class_ids = [c.class_id for c in ClassSession.query.filter_by(lecturer_id=current_user.user_id).all()]
    total_possible = db.session.query(func.count(Attendance.attendance_id)).filter(
        Attendance.class_id.in_(class_ids)
    ).scalar()
    total_present = db.session.query(func.count(Attendance.attendance_id)).filter(
        Attendance.class_id.in_(class_ids), Attendance.attendance_status == AttendanceStatus.present
    ).scalar()
    avg_attendance = round((total_present / total_possible * 100) if total_possible > 0 else 0, 2)
    
    return render_template('lecturer_dashboard.html', total_classes=total_classes, total_students=total_students, avg_attendance=avg_attendance)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != Role.student:
        flash('Access denied. Student privileges required.', 'danger')
        return redirect(url_for('home'))
    
    # Get enrolled modules for the student
    enrolled_modules = Enrollment.query.filter_by(student_id=current_user.user_id).all()
    modules_data = []
    
    for enrollment in enrolled_modules:
        module = enrollment.module
        # Get attendance stats for this module - ONLY classes for this module
        classes = ClassSession.query.filter_by(module_id=module.module_id).all()
        class_ids = [c.class_id for c in classes]
        
        total_sessions = len(class_ids)
        present_count = Attendance.query.filter(
            Attendance.student_id == current_user.user_id,
            Attendance.class_id.in_(class_ids),
            Attendance.attendance_status == AttendanceStatus.present
        ).count()
        
        attendance_percent = round((present_count / total_sessions * 100) if total_sessions > 0 else 0, 2)
        
        modules_data.append({
            'module_code': module.module_code,
            'module_name': module.module_name,
            'total_sessions': total_sessions,
            'present_count': present_count,
            'attendance_percent': attendance_percent
        })
    
    # Get overall attendance stats - ONLY for enrolled modules
    enrolled_module_ids = [em.module_id for em in enrolled_modules]
    enrolled_classes = ClassSession.query.filter(ClassSession.module_id.in_(enrolled_module_ids)).all() if enrolled_module_ids else []
    enrolled_class_ids = [c.class_id for c in enrolled_classes]
    
    all_classes_attended = Attendance.query.filter(
        Attendance.student_id == current_user.user_id, 
        Attendance.attendance_status == AttendanceStatus.present,
        Attendance.class_id.in_(enrolled_class_ids) if enrolled_class_ids else False
    ).count()
    
    all_classes_total = len(enrolled_class_ids)
    overall_attendance = round((all_classes_attended / all_classes_total * 100) if all_classes_total > 0 else 0, 2)
    
    return render_template('student_dashboard.html', 
                          modules_data=modules_data,
                          overall_attendance=overall_attendance,
                          total_classes_attended=all_classes_attended,
                          total_classes=all_classes_total)

@app.route('/student/attendance')
@login_required
def student_attendance():
    if current_user.role != Role.student:
        flash('Access denied. Student privileges required.', 'danger')
        return redirect(url_for('home'))
    
    # Get enrolled module IDs for this student
    enrolled_module_ids = [em.module_id for em in Enrollment.query.filter_by(student_id=current_user.user_id).all()]
    
    # Get all attendance records for the student - ONLY for enrolled modules
    if enrolled_module_ids:
        # Get class IDs for enrolled modules
        enrolled_class_ids = [c.class_id for c in ClassSession.query.filter(ClassSession.module_id.in_(enrolled_module_ids)).all()]
        
        if enrolled_class_ids:
            attendance_records = Attendance.query.filter(
                Attendance.student_id == current_user.user_id,
                Attendance.class_id.in_(enrolled_class_ids)
            ).order_by(Attendance.timestamp.desc()).all()
        else:
            attendance_records = []
    else:
        attendance_records = []
    
    # Group by module for summary
    module_attendance = {}
    for record in attendance_records:
        module_code = record.class_session.module.module_code
        if module_code not in module_attendance:
            module_attendance[module_code] = {
                'module_name': record.class_session.module.module_name,
                'total': 0,
                'present': 0
            }
        
        module_attendance[module_code]['total'] += 1
        if record.attendance_status == AttendanceStatus.present:
            module_attendance[module_code]['present'] += 1
    
    # Calculate percentages
    for module_code, data in module_attendance.items():
        data['percentage'] = round((data['present'] / data['total'] * 100) if data['total'] > 0 else 0, 2)
    
    return render_template('student_attendance.html', 
                          attendance_records=attendance_records,
                          module_attendance=module_attendance)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Update user information
        current_user.full_name = form.full_name.data
        
        # Only update password if provided
        if form.password.data:
            current_user.password_hash = generate_password_hash(form.password.data)
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    elif request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email
        if current_user.role == Role.student:
            form.student_number.data = current_user.student_number
    
    return render_template('profile.html', form=form)

@app.route('/lecturer/view_attendance', methods=['GET', 'POST'])
@login_required
def lecturer_view_attendance():
    if current_user.role != Role.lecturer:
        flash('Access denied. Lecturer privileges required.', 'danger')
        return redirect(url_for('home'))
    
    form = AttendanceFilterForm()
    lecturer_classes = ClassSession.query.filter_by(lecturer_id=current_user.user_id).order_by(ClassSession.class_date.desc()).all()
    form.class_id.choices = [(0, 'All Classes')] + [(c.class_id, f"{c.module.module_code} - {c.class_type.value} on {c.class_date}") for c in lecturer_classes]
    
    # Base query with single join to ClassSession
    query = Attendance.query.join(ClassSession, ClassSession.class_id == Attendance.class_id).filter(ClassSession.lecturer_id == current_user.user_id)
    
    if form.validate_on_submit():
        # Apply filters without redundant joins
        if form.class_id.data != 0:
            query = query.filter(Attendance.class_id == form.class_id.data)
        if form.student_number.data:
            student = User.query.filter_by(student_number=form.student_number.data, role=Role.student).first()
            if student:
                query = query.filter(Attendance.student_id == student.user_id)
            else:
                flash('Student not found.', 'warning')
        if form.date_from.data:
            query = query.filter(ClassSession.class_date >= form.date_from.data)
        if form.date_to.data:
            query = query.filter(ClassSession.class_date <= form.date_to.data)
        
        attendances = query.order_by(Attendance.timestamp.desc()).all()
    else:
        attendances = query.order_by(Attendance.timestamp.desc()).all()
    
    return render_template('view_attendance.html', form=form, attendances=attendances)

@app.route('/lecturer/allocate_marks', methods=['GET', 'POST'])
@login_required
def lecturer_allocate_marks():
    if current_user.role != Role.lecturer:
        flash('Access denied. Lecturer privileges required.', 'danger')
        return redirect(url_for('home'))
    
    form = MarksForm()
    assignments = Assignment.query.filter_by(lecturer_id=current_user.user_id).all()
    form.module_id.choices = [(a.module.module_id, f"{a.module.module_code} - {a.module.module_name}") for a in assignments]
    
    students_data = []
    module = None
    total_sessions = 0
    
    if form.validate_on_submit():
        module_id = form.module_id.data
        module = Module.query.get(module_id)
        
        # Get classes for this module taught by lecturer
        classes = ClassSession.query.filter_by(module_id=module_id, lecturer_id=current_user.user_id).all()
        total_sessions = len(classes)
        class_ids = [c.class_id for c in classes]
        
        # Get enrolled students
        enrollments = Enrollment.query.filter_by(module_id=module_id).all()
        
        for enrollment in enrollments:
            student = enrollment.student
            present_count = Attendance.query.filter(
                Attendance.student_id == student.user_id,
                Attendance.class_id.in_(class_ids),
                Attendance.attendance_status == AttendanceStatus.present
            ).count()
            percent = round((present_count / total_sessions * 100) if total_sessions > 0 else 0, 2)
            students_data.append({
                'student_number': student.student_number,
                'name': student.full_name,
                'present': present_count,
                'percent': percent,
                'warning': percent < 75
            })
    
    return render_template('allocate_marks.html', form=form, module=module, total_sessions=total_sessions, students_data=students_data)

@app.route('/lecturer/calendar')
@login_required
def lecturer_calendar():
    if current_user.role != Role.lecturer:
        flash('Access denied. Lecturer privileges required.', 'danger')
        return redirect(url_for('home'))
    
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    
    # Handle month navigation
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    
    cal = calendar.monthcalendar(year, month)
    
    # Get classes in this month
    classes = ClassSession.query.filter_by(lecturer_id=current_user.user_id).filter(
        extract('year', ClassSession.class_date) == year,
        extract('month', ClassSession.class_date) == month
    ).all()
    
    classes_by_day = defaultdict(list)
    for c in classes:
        classes_by_day[c.class_date.day].append(c)
    
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    month_name = calendar.month_name[month]
    
    return render_template('calendar.html', 
                         cal=cal, 
                         classes_by_day=classes_by_day,
                         year=year, 
                         month=month,
                         month_name=month_name,
                         today=today,
                         prev_year=prev_year,
                         prev_month=prev_month,
                         next_year=next_year,
                         next_month=next_month)

def is_session_ended(class_session):
    """Check if a class session has ended (with proper timezone handling)"""
    current_time = datetime.now(timezone.utc).astimezone()
    
    # Create datetime objects for comparison
    class_date = class_session.class_date
    class_end_time = class_session.end_time
    
    # Combine date and time, assume they are in the same timezone as current time
    class_end_datetime = datetime.combine(class_date, class_end_time)
    class_end_datetime = class_end_datetime.replace(tzinfo=current_time.tzinfo)
    
    return current_time > class_end_datetime

def is_session_active(class_session):
    """Check if a class session is currently active"""
    current_time = datetime.now(timezone.utc).astimezone()
    
    # Create datetime objects for comparison
    class_date = class_session.class_date
    class_start_time = class_session.start_time
    class_end_time = class_session.end_time
    
    # Combine date and time
    class_start_datetime = datetime.combine(class_date, class_start_time)
    class_start_datetime = class_start_datetime.replace(tzinfo=current_time.tzinfo)
    
    class_end_datetime = datetime.combine(class_date, class_end_time)
    class_end_datetime = class_end_datetime.replace(tzinfo=current_time.tzinfo)
    
    return class_start_datetime <= current_time <= class_end_datetime

@app.route('/lecturer/attendance_scanner')
@login_required
def lecturer_attendance_scanner():
    if current_user.role != Role.lecturer:
        flash('Access denied. Lecturer privileges required.', 'danger')
        return redirect(url_for('home'))
    
    # Get today's classes for this lecturer
    today = date.today()
    
    # Only show classes that haven't ended yet
    todays_classes = ClassSession.query.filter_by(
        lecturer_id=current_user.user_id,
        class_date=today
    ).order_by(ClassSession.start_time).all()
    
    # Filter out classes that have ended
    active_classes = []
    for class_session in todays_classes:
        if not is_session_ended(class_session):
            # Get enrollment count
            enrollment_count = Enrollment.query.filter_by(module_id=class_session.module_id).count()
            
            # Get facial data count for enrolled students
            enrollments = Enrollment.query.filter_by(module_id=class_session.module_id).all()
            student_ids = [enrollment.student_id for enrollment in enrollments]
            facial_data_count = FacialData.query.filter(FacialData.student_id.in_(student_ids)).count() if student_ids else 0
            
            # Get attendance count for this SPECIFIC class session
            attendance_count = Attendance.query.filter_by(class_id=class_session.class_id).count()
            
            # Check if session is currently active
            session_active = is_session_active(class_session)
            
            active_classes.append({
                'class_session': class_session,
                'enrollment_count': enrollment_count,
                'facial_data_count': facial_data_count,
                'attendance_count': attendance_count,
                'session_active': session_active
            })
    
    return render_template('attendance_scanner.html', classes_data=active_classes)

@app.route('/lecturer/browser_face_scan/<int:class_id>')
@login_required
def browser_face_scan(class_id):
    """Browser face scanner with session time validation"""
    if current_user.role != Role.lecturer:
        flash('Access denied', 'danger')
        return redirect(url_for('lecturer_attendance_scanner'))
    
    class_session = ClassSession.query.get(class_id)
    if not class_session or class_session.lecturer_id != current_user.user_id:
        flash('Class not found', 'danger')
        return redirect(url_for('lecturer_attendance_scanner'))
    
    # Check if class session has ended
    is_session_ended_flag = is_session_ended(class_session)
    
    # Check if session is currently active
    is_session_active_flag = is_session_active(class_session)
    
    # Get current time for display
    now = datetime.now(timezone.utc).astimezone()
    
    # Get class info for display
    class_info = f"{class_session.module.module_code} - {class_session.class_type.value.title()} on {class_session.class_date} at {class_session.start_time.strftime('%H:%M')}"
    
    return render_template('browser_face_scanner.html', 
                         class_session=class_session,
                         class_info=class_info,
                         is_session_ended=is_session_ended_flag,
                         is_session_active=is_session_active_flag,
                         now=now)  # Add this line

@app.route('/lecturer/get_student_faces')
@login_required
def get_student_faces():
    if current_user.role != Role.lecturer:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify({'success': False, 'message': 'Class ID required'})
    
    class_session = ClassSession.query.get(class_id)
    if not class_session or class_session.lecturer_id != current_user.user_id:
        return jsonify({'success': False, 'message': 'Class not found'})
    
    # Get enrolled students with facial data
    enrollments = Enrollment.query.filter_by(module_id=class_session.module_id).all()
    students_data = []
    
    for enrollment in enrollments:
        student = enrollment.student
        facial_data = FacialData.query.filter_by(student_id=student.user_id).first()
        
        student_info = {
            'user_id': student.user_id,
            'name': student.full_name,
            'student_number': student.student_number,
            'has_face_data': facial_data is not None
        }
        
        # Load face image data if available
        if facial_data:
            filepath = os.path.join(UPLOAD_FOLDER, facial_data.image_path)
            if os.path.exists(filepath):
                try:
                    # Read and encode the image
                    with open(filepath, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                        student_info['faceData'] = f"data:image/jpeg;base64,{encoded_string}"
                except Exception as e:
                    print(f"Error loading face image: {e}")
                    
                # Try to read image data directly if previous open failed
                try:
                    with open(filepath, "rb") as image_file:
                        image_data = image_file.read()
                    if len(image_data) > 0:
                        encoded_string = base64.b64encode(image_data).decode('utf-8')
                        student_info['faceData'] = f"data:image/jpeg;base64,{encoded_string}"
                    else:
                        print(f"Empty image file for student {student.student_number}")
                        student_info['has_face_data'] = False
                except Exception as e2:
                    print(f"Error loading face image for {student.student_number}: {e2}")
                    student_info['has_face_data'] = False
        
        students_data.append(student_info)
    
    return jsonify({'success': True, 'students': students_data})

@app.route('/lecturer/mark_attendance_manual', methods=['POST'])
@login_required
def mark_attendance_manual():
    if current_user.role != Role.lecturer:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    data = request.get_json()
    student_id = data.get('student_id')
    class_id = data.get('class_id')
    status = data.get('status', 'present')
    
    # Check if attendance already exists
    existing_attendance = Attendance.query.filter_by(
        student_id=student_id,
        class_id=class_id
    ).first()
    
    if existing_attendance:
        existing_attendance.attendance_status = AttendanceStatus.present if status == 'present' else AttendanceStatus.absent
        existing_attendance.timestamp = datetime.now(timezone.utc).astimezone()
    else:
        attendance = Attendance(
            student_id=student_id,
            class_id=class_id,
            attendance_status=AttendanceStatus.present if status == 'present' else AttendanceStatus.absent,
            timestamp=datetime.now(timezone.utc).astimezone()
        )
        db.session.add(attendance)
    
    db.session.commit()
    
    student = User.query.get(student_id)
    return jsonify({
        'success': True,
        'message': f'Attendance marked for {student.full_name}',
        'student_name': student.full_name,
        'student_number': student.student_number
    })

@app.route('/lecturer/recognize_face', methods=['POST'])
@login_required
def recognize_face():
    """Recognize face from captured image and mark attendance"""
    if current_user.role != Role.lecturer:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        data = request.get_json()
        image_data = data.get('image_data')
        class_id = data.get('class_id')
        
        if not image_data or not class_id:
            return jsonify({'success': False, 'message': 'Missing image data or class ID'})
        
        # Use the facial recognition function
        result = recognize_face_from_image(image_data, class_id)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in recognize_face: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/lecturer/get_enrolled_students')
@login_required
def get_enrolled_students():
    """Get enrolled students for a specific class session"""
    if current_user.role != Role.lecturer:
        return jsonify([])
    
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify([])
    
    try:
        class_session = ClassSession.query.get(class_id)
        if not class_session or class_session.lecturer_id != current_user.user_id:
            return jsonify([])
        
        # Get enrollments for this module
        enrollments = Enrollment.query.filter_by(module_id=class_session.module_id).all()
        
        students = []
        for enrollment in enrollments:
            student = enrollment.student
            students.append({
                'user_id': student.user_id,
                'student_number': student.student_number,
                'full_name': student.full_name,
                'email': student.email
            })
        
        return jsonify(students)
        
    except Exception as e:
        print(f"Error getting enrolled students: {str(e)}")
        return jsonify([])
    
@app.route('/lecturer/get_existing_attendance')
@login_required
def get_existing_attendance():
    """Get existing attendance records for a specific class session"""
    if current_user.role != Role.lecturer:
        return jsonify([])
    
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify([])
    
    try:
        class_session = ClassSession.query.get(class_id)
        if not class_session or class_session.lecturer_id != current_user.user_id:
            return jsonify([])
        
        # Get existing attendance records
        existing_attendance = Attendance.query.filter_by(class_id=class_id).all()
        
        attendance_data = []
        for att in existing_attendance:
            attendance_data.append({
                'student_id': att.student_id,
                'student_name': att.student.full_name,
                'student_number': att.student.student_number,
                'timestamp': att.timestamp.isoformat() if att.timestamp else None
            })
        
        return jsonify(attendance_data)
        
    except Exception as e:
        print(f"Error getting existing attendance: {str(e)}")
        return jsonify([])

# Admin User Management
@app.route('/admin/users', methods=['GET'])
@login_required
def admin_list_users():
    print("DEBUG: admin_list_users route accessed")  # Debug line
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    try:
        students = User.query.filter_by(role=Role.student).all()
        lecturers = User.query.filter_by(role=Role.lecturer).all()
        print(f"DEBUG: Found {len(students)} students and {len(lecturers)} lecturers")  # Debug line
        return render_template('admin_users.html', students=students, lecturers=lecturers)
    except Exception as e:
        print(f"ERROR in admin_list_users: {str(e)}")  # Debug line
        flash('Error loading users.', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    form = AdminAddUserForm()
    
    # Set role choices
    form.role.choices = [(Role.student.value, 'Student'), (Role.lecturer.value, 'Lecturer')]
    
    if form.validate_on_submit():
        try:
            # Check if email already exists
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already exists.', 'danger')
                return render_template('admin_add_user.html', form=form)
            
            hashed_password = generate_password_hash(form.password.data)
            user = User(
                full_name=form.full_name.data,
                email=form.email.data,
                password_hash=hashed_password,
                role=Role(form.role.data)
            )
            
            if form.role.data == Role.student.value:
                # Check if student number already exists
                if not form.student_number.data:
                    flash('Student number is required for students.', 'danger')
                    return render_template('admin_add_user.html', form=form)
                
                existing_student = User.query.filter_by(student_number=form.student_number.data).first()
                if existing_student:
                    flash('Student number already exists.', 'danger')
                    return render_template('admin_add_user.html', form=form)
                user.student_number = form.student_number.data
            else:
                # Check if username already exists
                if not form.username.data:
                    flash('Username is required for lecturers.', 'danger')
                    return render_template('admin_add_user.html', form=form)
                
                existing_lecturer = User.query.filter_by(username=form.username.data).first()
                if existing_lecturer:
                    flash('Username already exists.', 'danger')
                    return render_template('admin_add_user.html', form=form)
                user.username = form.username.data
            
            db.session.add(user)
            db.session.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('admin_list_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding user: {str(e)}', 'danger')
            return render_template('admin_add_user.html', form=form)
    
    return render_template('admin_add_user.html', form=form)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    user = User.query.get_or_404(user_id)
    if user.role == Role.admin:
        flash('Cannot edit admin accounts.', 'danger')
        return redirect(url_for('admin_list_users'))
    form = AdminEditUserForm()
    if form.validate_on_submit():
        user.full_name = form.full_name.data
        user.email = form.email.data
        if user.role == Role.student:
            user.student_number = form.student_number.data
        else:
            user.username = form.username.data
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_list_users'))
    elif request.method == 'GET':
        form.full_name.data = user.full_name
        form.email.data = user.email
        if user.role == Role.student:
            form.student_number.data = user.student_number
        else:
            form.username.data = user.username
    return render_template('admin_edit_user.html', form=form, user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    
    if user.role == Role.admin:
        flash('Cannot delete admin accounts.', 'danger')
        return redirect(url_for('admin_list_users'))
    
    try:
        # Delete related records first
        if user.role == Role.student:
            # Delete student's facial data
            FacialData.query.filter_by(student_id=user_id).delete()
            # Delete student's attendance records
            Attendance.query.filter_by(student_id=user_id).delete()
            # Delete student's enrollments
            Enrollment.query.filter_by(student_id=user_id).delete()
        else:  # Lecturer
            # Reassign classes to another lecturer or delete them
            classes = ClassSession.query.filter_by(lecturer_id=user_id).all()
            if classes:
                # Option 1: Reassign to admin or another lecturer
                admin_user = User.query.filter_by(role=Role.admin).first()
                if admin_user:
                    for class_session in classes:
                        class_session.lecturer_id = admin_user.user_id
                else:
                    # Option 2: Delete the classes and their attendance records
                    for class_session in classes:
                        Attendance.query.filter_by(class_id=class_session.class_id).delete()
                        db.session.delete(class_session)
            
            # Delete lecturer's assignments
            Assignment.query.filter_by(lecturer_id=user_id).delete()
        
        # Now delete the user
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}. This user may have related records that need to be handled first.', 'danger')
        print(f"Delete user error: {str(e)}")  # Debug
    
    return redirect(url_for('admin_list_users'))

@app.route('/admin/reset_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_reset_password(user_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    user = User.query.get_or_404(user_id)
    if user.role == Role.admin:
        flash('Cannot reset admin passwords.', 'danger')
        return redirect(url_for('admin_list_users'))
    form = AdminResetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash('Password reset successfully!', 'success')
        return redirect(url_for('admin_list_users'))
    return render_template('admin_reset_password.html', form=form, user=user)

@app.route('/admin/bulk_import', methods=['GET', 'POST'])
@login_required
def admin_bulk_import():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    form = BulkImportForm()
    if form.validate_on_submit():
        file = form.file.data
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            try:
                role = Role(row['role'].lower())
                hashed_password = generate_password_hash(row['password'])
                user = User(
                    full_name=row['full_name'],
                    email=row['email'],
                    password_hash=hashed_password,
                    role=role
                )
                if role == Role.student:
                    user.student_number = row.get('student_number')
                else:
                    user.username = row.get('username')
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(f'Error importing {row["email"]}: Duplicate or invalid data.', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error importing {row["email"]}: {str(e)}', 'danger')
        flash('Bulk import completed!', 'success')
        return redirect(url_for('admin_list_users'))
    return render_template('admin_bulk_import.html', form=form)

# Admin Class/Course Management
@app.route('/admin/modules', methods=['GET'])
@login_required
def admin_list_modules():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    modules = Module.query.all()
    return render_template('admin_modules.html', modules=modules)

@app.route('/admin/add_module', methods=['GET', 'POST'])
@login_required
def admin_add_module():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    form = AddModuleForm()
    if form.validate_on_submit():
        module = Module(
            module_code=form.module_code.data,
            module_name=form.module_name.data,
            description=form.description.data
        )
        db.session.add(module)
        db.session.commit()
        flash('Module added successfully!', 'success')
        return redirect(url_for('admin_list_modules'))
    return render_template('admin_add_module.html', form=form)

@app.route('/admin/edit_module/<int:module_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_module(module_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    module = Module.query.get_or_404(module_id)
    form = EditModuleForm()
    if form.validate_on_submit():
        module.module_code = form.module_code.data
        module.module_name = form.module_name.data
        module.description = form.description.data
        db.session.commit()
        flash('Module updated successfully!', 'success')
        return redirect(url_for('admin_list_modules'))
    elif request.method == 'GET':
        form.module_code.data = module.module_code
        form.module_name.data = module.module_name
        form.description.data = module.description
    return render_template('admin_edit_module.html', form=form, module=module)

@app.route('/admin/delete_module/<int:module_id>', methods=['POST'])
@login_required
def admin_delete_module(module_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    module = Module.query.get_or_404(module_id)
    db.session.delete(module)
    db.session.commit()
    flash('Module deleted successfully!', 'success')
    return redirect(url_for('admin_list_modules'))

@app.route('/admin/classes', methods=['GET'])
@login_required
def admin_list_classes():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    classes = ClassSession.query.all()
    return render_template('admin_classes.html', classes=classes)

@app.route('/admin/add_class', methods=['GET', 'POST'])
@login_required
def admin_add_class():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    form = AddClassForm()
    form.module_id.choices = [(m.module_id, f"{m.module_code} - {m.module_name}") for m in Module.query.all()]
    form.lecturer_id.choices = [(l.user_id, l.full_name) for l in User.query.filter_by(role=Role.lecturer).all()]
    if form.validate_on_submit():
        class_session = ClassSession(
            module_id=form.module_id.data,
            lecturer_id=form.lecturer_id.data,
            class_type=ClassType(form.class_type.data),
            class_date=form.class_date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            location=form.location.data
        )
        db.session.add(class_session)
        db.session.commit()
        flash('Class added successfully!', 'success')
        return redirect(url_for('admin_list_classes'))
    return render_template('admin_add_class.html', form=form)

@app.route('/admin/edit_class/<int:class_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_class(class_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    class_session = ClassSession.query.get_or_404(class_id)
    form = EditClassForm()
    form.module_id.choices = [(m.module_id, f"{m.module_code} - {m.module_name}") for m in Module.query.all()]
    form.lecturer_id.choices = [(l.user_id, l.full_name) for l in User.query.filter_by(role=Role.lecturer).all()]
    if form.validate_on_submit():
        class_session.module_id = form.module_id.data
        class_session.lecturer_id = form.lecturer_id.data
        class_session.class_type = ClassType(form.class_type.data)
        class_session.class_date = form.class_date.data
        class_session.start_time = form.start_time.data
        class_session.end_time = form.end_time.data
        class_session.location = form.location.data
        db.session.commit()
        flash('Class updated successfully!', 'success')
        return redirect(url_for('admin_list_classes'))
    elif request.method == 'GET':
        form.module_id.data = class_session.module_id
        form.lecturer_id.data = class_session.lecturer_id
        form.class_type.data = class_session.class_type.value
        form.class_date.data = class_session.class_date
        form.start_time.data = class_session.start_time
        form.end_time.data = class_session.end_time
        form.location.data = class_session.location
    return render_template('admin_edit_class.html', form=form, class_session=class_session)

@app.route('/admin/delete_class/<int:class_id>', methods=['POST'])
@login_required
def admin_delete_class(class_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    class_session = ClassSession.query.get_or_404(class_id)
    
    try:
        # Delete attendance records for this class first
        Attendance.query.filter_by(class_id=class_id).delete()
        
        # Now delete the class
        db.session.delete(class_session)
        db.session.commit()
        flash('Class deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}. There may be related records that prevent deletion.', 'danger')
        print(f"Delete class error: {str(e)}")  # Debug
    
    return redirect(url_for('admin_list_classes'))

@app.route('/admin/assign_lecturer/<int:module_id>', methods=['GET', 'POST'])
@login_required
def admin_assign_lecturer(module_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    module = Module.query.get_or_404(module_id)
    form = AssignLecturerForm()
    form.lecturer_id.choices = [(l.user_id, l.full_name) for l in User.query.filter_by(role=Role.lecturer).all()]
    if form.validate_on_submit():
        assignment = Assignment(
            lecturer_id=form.lecturer_id.data,
            module_id=module_id
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Lecturer assigned to module!', 'success')
        return redirect(url_for('admin_list_modules'))
    return render_template('admin_assign_lecturer.html', form=form, module=module)

# FIXED: Enroll Students Route - Corrected form handling
@app.route('/admin/enroll_students', methods=['GET', 'POST'])
@login_required
def admin_enroll_students():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    form = EnrollStudentsForm()
    form.module_id.choices = [(m.module_id, f"{m.module_code} - {m.module_name}") for m in Module.query.all()]
    form.student_ids.choices = [(s.user_id, f"{s.student_number} - {s.full_name}") for s in User.query.filter_by(role=Role.student).all()]
    
    if form.validate_on_submit():
        module_id = form.module_id.data
        selected_students = form.student_ids.data  # FIXED: Use form data instead of request.form
        
        if not selected_students:
            flash('Please select at least one student to enroll.', 'warning')
            return render_template('admin_enroll_students.html', form=form)
        
        enrolled_count = 0
        module = Module.query.get(module_id)
        
        for student_id in selected_students:
            existing = Enrollment.query.filter_by(student_id=student_id, module_id=module_id).first()
            if not existing:
                enrollment = Enrollment(
                    student_id=student_id,
                    module_id=module_id
                )
                db.session.add(enrollment)
                enrolled_count += 1
        
        if enrolled_count > 0:
            db.session.commit()
            flash(f'Successfully enrolled {enrolled_count} student(s) in {module.module_code}!', 'success')
        else:
            flash('No new students were enrolled (they may already be enrolled in this module).', 'info')
        
        return redirect(url_for('admin_list_modules'))
    
    return render_template('admin_enroll_students.html', form=form)

@app.route('/admin/assign_modules_to_lecturer/<int:lecturer_id>', methods=['GET', 'POST'])
@login_required
def admin_assign_modules_to_lecturer(lecturer_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    lecturer = User.query.get_or_404(lecturer_id)
    if lecturer.role != Role.lecturer:
        flash('Invalid lecturer.', 'danger')
        return redirect(url_for('admin_list_users'))
    form = AssignModulesForm()
    form.modules.choices = [(m.module_id, f"{m.module_code} - {m.module_name}") for m in Module.query.all()]
    if form.validate_on_submit():
        selected_modules = form.modules.data  # FIXED: Use form data instead of request.form
        for module_id in selected_modules:
            existing = Assignment.query.filter_by(lecturer_id=lecturer_id, module_id=module_id).first()
            if not existing:
                assignment = Assignment(lecturer_id=lecturer_id, module_id=module_id)
                db.session.add(assignment)
        db.session.commit()
        flash('Modules assigned to lecturer successfully!', 'success')
        return redirect(url_for('admin_list_users'))
    existing_modules = [str(a.module_id) for a in Assignment.query.filter_by(lecturer_id=lecturer_id).all()]
    return render_template('admin_assign_modules_to_lecturer.html', form=form, lecturer=lecturer, existing_modules=existing_modules)

# FIXED: Enroll Student in Modules Route - Corrected form handling
@app.route('/admin/enroll_student_in_modules/<int:student_id>', methods=['GET', 'POST'])
@login_required
def admin_enroll_student_in_modules(student_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    student = User.query.get_or_404(student_id)
    if student.role != Role.student:
        flash('Invalid student.', 'danger')
        return redirect(url_for('admin_list_users'))
    
    form = EnrollModulesForm()
    form.modules.choices = [(m.module_id, f"{m.module_code} - {m.module_name}") for m in Module.query.all()]
    
    if form.validate_on_submit():
        selected_modules = form.modules.data  # FIXED: Use form data instead of request.form
        
        if not selected_modules:
            flash('Please select at least one module to enroll the student in.', 'warning')
            return render_template('admin_enroll_student_in_modules.html', form=form, student=student, existing_modules=[])
        
        enrolled_count = 0
        
        for module_id in selected_modules:
            existing = Enrollment.query.filter_by(student_id=student_id, module_id=module_id).first()
            if not existing:
                enrollment = Enrollment(student_id=student_id, module_id=module_id)
                db.session.add(enrollment)
                enrolled_count += 1
        
        if enrolled_count > 0:
            db.session.commit()
            flash(f'Successfully enrolled {student.full_name} in {enrolled_count} module(s)!', 'success')
        else:
            flash(f'{student.full_name} is already enrolled in all selected modules.', 'info')
        
        return redirect(url_for('admin_list_users'))
    
    existing_modules = [str(e.module_id) for e in Enrollment.query.filter_by(student_id=student_id).all()]
    return render_template('admin_enroll_student_in_modules.html', form=form, student=student, existing_modules=existing_modules)

# FIXED: Student Enrollments Route - Include enrollment_date
@app.route('/admin/student_enrollments/<int:student_id>', methods=['GET'])
@login_required
def admin_student_enrollments(student_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    student = User.query.get_or_404(student_id)
    if student.role != Role.student:
        flash('This user is not a student.', 'danger')
        return redirect(url_for('admin_list_users'))
    
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    # Create a list of tuples with (module, enrollment) to include enrollment_date
    module_enrollments = [(enrollment.module, enrollment) for enrollment in enrollments]
    
    return render_template('admin_student_enrollments.html', student=student, module_enrollments=module_enrollments)

@app.route('/admin/view_attendance', methods=['GET', 'POST'])
@login_required
def admin_view_attendance():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    form = AdminAttendanceFilterForm()
    all_classes = ClassSession.query.order_by(ClassSession.class_date.desc()).all()
    form.class_id.choices = [(0, 'All Classes')] + [(c.class_id, f"{c.module.module_code} - {c.class_type.value} on {c.class_date}") for c in all_classes]
    query = Attendance.query
    if form.validate_on_submit():
        if form.class_id.data != 0:
            query = query.filter(Attendance.class_id == form.class_id.data)
        if form.student_number.data:
            student = User.query.filter_by(student_number=form.student_number.data, role=Role.student).first()
            if student:
                query = query.filter(Attendance.student_id == student.user_id)
            else:
                flash('Student not found.', 'warning')
        if form.date_from.data:
            query = query.join(ClassSession).filter(ClassSession.class_date >= form.date_from.data)
        if form.date_to.data:
            query = query.join(ClassSession).filter(ClassSession.class_date <= form.date_to.data)
    attendances = query.order_by(Attendance.timestamp.desc()).all()
    return render_template('admin_view_attendance.html', form=form, attendances=attendances)

@app.route('/admin/generate_report', methods=['GET', 'POST'])
@login_required
def admin_generate_report():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    form = ReportForm()
    form.class_id.choices = [(c.class_id, f"{c.module.module_code} - {c.class_type.value} on {c.class_date}") for c in ClassSession.query.all()]
    form.student_id.choices = [(s.user_id, f"{s.student_number} - {s.full_name}") for s in User.query.filter_by(role=Role.student).all()]
    report_data = None
    if form.validate_on_submit():
        query = Attendance.query
        if form.type.data == 'class':
            if form.class_id.data:
                query = query.filter(Attendance.class_id == form.class_id.data)
        elif form.type.data == 'student':
            if form.student_id.data:
                query = query.filter(Attendance.student_id == form.student_id.data)
        elif form.type.data == 'date':
            if form.date_from.data:
                query = query.join(ClassSession).filter(ClassSession.class_date >= form.date_from.data)
            if form.date_to.data:
                query = query.join(ClassSession).filter(ClassSession.class_date <= form.date_to.data)
        report_data = query.all()
        # For CSV export
        if request.args.get('export') == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Attendance ID', 'Student Name', 'Class Date', 'Status'])
            for att in report_data:
                writer.writerow([att.attendance_id, att.student.full_name, att.class_session.class_date, att.attendance_status.value])
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=report.csv"
            response.headers["Content-type"] = "text/csv"
            return response
    return render_template('admin_report.html', form=form, report_data=report_data)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    # Simple stats
    total_students = User.query.filter_by(role=Role.student).count()
    total_lecturers = User.query.filter_by(role=Role.lecturer).count()
    total_classes = ClassSession.query.count()
    total_attendances = Attendance.query.count()
    present_count = Attendance.query.filter_by(attendance_status=AttendanceStatus.present).count()
    avg_attendance = round((present_count / total_attendances * 100) if total_attendances > 0 else 0, 2)
    # Trends: e.g., attendance by month (using SQLAlchemy)
    trends = db.session.query(
        extract('year', ClassSession.class_date).label('year'),
        extract('month', ClassSession.class_date).label('month'),
        func.avg(case((Attendance.attendance_status == AttendanceStatus.present, 1), else_=0)).label('avg_att')
    ).join(Attendance.class_session).group_by('year', 'month').all()
    return render_template('admin_analytics.html', total_students=total_students, total_lecturers=total_lecturers,
                           total_classes=total_classes, avg_attendance=avg_attendance, trends=trends)

@app.route('/admin/lecturer_assignments/<int:lecturer_id>', methods=['GET'])
@login_required
def admin_lecturer_assignments(lecturer_id):
    if current_user.role != Role.admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('home'))
    
    lecturer = User.query.get_or_404(lecturer_id)
    if lecturer.role != Role.lecturer:
        flash('This user is not a lecturer.', 'danger')
        return redirect(url_for('admin_list_users'))
    
    assignments = Assignment.query.filter_by(lecturer_id=lecturer_id).all()
    modules = [assignment.module for assignment in assignments]
    
    return render_template('admin_lecturer_assignments.html', lecturer=lecturer, modules=modules)