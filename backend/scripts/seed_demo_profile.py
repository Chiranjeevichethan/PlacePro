# ============================================================
# PLACEPRO - PHASE 18 - DEMO PROFILE SEEDER (DEVELOPMENT TOOL)
# ============================================================
#
# Creates a verified, ML-complete demo student profile through the
# EXISTING Phase 10 service functions (verify_profile), stored in
# the normal data/profiles/ store. It does NOT add endpoints and
# does NOT bypass any business logic - it is a convenience seed
# for the Phase 18 dashboard (which has no auth yet).
#
# Usage:
#   python backend/scripts/seed_demo_profile.py
#       -> creates demo-student (verified, complete)
#
#   python backend/scripts/seed_demo_profile.py --assess-all
#       -> ALSO takes assessments for every supported skill by
#          answering with the server-side correct answers. This is
#          OPT-IN: it fabricates assessment evidence for demo
#          purposes and is clearly labeled as such below.
#
#   python backend/scripts/seed_demo_profile.py --id my-profile
#       -> choose the profile id (default: demo-student)
#
# ============================================================

import argparse
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

DEMO_PROFILE = {
    "profile_id": None,  # set by --id
    "personal": {
        "name": "Aarav Sharma",
        "email": "aarav.sharma@example.com",
        "phone": "+91 98765 43210",
        "location": "Bengaluru, India",
        "linkedin": "https://linkedin.com/in/aaravsharma",
        "github": "https://github.com/aaravsharma",
        "portfolio": None,
    },
    "education": {
        "degree": "B.Tech",
        "branch": "CSE",
        "college": "National Institute of Technology",
        "cgpa": 8.2,
        "graduation_year": 2026,
    },
    "skills": {
        "programming_languages": ["Python", "Java", "C++", "JavaScript"],
        "frameworks": ["React", "Flask"],
        "databases": ["SQL", "MySQL"],
        "cloud": ["AWS"],
        "ai_ml": ["Machine Learning"],
        "web_technologies": ["HTML", "CSS"],
        "tools": ["Git", "Linux", "Docker"],
        "other_skills": ["Communication"],
    },
    "experience": [
        {
            "company": "Campus Tech Club",
            "role": "Core Member",
            "duration": "2024 - Present",
            "technologies": ["Python", "Git"],
        }
    ],
    "internships": [
        {
            "company": "StartupLabs",
            "role": "Software Engineering Intern",
            "duration": "Summer 2025",
            "technologies": ["Python", "SQL", "React"],
        }
    ],
    "projects": [
        {
            "project_name": "Placement Readiness Dashboard",
            "description": "Web dashboard aggregating readiness, predictions and recommendations.",
            "technologies": ["Python", "React", "SQL"],
        },
        {
            "project_name": "ML Placement Predictor",
            "description": "End-to-end ML pipeline predicting placement probability.",
            "technologies": ["Python", "Machine Learning", "Pandas"],
        },
        {
            "project_name": "College Event Portal",
            "description": "Full-stack event registration and management portal.",
            "technologies": ["JavaScript", "HTML", "CSS", "MySQL"],
        },
    ],
    "certifications": [
        {
            "name": "AWS Cloud Practitioner",
            "issuer": "Amazon Web Services",
            "year": 2025,
        }
    ],
    "achievements": {
        "hackathons": ["Smart India Hackathon - Finalist"],
        "awards": ["Dean's List 2025"],
        "coding_achievements": ["LeetCode 250+ problems solved"],
    },
    "ml_inputs": {
        "college_tier": "Tier-2",
        "backlogs": 0,
        "coding_skills": 7.5,
        "dsa_score": 7.0,
        "aptitude_score": 80.0,
        "communication_skills": 7.0,
        "ml_knowledge": 6.0,
        "system_design": 5.0,
        "open_source_contributions": 2,
        "extracurriculars": 1,
    },
    "verified": False,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo student profile.")
    parser.add_argument("--id", default="demo-student", help="Profile id (default: demo-student)")
    parser.add_argument(
        "--assess-all",
        action="store_true",
        help="Also complete assessments for every supported skill "
             "(fabricated demo evidence - opt-in only).",
    )
    args = parser.parse_args()

    from app.services.profile_service import (
        ProfileNotFoundError,
        _load,
        verify_profile,
    )
    from app.services.question_bank import SUPPORTED_SKILLS

    profile_id = args.id
    profile = dict(DEMO_PROFILE)
    profile["profile_id"] = profile_id

    # Fresh start: remove any existing profile with this id.
    try:
        _load(profile_id)
        path = os.path.join(
            os.environ.get("PLACEPRO_PROFILES_DIR", os.path.join(PROJECT_ROOT, "data", "profiles")),
            f"{profile_id}.json",
        )
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed existing profile '{profile_id}'.")
    except ProfileNotFoundError:
        pass

    verified, completion = verify_profile(profile)

    print("=" * 60)
    print("DEMO PROFILE CREATED (development tool)")
    print("=" * 60)
    print(f"  profile_id      : {verified['profile_id']}")
    print(f"  name            : {verified['personal'].get('name')}")
    print(f"  verified        : {verified['verified']}")
    print(f"  profile_complete: {completion['profile_complete']}")
    if completion["missing_fields"]:
        print(f"  missing fields  : {completion['missing_fields']}")
    print("  store           : data/profiles/")

    if args.assess_all:
        from app.services.assessment_service import (
            start_assessment,
            submit_assessment,
        )

        print()
        print("Seeding assessments (DEMO evidence - fabricated on purpose)...")
        for skill in SUPPORTED_SKILLS:
            session = start_assessment(profile_id, skill)
            correct = {
                q["id"]: q["correct_answer"]
                for q in session["questions"]
            }
            result = submit_assessment(
                session["assessment_id"], profile_id, correct
            )
            print(f"  {skill:<18} score={result['skill_score']:5.1f}  level={result['level']}")
        print("  NOTE: these scores were produced by answering with the "
              "server-side answer key; they exist only to demo the UI.")

    print()
    print("Next: start the backend, then the frontend:")
    print("  uvicorn backend.app.main:app --reload")
    print("  cd frontend && npm run dev")
    print(f"  (frontend uses VITE_DEMO_PROFILE_ID={profile_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
