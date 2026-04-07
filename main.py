import os
import json
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import google.generativeai as genai
from dotenv import load_dotenv
from passlib.context import CryptContext
from database import get_db, User

# --- Security Configuration ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("No GOOGLE_API_KEY found in .env file")
genai.configure(api_key=api_key)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Pydantic Models ---
class TopicRequest(BaseModel):
    topic: str

class ValidationRequest(BaseModel):
    user_guess: str
    answer_key: str
    user_id: int 

class AuthRequest(BaseModel):
    username: str
    password: str

# --- AI Configuration ---
engine_instructions = """
ROLE: You are the "Reverse Quiz Engine" for beginners and hobbyists.
MODE: JSON-ONLY Output.

DIFFICULTY LEVEL: Simple to Medium. 
- Avoid deep internals like GIL, memory management, or bytecode.
- Focus on common concepts (e.g., Loops, Lists, Variables, Functions, Strings, Classes, Objects, Regular Expressions, Exception Handling, Instance, File Handling, Tuples, Sets, Dictionary, Constructor, Operators, Type Casting).
- Focus on practical usage rather than computer science theory.

CORE LOGIC: 
1. Receive a TOPIC (e.g., "Python").
2. Pick a fundamental, easy-to-understand concept within that topic.
3. Generate a clear FACT and a playful HINT.
4. Ensure the ANSWER_KEY is the common name of that concept.

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
  "fact": "...",
  "hint": "...",
  "answer_key": "..."
}
"""

# Change the model names in main.py to this:
model = genai.GenerativeModel(
    model_name="gemini-flash-latest", 
    system_instruction=engine_instructions, 
    generation_config={
        "response_mime_type": "application/json",
        "temperature": 0.8,  # Higher temperature = more variety
        "top_p": 0.95,
    }
)

validator_model = genai.GenerativeModel(model_name="gemini-flash-latest")

# --- HTML Routes ---
@app.get("/")
def read_root(): 
    return FileResponse("static/index.html")

@app.get("/login")
def read_login(): 
    return FileResponse("static/login.html")

@app.get("/admin")
def read_admin(): 
    return FileResponse("static/admin.html")

# --- Security Middleware ---
def verify_admin(x_user_id: str = Header(None), db: Session = Depends(get_db)):
    if not x_user_id or x_user_id == "null":
        raise HTTPException(status_code=401, detail="Unauthorized: No valid session")
    
    try:
        safe_user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid ID format")
        
    user = db.query(User).filter(User.id == safe_user_id).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
        
    return user

# --- Auth Routes ---
@app.post("/api/register")
def register_user(req: AuthRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = pwd_context.hash(req.password)
    is_new_user_admin = True if req.username.lower() == "admin" else False
    
    new_user = User(username=req.username, password=hashed_password, is_admin=is_new_user_admin)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/api/login")
def login_user(req: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not pwd_context.verify(req.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    return {
        "message": "Login successful", 
        "user_id": user.id, 
        "username": user.username, 
        "score": user.total_score, 
        "is_admin": user.is_admin
    }

# --- Game Routes ---
@app.post("/api/generate_quiz")
def generate_quiz(req: TopicRequest):
    try:
        prompt = (
            f"Topic: {req.topic}. Create a simple or medium difficulty quiz. "
            "Choose a random basic building block. DO NOT ask about the GIL or complex internals."
        )
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Robust Markdown Cleaning
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0]
            
        return json.loads(raw_text.strip())
    except Exception as e:
        print(f"AI Gen Error: {e}")
        raise HTTPException(status_code=500, detail="AI Generation Error")

@app.post("/api/validate_guess")
def validate_guess(req: ValidationRequest, db: Session = Depends(get_db)):
    try:
        prompt = (
            f"Correct Concept: '{req.answer_key}'.\n"
            f"User Guess: '{req.user_guess}'.\n"
            "Is the user's guess conceptually the same? "
            "BE LENIENT. Ignore capitalization, extra spaces, or minor typos. "
            "Reply with ONLY 'True' or 'False'."
        )
        response = validator_model.generate_content(prompt)
        is_correct = "true" in response.text.strip().lower()

        user = db.query(User).filter(User.id == req.user_id).first()
        if user and is_correct:
            user.total_score += 10
            db.commit()
            return {"is_correct": True, "new_score": user.total_score}
        
        return {"is_correct": False, "new_score": user.total_score if user else 0}
    except Exception as e:
        print(f"AI Val Error: {e}")
        raise HTTPException(status_code=500, detail="AI Validation Error")

# --- SECURED ADMIN ROUTES ---
@app.get("/api/admin/users")
def get_all_users(admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "score": u.total_score, "is_admin": u.is_admin} for u in users]

@app.put("/api/admin/users/{target_id}/reset")
def reset_user_score(target_id: int, admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == target_id).first()
    if user:
        user.total_score = 0
        db.commit()
        return {"message": "Score reset"}
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/api/admin/users/{target_id}/toggle_admin")
def toggle_admin_status(target_id: int, admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    target_user = db.query(User).filter(User.id == target_id).first()
    if target_user:
        if target_user.id == admin.id:
            raise HTTPException(status_code=400, detail="You cannot demote yourself.")
        target_user.is_admin = not target_user.is_admin
        db.commit()
        return {"message": "Admin status updated"}
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/api/admin/users/{target_id}")
def delete_user(target_id: int, admin: User = Depends(verify_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == target_id).first()
    if user:
        if user.is_admin:
            raise HTTPException(status_code=400, detail="Cannot delete an admin account")
        db.delete(user)
        db.commit()
        return {"message": "User deleted"}
    raise HTTPException(status_code=404, detail="User not found")