# AiSteadMai - Group 26

🔐 A full-stack Django application with **custom user authentication**, **session management**, and a **modular structure** — designed for the **ICT2216 Secure Software Development** project.

💘AiSteadMai is a secure and user-friendly Django web application that helps individuals connect meaningfully through an intelligent matching system. It features a clean UI, robust session-based authentication, and customizable preferences — all built with a focus on security, modularity, and scalability.

🔗 Live Production Site: https://www.aisteadmai.shop/login/

---

## 🚀 Features

- 🔐 Custom login, registration, password reset
- 🛡️ Middleware for session and auth validation
- 🧩 Modular project structure (`core`, `authentication`)
- ✅ Django Forms validation
- 💾 SQLite + Django ORM
- 📦 Environment config via `.env`
- 💡 Styled with [Argon Dashboard](https://www.creative-tim.com/product/argon-dashboard)
- 🧪 GitHub Actions CI/CD workflow ready

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/ICT2216-SSD-GRP26.git
cd ICT2216-SSD-GRP26
<!-- Create and Activate a Virtual Environment -->
python -m venv venv
.\venv\Scripts\activate
<!-- Install Required Python Packages -->
pip install -r requirements.txt
<!-- Apply Database Migrations -->
python manage.py makemigrations
python manage.py migrate
<!-- Run the Development Server -->
python manage.py runserver


