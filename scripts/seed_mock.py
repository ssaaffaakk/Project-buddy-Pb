"""
Mock Data Seeder for ProjectBuddy
Run: python scripts/seed_mock.py
Clears existing non-admin data and seeds fresh realistic IUS mock data.
"""
import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# Allow running as `python scripts/seed_mock.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from extensions import db
from models import (
    User, UserInterest, UserSkill, UserCourse,
    Project, ProjectTag, ProjectSkill, ProjectMember, Application,
    Feedback, Endorsement, Badge, UserBadge,
    StudyGroup, StudyGroupMember, StudyGroupMessage,
    CommunityPost, CommunityComment, CommunityLike,
    Notification, ChatbotSession
)
from datetime import datetime, timedelta
import random

app = create_app()

# ── STUDENTS ──────────────────────────────────────────────────────────────────
STUDENTS = [
    # (first, last, email, dept, bio, skills, interests, courses)
    ("Amir",    "Kovačević", "amir.kovacevic@ius.edu.ba",
     "Computer Science",
     "CS junior passionate about backend systems and distributed computing. Love building APIs and working with databases.",
     ["Python","Flask","PostgreSQL","Docker","REST APIs","Git"],
     ["Python","SQL / DB","Cloud","DevOps","Networks","Docker / K8s"],
     ["CS201 — Data Structures","CS210 — Database Systems","CS230 — Operating Systems","CS301 — Computer Networks","MATH202 — Statistics & Probability"]),

    ("Leila",   "Hadžić",   "leila.hadzic@ius.edu.ba",
     "Software Engineering",
     "SE student focused on mobile and full-stack development. Currently building a student marketplace app.",
     ["React","TypeScript","Flutter","Node.js","MongoDB","Figma"],
     ["React","Mobile Dev","UI/UX Design","JavaScript","Flutter","Big Data"],
     ["SE202 — Software Design & Architecture","SE301 — Software Testing & QA","CS304 — Web Programming","CS305 — Mobile Development","ENG102 — Academic English II"]),

    ("Emre",    "Yıldız",   "emre.yildiz@ius.edu.ba",
     "Electrical & Electronics Engineering",
     "EEE student interested in embedded systems and IoT. Built several Arduino and Raspberry Pi projects.",
     ["C","C++","Arduino","VHDL","MATLAB","Python"],
     ["Embedded Systems","Electronics","IoT","Robotics","Control Systems","Signal Processing"],
     ["EEE201 — Electronics","EEE202 — Digital Logic","EEE301 — Microprocessors","EEE302 — Signals & Systems","PHYS102 — Physics II"]),

    ("Sara",    "Mustafić",  "sara.mustafic@ius.edu.ba",
     "Business Administration",
     "BA student with a passion for startup culture and marketing. Co-founded a student consulting club at IUS.",
     ["Excel","PowerPoint","Marketing Analytics","Canva","SQL"],
     ["Marketing","Entrepreneurship","Business Analytics","Management","E-commerce","Finance"],
     ["BA201 — Marketing","BA302 — Strategic Management","BA401 — Entrepreneurship","ECON201 — Microeconomics","ENG102 — Academic English II"]),

    ("Nikola",  "Petrović",  "nikola.petrovic@ius.edu.ba",
     "Computer Science",
     "Senior CS student specializing in machine learning and data science. Research assistant at the AI Lab.",
     ["Python","TensorFlow","PyTorch","Scikit-learn","Pandas","NumPy","SQL"],
     ["Machine Learning","AI / NLP","Data Analysis","Computer Vision","Python","Big Data"],
     ["CS303 — Artificial Intelligence","CS401 — Machine Learning","CS404 — Senior Project I","MATH201 — Linear Algebra","MATH202 — Statistics & Probability"]),

    ("Fatima",  "Salihović", "fatima.salihovic@ius.edu.ba",
     "Psychology",
     "Psychology student interested in UX research and human-computer interaction. Volunteer at the student counseling center.",
     ["Research Methods","SPSS","Qualitative Analysis","Survey Design","Figma"],
     ["Psychology","Research & Academia","UI/UX Design","Communication","Statistics","Human Behavior"],
     ["PSY201 — Social Psychology","PSY301 — Research Methods in Psychology","PSY401 — Clinical Psychology","ENG101 — Academic English I","TUR102 — Turkish II"]),

    ("Damir",   "Begić",     "damir.begic@ius.edu.ba",
     "Software Engineering",
     "Full-stack developer with a love for open source. Maintainer of two npm packages with 500+ weekly downloads.",
     ["JavaScript","React","Node.js","Express","PostgreSQL","Docker","Linux"],
     ["JavaScript","React","Node.js","DevOps","Docker / K8s","SQL / DB"],
     ["SE101 — Intro to Software Engineering","SE302 — Agile Development","CS304 — Web Programming","CS402 — Cloud Computing","SE402 — DevOps"]),

    ("Amina",   "Zukić",     "amina.zukic@ius.edu.ba",
     "Architecture",
     "Architecture student passionate about sustainable design and smart cities. Winner of the 2024 IUS Design Award.",
     ["AutoCAD","Revit","SketchUp","Photoshop","Rhino","3ds Max"],
     ["Architecture Design","3D Modeling / CAD","Urban Planning","Sustainable Design","BIM / Revit","Graphic Design"],
     ["ARCH101 — Design Studio I","ARCH201 — Design Studio II","ARCH301 — Structural Systems","ARCH401 — Urban Design","ENG101 — Academic English I"]),

    ("Haris",   "Imamović",  "haris.imamovic@ius.edu.ba",
     "Computer Science",
     "Cybersecurity enthusiast and CTF player. Part of the IUS CyberSec team that placed 3rd in regional competition.",
     ["Python","Linux","Wireshark","Metasploit","Burp Suite","Assembly","C"],
     ["Cybersecurity","Networks","Python","Embedded Systems","Blockchain","DevOps"],
     ["CS230 — Operating Systems","CS301 — Computer Networks","CS320 — Cybersecurity","CS403 — Distributed Systems","CS404 — Senior Project I"]),

    ("Zeynep",  "Arslan",    "zeynep.arslan@ius.edu.ba",
     "Communication & Design",
     "Graphic designer and content creator. Run a design blog with 2k+ followers. Love branding and visual storytelling.",
     ["Adobe Illustrator","Photoshop","Premiere Pro","After Effects","Figma","Canva"],
     ["Graphic Design","UI/UX Design","Video Editing","Photography","Animation","Communication"],
     ["COMM201 — Media & Communication","COMM301 — Design Principles","COMM401 — Digital Media","ENG102 — Academic English II","TUR101 — Turkish I"]),

    ("Kemal",   "Duraković",  "kemal.durakovic@ius.edu.ba",
     "Computer Science",
     "Game developer and CS sophomore. Working on an indie game in Unity. Also interested in graphics programming.",
     ["C#","Unity","C++","OpenGL","Blender","Python"],
     ["Game Dev","Computer Vision","3D Modeling / CAD","UI/UX Design","Python","Embedded Systems"],
     ["CS101 — Intro to Programming","CS201 — Data Structures","CS202 — Algorithms","CS220 — OOP","CS310 — Computer Graphics"]),

    ("Irma",    "Handžić",   "irma.handzic@ius.edu.ba",
     "International Relations",
     "IR student with interest in tech policy and digital governance. Interning at a Sarajevo-based NGO this semester.",
     ["Research","Policy Analysis","English","French","Excel"],
     ["International Relations","Law","Research & Academia","Communication","Economics","Management"],
     ["IR201 — International Relations","IR301 — European Studies","IR401 — Diplomacy","ECON201 — Microeconomics","ENG102 — Academic English II"]),

    ("Omer",    "Čaušević",  "omer.causevic@ius.edu.ba",
     "Biomedical Engineering",
     "BME student focused on medical imaging and signal processing. Research project on ECG anomaly detection using ML.",
     ["Python","MATLAB","C++","TensorFlow","Signal Processing"],
     ["Biomedical Research","Signal Processing","Machine Learning","Embedded Systems","Python","Research & Academia"],
     ["BME201 — Biomechanics","BME301 — Medical Imaging","BME401 — Biomedical Instrumentation","EEE302 — Signals & Systems","CS401 — Machine Learning"]),

    ("Mia",     "Nikolić",   "mia.nikolic@ius.edu.ba",
     "Computer Science",
     "CS freshman excited about web development and UI design. Building my first SaaS project this year.",
     ["HTML","CSS","JavaScript","React","Figma","Git"],
     ["React","UI/UX Design","JavaScript","Mobile Dev","Python","Data Analysis"],
     ["CS101 — Intro to Programming","CS121 — Discrete Mathematics","CS304 — Web Programming","ENG101 — Academic English I","MATH101 — Calculus I"]),
]

