"""
The interest taxonomy — a single source of truth used by registration and
edit-profile so both stay in sync. Grouped by field so a student from any
department can find themselves, not just CS majors.
"""

INTEREST_CATEGORIES = [
    {"name": "Software & Computer Science", "tags": [
        "Web Development", "Frontend", "Backend", "Full-Stack", "Mobile Development",
        "Game Development", "UI/UX Design", "Databases", "Cloud Computing", "DevOps",
        "Cybersecurity", "Networks", "Blockchain", "IoT", "AR / VR", "Embedded Systems",
    ]},
    {"name": "AI & Data", "tags": [
        "Machine Learning", "Deep Learning", "Data Science", "Data Analysis",
        "Artificial Intelligence", "Computer Vision", "Natural Language Processing",
        "Big Data", "Business Analytics", "Statistics",
    ]},
    {"name": "Engineering", "tags": [
        "Mechanical Engineering", "Electrical Engineering", "Civil Engineering",
        "Chemical Engineering", "Mechatronics", "Aerospace", "Robotics",
        "Control Systems", "Signal Processing", "Materials Science",
        "Renewable Energy", "CAD / 3D Modeling",
    ]},
    {"name": "Mathematics", "tags": [
        "Pure Mathematics", "Applied Mathematics", "Probability", "Optimization",
        "Cryptography", "Actuarial Science",
    ]},
    {"name": "Natural Sciences", "tags": [
        "Physics", "Chemistry", "Biology", "Biotechnology", "Genetics", "Neuroscience",
        "Environmental Science", "Astronomy", "Geology", "Ecology",
    ]},
    {"name": "Health & Medicine", "tags": [
        "Medicine", "Nursing", "Public Health", "Pharmacology", "Nutrition",
        "Physiotherapy", "Biomedical Engineering", "Mental Health", "Sports Science",
    ]},
    {"name": "Psychology & Social Sciences", "tags": [
        "Clinical Psychology", "Cognitive Science", "Developmental Psychology",
        "Social Psychology", "Counseling", "Sociology", "Anthropology",
        "Political Science", "International Relations", "Research Methods",
    ]},
    {"name": "Business & Economics", "tags": [
        "Entrepreneurship", "Marketing", "Finance", "Accounting", "Management",
        "Economics", "Supply Chain", "Human Resources", "Product Management",
        "E-commerce", "Consulting",
    ]},
    {"name": "Law & Policy", "tags": [
        "Law", "Human Rights", "Criminal Justice", "Public Policy", "Ethics",
        "Political Theory",
    ]},
    {"name": "Arts & Design", "tags": [
        "Graphic Design", "Illustration", "Photography", "Film & Video", "Music",
        "Animation", "Architecture", "Fashion Design", "Interior Design",
        "Creative Writing",
    ]},
    {"name": "Humanities & Languages", "tags": [
        "Literature", "History", "Philosophy", "Linguistics", "Languages",
        "Translation", "Cultural Studies", "Religious Studies",
    ]},
    {"name": "Media & Communication", "tags": [
        "Journalism", "Content Creation", "Digital Marketing", "Public Relations",
        "Social Media", "Broadcasting", "Podcasting",
    ]},
    {"name": "Education", "tags": [
        "Teaching", "Curriculum Design", "E-Learning", "Educational Psychology",
        "Special Education",
    ]},
]

# Flat list of every valid interest (handy for validation / lookups).
ALL_INTERESTS = [t for cat in INTEREST_CATEGORIES for t in cat["tags"]]
