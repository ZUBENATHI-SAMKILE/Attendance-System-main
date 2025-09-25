# facial_recognition.py - FIXED
import cv2
import os
from config import Config
import numpy as np
from datetime import datetime, timezone
from app.models import Attendance, AttendanceStatus, ClassSession, Enrollment, FacialData, User
from app import db
import base64
import json

class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy data types"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

def verify_face(image_path, student_number, upload_folder):
    """Verify if the uploaded image contains a clear face"""
    try:
        image = cv2.imread(image_path)
        if image is None:
            return False, "Invalid image file"
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return False, "No face detected in the image"
        elif len(faces) > 1:
            return False, "Multiple faces detected. Please upload an image with only one face"
        else:
            return True, "Face verified successfully"
            
    except Exception as e:
        return False, f"Error processing image: {str(e)}"

def extract_face_embeddings(image_path):
    """Extract face embeddings using OpenCV's face recognizer"""
    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect face
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return None
        
        # Extract face region and resize to standard size
        x, y, w, h = faces[0]
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (100, 100))
        
        # Normalize and flatten
        face_roi = face_roi.astype(np.float32) / 255.0
        embeddings = face_roi.flatten()
        
        return embeddings
        
    except Exception as e:
        print(f"Error extracting embeddings: {e}")
        return None

def compare_faces(embedding1, embedding2, threshold=0.6):
    """Compare two face embeddings using cosine similarity"""
    if embedding1 is None or embedding2 is None:
        return 0.0
    
    # Calculate cosine similarity
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(similarity)  # Convert to native Python float

def recognize_face_from_image(image_data, class_id):
    """Recognize face from image data and mark attendance for specific class session"""
    try:
        # Check if class session exists and get detailed info (FROM ATTACHED CODE)
        class_session = ClassSession.query.get(class_id)
        if not class_session:
            return {'success': False, 'message': 'Class not found'}
        
        # Detailed class info for debugging (FROM ATTACHED CODE)
        class_info = f"{class_session.module.module_code} on {class_session.class_date} at {class_session.start_time.strftime('%H:%M')}"
        
        # Check if class session time has passed (FROM ATTACHED CODE)
        current_time = datetime.now(timezone.utc).astimezone()
        class_datetime = datetime.combine(class_session.class_date, class_session.end_time)
        class_datetime = class_datetime.replace(tzinfo=current_time.tzinfo)
        
        if current_time > class_datetime:
            return {'success': False, 'message': f'Class session {class_info} has ended. Attendance cannot be marked.'}
        
        # Decode base64 image
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {'success': False, 'message': 'Invalid image data'}
        
        # Extract face embeddings from captured image
        captured_embeddings = extract_face_embeddings_from_frame(image)
        if captured_embeddings is None:
            return {'success': False, 'message': 'No face detected in captured image'}
        
        # Get enrolled students for this SPECIFIC class session's module (FROM ATTACHED CODE)
        enrollments = Enrollment.query.filter_by(module_id=class_session.module_id).all()
        best_match = None
        best_similarity = 0.0
        similarity_threshold = 0.6
        
        print(f"Checking {len(enrollments)} enrolled students for class {class_info}")  # FROM ATTACHED CODE
        
        for enrollment in enrollments:
            student = enrollment.student
            facial_data = FacialData.query.filter_by(student_id=student.user_id).first()
            
            if facial_data:
                # Get stored face embeddings
                stored_image_path = os.path.join(Config.UPLOAD_FOLDER, facial_data.image_path)
                stored_embeddings = extract_face_embeddings(stored_image_path)
                
                if stored_embeddings is not None:
                    similarity = compare_faces(captured_embeddings, stored_embeddings)
                    
                    if similarity > best_similarity and similarity > similarity_threshold:
                        best_similarity = similarity
                        best_match = student
                        print(f"Better match found: {student.full_name} ({student.student_number}) - {similarity:.2f}")  # FROM ATTACHED CODE
        
        if best_match:
            # Check if attendance already exists for THIS SPECIFIC class session (FROM ATTACHED CODE)
            existing_attendance = Attendance.query.filter_by(
                student_id=best_match.user_id,
                class_id=class_id  # Specific to this exact class session
            ).first()
            
            if existing_attendance:
                return {
                    'success': True,
                    'message': f'Attendance already marked for {best_match.full_name} in {class_info}',
                    'student_name': best_match.full_name,
                    'student_number': best_match.student_number,
                    'similarity': round(best_similarity * 100, 2),
                    'already_marked': True,
                    'class_info': class_info  # FROM ATTACHED CODE
                }
            else:
                # Mark attendance for THIS SPECIFIC class session (FROM ATTACHED CODE)
                attendance = Attendance(
                    student_id=best_match.user_id,
                    class_id=class_id,  # Specific to this exact class session
                    attendance_status=AttendanceStatus.present,
                    timestamp=datetime.now(timezone.utc).astimezone()
                )
                db.session.add(attendance)
                db.session.commit()
                
                print(f"Attendance marked for {best_match.full_name} in {class_info}")  # FROM ATTACHED CODE
                
                return {
                    'success': True,
                    'message': f'Attendance marked for {best_match.full_name} in {class_info}',
                    'student_name': best_match.full_name,
                    'student_number': best_match.student_number,
                    'similarity': round(best_similarity * 100, 2),
                    'already_marked': False,
                    'class_info': class_info  # FROM ATTACHED CODE
                }
        else:
            return {'success': False, 'message': 'No matching student found. Please ensure facial data is registered.'}  # ENHANCED MESSAGE FROM ATTACHED CODE
            
    except Exception as e:
        db.session.rollback()  # FROM ATTACHED CODE
        print(f"Error in face recognition for class {class_id}: {str(e)}")  # FROM ATTACHED CODE
        return {'success': False, 'message': f'Error in face recognition: {str(e)}'}

def extract_face_embeddings_from_frame(image):
    """Extract face embeddings directly from image frame"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect face
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return None
        
        # Extract largest face (FROM ATTACHED CODE)
        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (100, 100))
        
        # Normalize and flatten
        face_roi = face_roi.astype(np.float32) / 255.0
        embeddings = face_roi.flatten()
        
        return embeddings
        
    except Exception as e:
        print(f"Error extracting embeddings from frame: {e}")
        return None