# ── PROJECTS ──────────────────────────────────────────────────────────────────
PROJECTS = [
    {
        "title": "IUS Smart Campus App",
        "description": "A mobile application to help IUS students navigate campus, find free classrooms, check cafeteria menus, and get real-time event notifications. Looking for mobile devs and a UI/UX designer.",
        "course": "CS305 — Mobile Development",
        "team_size": 4,
        "status": "open",
        "tags": ["Mobile","React Native","Flutter","Campus","IUS"],
        "skills": ["Flutter","React Native","Firebase","Figma","UI/UX"],
        "owner_idx": 1,  # Leila
        "days_ago": 5,
    },
    {
        "title": "ML-Based Exam Score Predictor",
        "description": "Using historical exam data and study habits to predict final exam scores and recommend study strategies. Building a web dashboard for students to track their progress.",
        "course": "CS401 — Machine Learning",
        "team_size": 3,
        "status": "open",
        "tags": ["Machine Learning","Python","Flask","Data Science"],
        "skills": ["Python","Scikit-learn","Pandas","Flask","PostgreSQL"],
        "owner_idx": 4,  # Nikola
        "days_ago": 8,
    },
    {
        "title": "Student Marketplace Platform",
        "description": "A peer-to-peer marketplace for IUS students to buy/sell second-hand textbooks, electronics, and dorm items. Includes a rating system and secure payment integration.",
        "course": "SE202 — Software Design & Architecture",
        "team_size": 4,
        "status": "open",
        "tags": ["Full Stack","React","Node.js","E-commerce","PostgreSQL"],
        "skills": ["React","Node.js","PostgreSQL","Stripe API","Docker"],
        "owner_idx": 6,  # Damir
        "days_ago": 12,
    },
    {
        "title": "AR Campus Tour Guide",
        "description": "Augmented reality application that overlays building info, event schedules, and historical facts onto the IUS campus through your phone camera. Targeted at new students and visitors.",
        "course": "CS305 — Mobile Development",
        "team_size": 3,
        "status": "open",
        "tags": ["AR","Unity","Mobile","C#","3D"],
        "skills": ["Unity","C#","ARCore","ARKit","3D Modeling"],
        "owner_idx": 10,  # Kemal
        "days_ago": 3,
    },
    {
        "title": "Cybersecurity Awareness Platform",
        "description": "Gamified learning platform to teach students about phishing, password hygiene, and social engineering through interactive scenarios and CTF-style challenges.",
        "course": "CS320 — Cybersecurity",
        "team_size": 3,
        "status": "open",
        "tags": ["Cybersecurity","Gamification","Web","Education"],
        "skills": ["Python","Django","JavaScript","React","PostgreSQL"],
        "owner_idx": 8,  # Haris
        "days_ago": 7,
    },
    {
        "title": "Sarajevo Heritage Digital Archive",
        "description": "Digitizing and cataloguing historical photographs and documents from Sarajevo's archives. Building a searchable web platform with metadata tagging and map visualization.",
        "course": "IR301 — European Studies",
        "team_size": 4,
        "status": "open",
        "tags": ["History","Web","Map","Archive","Digital Humanities"],
        "skills": ["React","Python","PostgreSQL","Leaflet.js","Photography"],
        "owner_idx": 11,  # Irma
        "days_ago": 15,
    },
    {
        "title": "Sustainable Architecture Visualizer",
        "description": "3D visualization tool for architects to simulate energy efficiency, natural light, and ventilation for building designs. Integrating with Revit and BIM workflows.",
        "course": "ARCH301 — Structural Systems",
        "team_size": 3,
        "status": "closed",
        "tags": ["Architecture","3D","Simulation","Sustainability","BIM"],
        "skills": ["Revit","Python","Three.js","AutoCAD","3ds Max"],
        "owner_idx": 7,  # Amina
        "days_ago": 30,
    },
    {
        "title": "ECG Anomaly Detection System",
        "description": "Real-time ECG signal processing system that detects cardiac anomalies using deep learning. Deployed on a Raspberry Pi with a web dashboard for monitoring.",
        "course": "BME301 — Medical Imaging",
        "team_size": 3,
        "status": "completed",
        "tags": ["Biomedical","ML","Python","Raspberry Pi","Signal Processing"],
        "skills": ["Python","TensorFlow","Signal Processing","C","Raspberry Pi"],
        "owner_idx": 12,  # Omer
        "days_ago": 60,
    },
    {
        "title": "IUS Study Group Finder",
        "description": "Web app that matches students taking the same courses for study sessions. Integrates with the IUS course schedule and has a real-time group chat feature.",
        "course": "CS302 — Software Engineering",
        "team_size": 4,
        "status": "completed",
        "tags": ["Web","Flask","Real-time","Education","Matching"],
        "skills": ["Flask","PostgreSQL","SocketIO","React","Redis"],
        "owner_idx": 0,  # Amir
        "days_ago": 90,
    },
    {
        "title": "Brand Identity Design for Student NGO",
        "description": "Creating a full brand identity (logo, color palette, typography, social media templates) for a new student-run NGO focused on environmental awareness in Bosnia.",
        "course": "COMM301 — Design Principles",
        "team_size": 2,
        "status": "open",
        "tags": ["Branding","Graphic Design","Adobe","Social Media","NGO"],
        "skills": ["Adobe Illustrator","Photoshop","Figma","Canva","Brand Strategy"],
        "owner_idx": 9,  # Zeynep
        "days_ago": 2,
    },
]

