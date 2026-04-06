# 🦆 Quack Quiz - AI Reverse Quiz Engine

Quack Quiz is a full-stack interactive web application that flips the traditional quiz format. Instead of answering questions, users are given an AI-generated **Fact** and a **Cryptic Hint** and must guess the underlying **Concept**.

## 🚀 Features
- **AI Generation:** Uses Google Gemini 2.5 Flash to generate unique facts/hints.
- **Intelligent Validation:** A second AI pass validates guesses, allowing for minor typos and case-insensitivity.
- **Admin Dashboard:** A secured panel to manage users and reset scores.
- **Skip Logic:** Users can skip difficult questions to get a fresh AI-generated challenge.
- **Modern UI:** Responsive dark-mode interface built with Tailwind CSS.

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python)
- **Database:** SQLAlchemy (SQLite)
- **AI:** Google Generative AI (Gemini API)
- **Frontend:** JavaScript (ES6+), Tailwind CSS

## 📦 Installation & Setup
1. **Clone the repo:** `git clone <your-repo-url>`
2. **Setup Venv:** `python -m venv venv` and activate it.
3. **Install Libs:** `pip install -r requirements.txt`
4. **Environment Variables:** Create a `.env` file and add `GOOGLE_API_KEY=your_key_here`.
5. **Run:** `uvicorn main:app --reload`

## 🛡️ Admin Access
To test admin features, register with the username `admin`. The system automatically grants administrative rights to this specific handle.