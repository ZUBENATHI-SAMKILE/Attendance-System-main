## 🎓 Face Recognition Attendance System for Students

Live Demo :https://attendance-system-main-1-fcvz.onrender.com 
Only can run after sql is connected .

#  Project Overview

- The Face Recognition Attendance System is a Flask-based web application designed to automate student attendance tracking using face recognition technology.
- It aims to minimize absenteeism, reduce manual errors, and help lecturers monitor class participation efficiently.
- This system addresses the challenge of unreliable manual attendance systems and leverages AI-powered face detection
- and recognition to ensure secure, tamper-proof attendance recording.

# Motivation
- High student absenteeism contributes significantly to low academic performance and drop-out rates in universities.
- Traditional attendance methods (signing sheets, roll calls) are time-consuming, prone to fraud, and lack proper data integrity.

# This system was developed to:

- Ensure accurate and automated attendance marking.
- Eliminate human intervention and manipulation.
- Provide real-time attendance data for lecturers and administrators.

⚙️ System Features
- Face Recognition Attendance
1. Automatically detects and identifies student faces using a camera.
2. Marks attendance in real-time without manual input.

- User Authentication

1. Secure login for lecturers and admins.
2. Role-based access to attendance data.

- Attendance Records Management
1. Stores attendance history securely in the database.
2. Prevents tampering with attendance records.

- Performance Integration
1. Allows lecturers to allocate marks for attendance as part of a student’s continuous assessment.

- Flask Web Interface
1. Simple, user-friendly dashboard for lecturers and admins to view attendance data.

🧩 Tech Stack

- Backend Framework	Flask (Python)
- Database	SQL and SQLite 
- Face Recognition	face_recognition Python library (uses dlib)
- Frontend	HTML, CSS, and Javascript
- OpenCv
- IDE	 VS Code
- Language	Python 

- How to Run the Project
1. Clone the Repository
git clone https://github.com/ZUBENATHI-SAMKILE/Attendance-System-main.git
cd FaceRecognitionAttendance

 2.Install Dependencies
pip install -r requirements.txt

3️. Run the Application
python run.py

4️. Access the System

Open your browser and go to:

http://127.0.0.1:5000

- Usage

1. Register Students — Add student details and capture their face data. 

2. Train Model — The system encodes and saves facial features for recognition.

3. Mark Attendance — When a student appears before the camera, their face is detected and attendance recorded automatically.

4. View Records — Lecturers can log in to check daily/weekly attendance and allocate participation marks.

🔒 Security

- Dut students email only allowed for registration.
- Attendance data cannot be altered manually.
- Only authorized users (lecturers/admins) can access attendance records.
- Each student’s identity is verified through facial features to prevent proxy attendance.

-Team & Contributions
Developed by a student team as part of a university research and system development project focused on enhancing attendance accuracy and student engagement using AI and Flask technology.