# ── STUDY GROUPS ──────────────────────────────────────────────────────────────
STUDY_GROUPS = [
    {
        "name": "CS301 Network Ninjas",
        "topic": "Computer Networks",
        "description": "Study group for CS301. We meet every Tuesday and Thursday to go through lecture materials and solve past exam questions.",
        "creator_idx": 0,  # Amir
        "member_idxs": [1, 6, 8, 13],
        "messages": [
            (0, "Hey everyone! Let's start with Chapter 5 — Transport Layer this week."),
            (6, "Sounds good. Anyone have the slides from Tuesday's lecture?"),
            (1, "I uploaded them to the Files section. Check it out!"),
            (8, "Great. Also found a good YouTube playlist on TCP/IP. Should I share the link?"),
            (0, "Yes please! Also reminder — exam is in 3 weeks so let's be consistent."),
            (13, "Just joined! Can someone catch me up on what we covered last session?"),
            (6, "Sure Mia, we did OSI model and started on TCP. Check the notes I posted."),
        ],
    },
    {
        "name": "ML & AI Study Circle",
        "topic": "Machine Learning",
        "description": "For CS401 and anyone interested in AI/ML. We do paper reading sessions, Kaggle competitions, and project collaboration.",
        "creator_idx": 4,  # Nikola
        "member_idxs": [0, 12, 6, 2],
        "messages": [
            (4, "Welcome everyone! This week let's do the attention mechanism paper — 'Attention Is All You Need'."),
            (12, "Already read it! The multi-head attention part is brilliant. Anyone want to walk through the math?"),
            (0, "I'll try — give me a bit. Also, are we joining the Titanic Kaggle competition as a team?"),
            (4, "Let's do it. Damir you handle feature engineering, Nikola does the modeling, I'll do EDA."),
            (6, "I'm in. What's our baseline target — top 20%?"),
            (4, "Let's aim for top 10%. We have the skills."),
            (12, "Challenge accepted 💪"),
        ],
    },
    {
        "name": "Architecture Studio Collective",
        "topic": "Architecture Design",
        "description": "Group for ARCH students to share design critiques, reference projects, and collaborate on studio work.",
        "creator_idx": 7,  # Amina
        "member_idxs": [9, 11],
        "messages": [
            (7, "Posted my concept sketches for the urban housing project in Files. Would love feedback!"),
            (9, "Amina these are stunning! The passive cooling strategy is clever. Have you considered solar panels on the south façade?"),
            (7, "Yes! I'm modeling that in Revit now. The angle optimization is tricky with the site orientation."),
            (11, "Not an architecture student but I love what you're doing here. The heritage building integration concept is beautiful."),
            (7, "Thanks Irma! The brief specifically asked for sensitivity to the Ottoman heritage district nearby."),
        ],
    },
    {
        "name": "Cybersec & CTF Team",
        "topic": "Cybersecurity",
        "description": "Practice group for CTF competitions and CS320 exam prep. All skill levels welcome — we learn together.",
        "creator_idx": 8,  # Haris
        "member_idxs": [0, 6],
        "messages": [
            (8, "This week's challenge: Hack The Box machine 'Retired'. Who's in?"),
            (0, "I'll try the web part. Got some experience with SQL injection."),
            (6, "I'll look at the network enumeration. nmap scan already running."),
            (8, "Nice. Let's sync tomorrow evening at 8pm. Also check out the TryHackMe path I shared."),
            (0, "Root flag captured! The privilege escalation was via a misconfigured sudo rule."),
            (8, "Let's go! Document it in our shared notes for the team."),
        ],
    },
    {
        "name": "Business & Startup Hub",
        "topic": "Entrepreneurship",
        "description": "For BA and entrepreneurship students. We discuss startup ideas, pitch practice, and business case studies.",
        "creator_idx": 3,  # Sara
        "member_idxs": [11, 9],
        "messages": [
            (3, "Let's do a business model canvas for each person's idea this week. 10 minutes each, then group feedback."),
            (11, "Love it. I've been working on a policy monitoring platform idea — would love your take on the monetization."),
            (9, "Mine is a design marketplace for Bosnian creatives. Still figuring out the commission structure."),
            (3, "Both sound great! Also — YCombinator startup school applications just opened. Anyone interested in applying?"),
            (11, "Definitely interested. Let's work on the application together."),
        ],
    },
]

