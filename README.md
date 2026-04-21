# DSA Tracker Backend

A FastAPI-based backend application designed to help users track their progress in Data Structures and Algorithms (DSA). The system supports authentication, problem tracking, notes management, academic tracking, and intelligent recommendations based on user performance.

---

## Overview

This project provides a structured backend for managing DSA preparation. It allows users to record submissions, analyze weaknesses, maintain notes, and receive personalized problem recommendations. The system is built with scalability and clean architecture in mind.

---

## Features

- User Authentication (Register/Login with JWT)
- Secure Password Handling
- Role-Based Access Control (Student/Admin)
- Problem Tracking System
- Notes Management
- Academic Performance Tracking (CGPA, Attendance)
- Recommendation Engine based on weak topics
- LeetCode Sync Support
- RESTful API Design
- Structured Error Handling

---

## Tech Stack

- Backend: FastAPI
- Language: Python
- Database: Supabase (PostgreSQL)
- Authentication: JWT
- HTTP Client: httpx

---

## Project Structure

DSA-TRACKER/

│
├── main.py  
├── authentication.py  
├── academic.py  
├── notes.py  
├── problems.py  
├── submissions.py  
├── recommendations.py  
├── database.py  
├── schemas.py  
├── security.py  
├── response.py  
├── loggings.py  
├── leetcode_bank.py  
├── requirements.txt  
└── .env.example  

---

## Setup Instructions

### 1. Clone the Repository

git clone https://github.com/eshaaa18/DSA-TRACKER-2.0.git  
cd DSA-TRACKER-2.0  

---

### 2. Create Environment Variables

Create a `.env` file in the root directory and add:

SUPABASE_URL=  
SUPABASE_ANON_KEY=  
SUPABASE_SERVICE_KEY=  
JWT_SECRET=  

---

### 3. Install Dependencies

pip install -r requirements.txt  

---

### 4. Run the Server

uvicorn main:app --reload  

---

## API Documentation

Once the server is running:

http://127.0.0.1:8000/docs  

---

## Usage Flow

1. Register a new user  
2. Login to receive a JWT token  
3. Authorize using the token  
4. Track problems and submissions  
5. Add notes and academic data  
6. Get personalized recommendations  

---

## Future Improvements

- Frontend integration  
- Deployment  
- Analytics dashboard  
- Enhanced recommendation system  

---

## License

This project is for educational and personal use.

---

🎀
