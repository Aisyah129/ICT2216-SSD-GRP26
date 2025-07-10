# AiSteadMai - Group 26

🔐 A full-stack Django application with **custom user authentication**, **session management**, and a **modular structure** — designed for the **ICT2216 Secure Software Development** project.

💘AiSteadMai is a secure and user-friendly Django web application that helps individuals connect meaningfully through an intelligent matching system. It features a clean UI, robust session-based authentication, and customizable preferences — all built with a focus on security, modularity, and scalability.

🔗 Live Production Site: https://www.aisteadmai.shop/login/

---

## 🚀 Features

- 🧭 Browse Profiles: Users can swipe through other user profiles, view photos, bios, and match scores.
- 💖 Like & Match System: Like users to build potential connections. When two users like each other, it becomes a match.
- 🎯 Set Preferences: Users can filter matches by age, distance, height, religion, languages spoken, and more.
- 🗣️ Multilingual Support: Profiles can include multiple spoken languages, improving cultural inclusivity.
- 💬 In-App Messaging: Matched users can exchange messages in real-time via an integrated chat system.
- 📸 Photo Upload & Gallery: Users can upload multiple profile photos and choose a primary display image.
- ⭐ Premium Features: Premium users enjoy perks like full access to who liked them and advanced filtering options.
- 🧠 AI-Enhanced Matching: Intelligent sorting of profile suggestions based on past likes and preference matching.
- 🖥️ Admin Dashboard: Admins can view user stats, moderate content, and manage platform settings.

---

## 🛠️ Setup Instructions

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/ICT2216-SSD-GRP26.git
cd ICT2216-SSD-GRP26

# Create and Activate a Virtual Environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# Install Required Python Packages
pip install -r requirements.txt

# Apply Database Migrations
python manage.py makemigrations
python manage.py migrate

# Run the Development Server
python manage.py runserver