# ── COMMUNITY POSTS ───────────────────────────────────────────────────────────
COMMUNITY_POSTS = [
    {
        "author_idx": 4,  # Nikola
        "title": "Resources for Learning Machine Learning from Scratch",
        "body": "After getting many DMs asking how I got into ML, here's my honest roadmap:\n\n1. **Math first**: Linear Algebra (3Blue1Brown), Calculus (Khan Academy), Stats (StatQuest on YouTube)\n2. **Python basics**: Automate the Boring Stuff → then move to NumPy, Pandas\n3. **ML theory**: Andrew Ng's Coursera course is still the gold standard\n4. **Practice**: Kaggle Learn micro-courses → then actual competitions\n5. **Deep learning**: fast.ai → then the original papers\n\nTotal time: ~6 months if you're consistent. Happy to answer questions!",
        "days_ago": 14,
        "likes_idxs": [0, 1, 2, 6, 8, 10, 12, 13],
        "comments": [
            (0, "This is gold. The fast.ai course was a game changer for me too."),
            (13, "Thank you so much! Just started my ML journey. How many hours per day do you recommend?"),
            (4, "1-2 focused hours beats 5 scattered hours any day. Quality over quantity."),
            (6, "Would add: build a project as soon as you can. Theory clicks so much faster when applied."),
        ],
    },
    {
        "author_idx": 7,  # Amina
        "title": "IUS Architecture Students — Design Award Winners Announced!",
        "body": "Incredibly proud to share that our Architecture faculty had 3 student projects shortlisted for the Regional Sustainable Design Award 2024!\n\n🥇 1st place went to our 3rd year team's 'Post-Industrial Riverside Revitalization' project\n🥈 2nd place: 'Passive House Community Hub' by 4th year students\n🏅 Special mention: 'Adaptive Reuse of Ottoman Hammam' — a 2nd year student's solo entry\n\nProud of everyone who participated. Architecture at IUS is growing fast — keep pushing boundaries!",
        "days_ago": 7,
        "likes_idxs": [3, 5, 9, 11, 12, 13],
        "comments": [
            (9, "Congratulations Amina! You deserved that special mention so much."),
            (11, "This is amazing! Architecture at IUS is really putting itself on the map."),
            (7, "Thank you all! None of it would happen without the incredible studio culture we have."),
        ],
    },
    {
        "author_idx": 8,  # Haris
        "title": "IUS CyberSec Team Places 3rd at Regional CTF — Recap",
        "body": "What a weekend! Our 4-person team competed in the Western Balkans Cybersecurity CTF and placed 3rd out of 47 teams.\n\n**What we solved:**\n- Web: 3/4 challenges (XSS, SQLi, JWT exploit)\n- Crypto: 2/3 (RSA misimplementation, hash extension)\n- Forensics: 4/4 (all flags captured 💪)\n- PWN: 1/3 (stack overflow, no heap yet)\n- Misc: 2/2\n\n**What we learned:**\nHeap exploitation is our weak point. Training plan is set for next semester.\n\nIf you want to join the team for next year, comment below or DM me!",
        "days_ago": 10,
        "likes_idxs": [0, 1, 4, 6, 10, 13],
        "comments": [
            (0, "Incredible work! The forensics sweep is impressive."),
            (6, "I want to join next year! How do I get started with CTFs?"),
            (8, "Start with TryHackMe, then picoCTF for beginners. DM me and I'll give you a full roadmap."),
            (4, "Amazing result! What tools did you use for the crypto challenges?"),
            (8, "pwntools, CyberChef, and Python for scripting. The RSA challenge was a classic small-e attack."),
        ],
    },
    {
        "author_idx": 3,  # Sara
        "title": "Startup Idea Validation: Student-to-Student Tutoring Marketplace",
        "body": "I've been working on a startup concept and would love community feedback before I invest more time.\n\n**The Idea:** A peer tutoring marketplace specifically for IUS students. Students who excel in a subject can offer paid 1-on-1 or group sessions to other students.\n\n**Problem it solves:** Tutoring is expensive outside university. Peer tutors who know the IUS curriculum are more relevant than generic tutors.\n\n**Revenue model:** 20% platform commission on each session.\n\n**Questions for you:**\n1. Would you pay €10-15/hour for a top student tutor?\n2. Would you sign up as a tutor if you could earn €8-12/hour?\n3. What features would make this a must-use?\n\nDrop your honest thoughts below!",
        "days_ago": 4,
        "likes_idxs": [1, 2, 5, 6, 11, 12, 13],
        "comments": [
            (5, "Yes to both questions! The curriculum-specific angle is the key differentiator."),
            (4, "I'd definitely sign up as a tutor for math/ML topics. Great idea Sara."),
            (1, "Feature request: let students rate sessions and build tutor reputation scores."),
            (3, "Love that idea Leila! That's going straight into the MVP spec."),
            (11, "The €10-15 price point seems very reasonable. I'd pay that for CS help."),
            (6, "Build the MVP fast and test it. Even a Google Form + WhatsApp group proves the concept."),
        ],
    },
    {
        "author_idx": 1,  # Leila
        "title": "Free Resources I Used to Learn React in 3 Months",
        "body": "Many people ask how I learned React so I figured I'd make a proper post:\n\n**Week 1-2: JavaScript Foundations**\n- javascript.info (best JS resource, period)\n- 30 Days of JavaScript challenge on GitHub\n\n**Week 3-4: React Basics**\n- Official React docs (the new docs with hooks are excellent)\n- Scrimba's free React course\n\n**Week 5-8: Building Things**\n- Build a todo app, then a weather app, then a small e-commerce UI\n- Learn React Router, useState, useEffect, useContext\n\n**Week 9-12: Going Deeper**\n- React Query for data fetching\n- Zustand for state management (simpler than Redux)\n- Start contributing to open source\n\nTotal cost: €0. Everything above is free. No excuses!",
        "days_ago": 20,
        "likes_idxs": [0, 6, 10, 13, 4, 2],
        "comments": [
            (6, "The javascript.info recommendation is so underrated. Best resource out there."),
            (13, "This is exactly what I needed! Starting today."),
            (10, "Would add Wes Bos's JavaScript30 to the foundations list too."),
            (1, "Great addition Kemal! That course is excellent for DOM manipulation."),
        ],
    },
    {
        "author_idx": 5,  # Fatima
        "title": "Psychology Students: UX Research Methods Workshop This Friday",
        "body": "Hey everyone!\n\nThe Psychology department in collaboration with the CS faculty is hosting a **UX Research Methods Workshop** this Friday at 14:00 in Room B204.\n\n**What you'll learn:**\n- Conducting user interviews\n- Usability testing basics\n- Affinity diagramming\n- Writing research reports\n\nThis is a great opportunity for both Psychology and CS/SE students to collaborate and learn human-centered design skills.\n\n**Registration:** just comment below with 'I'm in' — space is limited to 25 participants.\n\nSee you there! 🎉",
        "days_ago": 2,
        "likes_idxs": [1, 3, 7, 9, 11, 13],
        "comments": [
            (1, "I'm in! This is exactly the bridge between CS and Psychology I was looking for."),
            (7, "I'm in! Architecture students care a lot about user experience of spaces too."),
            (9, "I'm in! Great initiative Fatima."),
            (13, "I'm in! 🙋"),
            (5, "Wonderful! Registration is now at 4/25. Lots of space still — bring friends!"),
        ],
    },
]


