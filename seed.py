from app import app, db
from app.models import User, Role, Module, Assignment, Enrollment, ClassSession, ClassType, Attendance, AttendanceStatus, FacialData
from werkzeug.security import generate_password_hash
from datetime import date, time, datetime

def seed_database():
    with app.app_context():
        try:
            # Create Admin
            admin = User.query.filter_by(email='admin@example.com').first()
            if not admin:
                admin = User(
                    full_name='Admin User',
                    email='admin@example.com',
                    password_hash=generate_password_hash('adminpass'),
                    role=Role.admin
                )
                db.session.add(admin)
                print("Admin created.")

            lecturer = User.query.filter_by(email='lecturer@dut.ac.za').first()
            if not lecturer:
                lecturer = User(
                    full_name='Dr. John Lecturer',
                    email='lecturer@dut.ac.za',
                    password_hash=generate_password_hash('lectpass'),
                    role=Role.lecturer
                )
                db.session.add(lecturer)
                print("Lecturer created.")

            # Create Students with proper student numbers (starting with 22)
            students = []
            for i in range(1, 4):
                student_number = f'22{i:06d}'  # 22 followed by 6 digits
                email = f'student{i}@dut4life.ac.za'
                student = User.query.filter_by(student_number=student_number).first()
                if not student:
                    student = User(
                        full_name=f'Student {i}',
                        email=email,
                        student_number=student_number,
                        password_hash=generate_password_hash('studpass'),
                        role=Role.student
                    )
                    db.session.add(student)
                    print(f"Student {i} created.")
                students.append(student)

            # Commit users
            db.session.commit()

            # Create Module
            module = Module.query.filter_by(module_code='CS101').first()
            if not module:
                module = Module(
                    module_code='CS101',
                    module_name='Introduction to Computer Science',
                    description='Basic CS course'
                )
                db.session.add(module)
                db.session.commit()
                print("Module created.")

            # Assign lecturer to module
            assignment = Assignment.query.filter_by(lecturer_id=lecturer.user_id, module_id=module.module_id).first()
            if not assignment:
                assignment = Assignment(
                    lecturer_id=lecturer.user_id,
                    module_id=module.module_id,
                    assigned_date=date(2025, 9, 1)
                )
                db.session.add(assignment)
                db.session.commit()
                print("Assignment created.")

            # Enroll students in module
            for student in students:
                enrollment = Enrollment.query.filter_by(student_id=student.user_id, module_id=module.module_id).first()
                if not enrollment:
                    enrollment = Enrollment(
                        student_id=student.user_id,
                        module_id=module.module_id,
                        enrollment_date=date(2025, 9, 1)
                    )
                    db.session.add(enrollment)
                    print(f"Student {student.student_number} enrolled.")
            db.session.commit()

            # Create ClassSessions over September 2025 at different days/times
            classes = [
                {'date': date(2025, 9, 2), 'start': time(9, 0), 'end': time(10, 0)},  # Tuesday
                {'date': date(2025, 9, 5), 'start': time(10, 0), 'end': time(11, 0)},  # Friday
                {'date': date(2025, 9, 10), 'start': time(9, 0), 'end': time(10, 0)},  # Wednesday
                {'date': date(2025, 9, 15), 'start': time(14, 0), 'end': time(15, 0)},  # Monday
                {'date': date(2025, 9, 20), 'start': time(11, 0), 'end': time(12, 0)},  # Saturday
                {'date': date(2025, 9, 25), 'start': time(15, 0), 'end': time(16, 0)},   # Thursday
                {'date': date(2025, 9, 26), 'start': time(00, 00), 'end': time(18, 00)}
            ]

            class_sessions = []
            for cls in classes:
                # Check for existing class with same module, date, AND time
                session = ClassSession.query.filter_by(
                    module_id=module.module_id, 
                    class_date=cls['date'],
                    start_time=cls['start']
                ).first()
                
                if not session:
                    session = ClassSession(
                        module_id=module.module_id,
                        lecturer_id=lecturer.user_id,
                        class_type=ClassType.lecture,
                        class_date=cls['date'],
                        start_time=cls['start'],
                        end_time=cls['end'],
                        location='Room 101'
                    )
                    db.session.add(session)
                    print(f"Class on {cls['date']} at {cls['start']} created.")
                else:
                    print(f"Class on {cls['date']} at {cls['start']} already exists.")
                
                class_sessions.append(session)
                db.session.commit()

                # Create Attendance records for past classes only (not today)
                today = date.today()
                for session in class_sessions:
                    # Only create attendance records for past classes
                    if session.class_date < today:
                        for student in students:
                            att = Attendance.query.filter_by(student_id=student.user_id, class_id=session.class_id).first()
                            if not att:
                                # Create timestamp based on class date and start time
                                class_datetime = datetime.combine(session.class_date, session.start_time)
                                
                                att = Attendance(
                                    student_id=student.user_id,
                                    class_id=session.class_id,
                                    attendance_status=AttendanceStatus.absent,
                                    timestamp=class_datetime  # Set to actual class time instead of current time
                                )
                                db.session.add(att)

                db.session.commit()

                # Set attendance patterns for past classes only
                # Student1: Present for all past classes
                for session in class_sessions:
                    if session.class_date < today:
                        att = Attendance.query.filter_by(
                            student_id=students[0].user_id, 
                            class_id=session.class_id
                        ).first()
                        if att:
                            att.attendance_status = AttendanceStatus.present
                            # Update timestamp to match class time for present records too
                            att.timestamp = datetime.combine(session.class_date, session.start_time)

                # Student2: Present for first 4 past classes, absent for others
                past_sessions = [s for s in class_sessions if s.class_date < today]
                for i, session in enumerate(past_sessions):
                    att = Attendance.query.filter_by(
                        student_id=students[1].user_id, 
                        class_id=session.class_id
                    ).first()
                    if att:
                        if i < 4:  # Present for first 4 classes
                            att.attendance_status = AttendanceStatus.present
                        else:
                            att.attendance_status = AttendanceStatus.absent
                        # Set timestamp to match class time
                        att.timestamp = datetime.combine(session.class_date, session.start_time)

                # Student3: Present for first 2 past classes only
                for i, session in enumerate(past_sessions):
                    att = Attendance.query.filter_by(
                        student_id=students[2].user_id, 
                        class_id=session.class_id
                    ).first()
                    if att:
                        if i < 2:  # Present for first 2 classes
                            att.attendance_status = AttendanceStatus.present
                        else:
                            att.attendance_status = AttendanceStatus.absent
                        # Set timestamp to match class time
                        att.timestamp = datetime.combine(session.class_date, session.start_time)

                db.session.commit()
            print("Attendance records created for past classes.")

            # Optional: Add placeholder facial data for students (since no real images)
            for student in students:
                facial = FacialData.query.filter_by(student_id=student.user_id).first()
                if not facial:
                    facial = FacialData(
                        student_id=student.user_id,
                        image_path=f'student_{student.student_number}.jpg'  # Assume files exist or placeholders
                    )
                    db.session.add(facial)
                    print(f"Facial data for {student.student_number} added.")
            db.session.commit()

            print("Database seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error during seeding: {str(e)}")

if __name__ == '__main__':
    seed_database()