def seed():
    with app.app_context():
        MOCK_PASSWORD = app.config.get('MOCK_PASSWORD') or 'Mock@123'
        print("Clearing non-admin data...")
        # Delete in dependency order
        for model in [CommunityLike, CommunityComment, CommunityPost,
                      StudyGroupMessage, StudyGroupMember, StudyGroup,
                      UserBadge, Endorsement, Feedback,
                      Application, ProjectMember, ProjectSkill, ProjectTag, Project,
                      UserCourse, UserInterest, UserSkill, ChatbotSession, Notification]:
            db.session.execute(model.__table__.delete())
        # Delete non-admin users
        db.session.execute(
            User.__table__.delete().where(User.__table__.c.role != 'admin')
        )
        db.session.commit()
        print("Cleared.")

        # ── Create students ───────────────────────────────────────────────
        users = []
        for i, (first, last, email, dept, bio, skills, interests, courses) in enumerate(STUDENTS):
            u = User(first_name=first, last_name=last, email=email,
                     department=dept, bio=bio, role="student")
            u.set_password(MOCK_PASSWORD)
            db.session.add(u)
            db.session.flush()
            for s in skills:
                db.session.add(UserSkill(user_id=u.id, skill=s))
            for tag in interests[:5]:  # max 5
                db.session.add(UserInterest(user_id=u.id, tag=tag))
            for c in courses:
                db.session.add(UserCourse(user_id=u.id, course=c))
            users.append(u)
            print(f"  Created user: {first} {last}")
        db.session.commit()

        # ── Create projects ───────────────────────────────────────────────
        projects = []
        for pd in PROJECTS:
            owner = users[pd["owner_idx"]]
            created = datetime.utcnow() - timedelta(days=pd["days_ago"])
            completed_at = created + timedelta(days=20) if pd["status"] == "completed" else None
            p = Project(
                title=pd["title"],
                description=pd["description"],
                owner_id=owner.id,
                course=pd.get("course"),
                team_size=pd["team_size"],
                status=pd["status"],
                created_at=created,
                completed_at=completed_at,
            )
            db.session.add(p)
            db.session.flush()
            for tag in pd["tags"]:
                db.session.add(ProjectTag(project_id=p.id, tag=tag))
            for sk in pd["skills"]:
                db.session.add(ProjectSkill(project_id=p.id, skill=sk))
            # Owner is always a member
            db.session.add(ProjectMember(project_id=p.id, user_id=owner.id, role="owner", joined_at=created))
            projects.append(p)
            print(f"  Created project: {pd['title'][:50]}")
        db.session.commit()

        # ── Add some members and applications ─────────────────────────────
        # Project 0 (Smart Campus): Nikola applied + joined, Haris applied
        db.session.add(ProjectMember(project_id=projects[0].id, user_id=users[4].id,
                                     joined_at=datetime.utcnow()-timedelta(days=3)))
        db.session.add(Application(project_id=projects[0].id, applicant_id=users[8].id,
                                   status="pending", created_at=datetime.utcnow()-timedelta(days=1)))

        # Project 1 (ML Predictor): Damir joined, Mia applied
        db.session.add(ProjectMember(project_id=projects[1].id, user_id=users[6].id,
                                     joined_at=datetime.utcnow()-timedelta(days=5)))
        db.session.add(Application(project_id=projects[1].id, applicant_id=users[13].id,
                                   status="pending", created_at=datetime.utcnow()-timedelta(days=2)))

        # Project 2 (Marketplace): Amir joined
        db.session.add(ProjectMember(project_id=projects[2].id, user_id=users[0].id,
                                     joined_at=datetime.utcnow()-timedelta(days=8)))

        # Completed projects (8, 9) — add members
        db.session.add(ProjectMember(project_id=projects[7].id, user_id=users[2].id,
                                     joined_at=datetime.utcnow()-timedelta(days=58)))
        db.session.add(ProjectMember(project_id=projects[8].id, user_id=users[6].id,
                                     joined_at=datetime.utcnow()-timedelta(days=88)))
        db.session.add(ProjectMember(project_id=projects[8].id, user_id=users[4].id,
                                     joined_at=datetime.utcnow()-timedelta(days=87)))
        db.session.commit()

        # ── Feedback (only for completed projects) ────────────────────────
        # Project 8 completed: Amir rates Damir and Nikola; they rate back
        feedbacks = [
            (users[6].id, users[0].id, projects[8].id, 5, "Amir is an exceptional collaborator. His API design skills are top-notch and he always delivers on time."),
            (users[4].id, users[0].id, projects[8].id, 5, "One of the best teammates I've had. Very communicative and technically strong."),
            (users[0].id, users[6].id, projects[8].id, 4, "Damir's frontend work was excellent. Creative and detail-oriented. Would work with him again!"),
            (users[0].id, users[4].id, projects[8].id, 5, "Nikola is an ML wizard. His model accuracy improvements saved the whole project."),
        ]
        for giver_id, receiver_id, proj, rating, comment in feedbacks:
            db.session.add(Feedback(project_id=proj, giver_id=giver_id,
                                    receiver_id=receiver_id, rating=rating, comment=comment,
                                    created_at=datetime.utcnow()-timedelta(days=15)))
        db.session.commit()

        # ── Endorsements ──────────────────────────────────────────────────
        endorsements = [
            (users[6].id, users[0].id, "Flask"),
            (users[4].id, users[0].id, "PostgreSQL"),
            (users[0].id, users[6].id, "React"),
            (users[0].id, users[6].id, "Node.js"),
            (users[0].id, users[4].id, "Machine Learning"),
            (users[0].id, users[4].id, "Python"),
            (users[6].id, users[4].id, "TensorFlow"),
            (users[1].id, users[9].id, "Figma"),
            (users[9].id, users[1].id, "React"),
        ]
        for giver_id, receiver_id, skill in endorsements:
            db.session.add(Endorsement(giver_id=giver_id, receiver_id=receiver_id, skill=skill))
        db.session.commit()

        # ── Badges ────────────────────────────────────────────────────────
        badges = Badge.query.all()
        if badges:
            first_step = next((b for b in badges if b.name == "first step"), badges[0])
            for u in [users[0], users[4], users[6], users[12]]:
                db.session.add(UserBadge(user_id=u.id, badge_id=first_step.id))
        db.session.commit()

        # ── Study Groups ──────────────────────────────────────────────────
        for sg_data in STUDY_GROUPS:
            creator = users[sg_data["creator_idx"]]
            sg = StudyGroup(
                name=sg_data["name"],
                topic=sg_data["topic"],
                description=sg_data["description"],
                creator_id=creator.id,
                created_at=datetime.utcnow() - timedelta(days=random.randint(10, 40)),
            )
            db.session.add(sg)
            db.session.flush()
            # Add creator as admin member
            db.session.add(StudyGroupMember(group_id=sg.id, user_id=creator.id, role="admin"))
            # Add other members
            for mi in sg_data["member_idxs"]:
                db.session.add(StudyGroupMember(group_id=sg.id, user_id=users[mi].id))
            # Add messages
            base_time = datetime.utcnow() - timedelta(hours=len(sg_data["messages"]) * 2)
            for j, (author_idx, body) in enumerate(sg_data["messages"]):
                msg_time = base_time + timedelta(hours=j * 2 + random.randint(0, 30))
                db.session.add(StudyGroupMessage(
                    group_id=sg.id,
                    author_id=users[author_idx].id,
                    body=body,
                    created_at=msg_time,
                ))
            print(f"  Created study group: {sg_data['name']}")
        db.session.commit()

        # ── Community Posts ───────────────────────────────────────────────
        for cp_data in COMMUNITY_POSTS:
            author = users[cp_data["author_idx"]]
            created = datetime.utcnow() - timedelta(days=cp_data["days_ago"])
            post = CommunityPost(
                author_id=author.id,
                title=cp_data.get("title"),
                body=cp_data["body"],
                created_at=created,
            )
            db.session.add(post)
            db.session.flush()
            # Likes
            for li in cp_data.get("likes_idxs", []):
                db.session.add(CommunityLike(post_id=post.id, user_id=users[li].id))
            # Comments
            for j, (commenter_idx, comment_body) in enumerate(cp_data.get("comments", [])):
                db.session.add(CommunityComment(
                    post_id=post.id,
                    author_id=users[commenter_idx].id,
                    body=comment_body,
                    created_at=created + timedelta(hours=j + 1),
                ))
            print(f"  Created post: {cp_data.get('title', cp_data['body'][:40])}")
        db.session.commit()

        # ── Notifications ─────────────────────────────────────────────────
        db.session.add(Notification(
            user_id=users[1].id,
            message="Your application to 'IUS Smart Campus App' was accepted!",
            link=f"/project/{projects[0].id}",
            type="accepted",
            created_at=datetime.utcnow() - timedelta(hours=3),
        ))
        db.session.add(Notification(
            user_id=users[0].id,
            message="Nikola Petrović applied to join 'IUS Study Group Finder'",
            link="/my-projects",
            type="apply",
            created_at=datetime.utcnow() - timedelta(hours=10),
        ))
        db.session.commit()

        print("\nMock data seeded successfully!")
        print(f"  Users:          {User.query.filter(User.role!='admin').count()}")
        print(f"  Projects:       {Project.query.count()}")
        print(f"  Study Groups:   {StudyGroup.query.count()}")
        print(f"  Community Posts:{CommunityPost.query.count()}")
        print(f"\nAll mock users password: {MOCK_PASSWORD}")
        print("Sample logins:")
        for u in users[:4]:
            print(f"  {u.email} / {MOCK_PASSWORD}")


if __name__ == "__main__":
    seed()
