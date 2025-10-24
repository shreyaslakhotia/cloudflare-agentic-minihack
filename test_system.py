"""
Simple test script to validate the system is working.
Run this after starting the API server.
"""
import time
import requests
import json

API_BASE = "http://localhost:8000"


def test_health():
    """Test the health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{API_BASE}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("✅ Health check passed")


def test_submit():
    """Test submitting an analysis."""
    print("\n=== Testing Submit Endpoint ===")
    
    data = {
        "user_prompt": "I want to transition into a senior software engineering role at a cloud company",
        "salary_min": 150000,
        "salary_max": 250000,
        "locations": "San Francisco,Austin",
        "industries": "cloud,technology",
        "roles": "Senior Software Engineer,Principal Engineer",
        "interests": "Python,AWS,Kubernetes",
        "remote_ok": True
    }
    
    # Create a simple text resume
    resume_content = """
John Doe
Software Engineer

SKILLS
Python, JavaScript, React, AWS, Docker, Kubernetes, PostgreSQL, Redis

EDUCATION
B.S. Computer Science, Stanford University, 2020

EXPERIENCE
Senior Software Engineer, Tech Corp, 2020-2024
- Built cloud infrastructure serving 1M+ users
- Led team of 5 engineers
- Deployed microservices on Kubernetes

Software Engineer, Startup Inc, 2018-2020
- Developed REST APIs in Python/Django
- Integrated AWS services (S3, Lambda, RDS)
"""
    
    files = {
        "resume": ("resume.txt", resume_content, "text/plain")
    }
    
    response = requests.post(f"{API_BASE}/submit", data=data, files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    
    submission_id = response.json()["submission_id"]
    print(f"✅ Submit passed - Submission ID: {submission_id}")
    return submission_id


def test_status(submission_id):
    """Test checking status."""
    print("\n=== Testing Status Endpoint ===")
    
    max_wait = 120  # 2 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(f"{API_BASE}/status/{submission_id}")
        print(f"Status Code: {response.status_code}")
        
        data = response.json()
        print(f"State: {data['state']} | Progress: {data['progress']}% | Message: {data['message']}")
        
        if data["state"] == "completed":
            print("✅ Analysis completed!")
            return True
        elif data["state"] == "failed":
            print("❌ Analysis failed!")
            return False
        
        time.sleep(5)
    
    print("⚠️ Timeout waiting for completion")
    return False


def test_report(submission_id):
    """Test retrieving the report."""
    print("\n=== Testing Report Endpoint ===")
    
    response = requests.get(f"{API_BASE}/report/{submission_id}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        report = data.get("report", {})
        
        print(f"\n📊 Report Summary:")
        print(f"  - Recommendations: {len(report.get('recommendations', []))}")
        print(f"  - Match Scores: {len(report.get('match_scores', []))}")
        print(f"  - Salary Range: ${report.get('salary_insights', {}).get('range', {}).get('min', 0):,} - ${report.get('salary_insights', {}).get('range', {}).get('max', 0):,}")
        print(f"  - Citations: {len(report.get('citations', []))}")
        print(f"  - Elapsed: {data.get('elapsed_seconds', 0):.2f}s")
        
        if report.get('recommendations'):
            print(f"\n🎯 Top Recommendation:")
            rec = report['recommendations'][0]
            print(f"  {rec.get('title', 'N/A')} at {rec.get('company', 'N/A')}")
            print(f"  Rationale: {rec.get('rationale', 'N/A')[:100]}...")
        
        print("✅ Report retrieved successfully")
        return True
    else:
        print(f"❌ Failed to retrieve report: {response.text}")
        return False


def test_chat(submission_id):
    """Test the chat endpoint."""
    print("\n=== Testing Chat Endpoint ===")
    
    questions = [
        "What are my strongest skills for these roles?",
        "What if I learned Go programming? How would that help?",
        "Which location would you recommend based on cost of living?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        
        response = requests.post(
            f"{API_BASE}/chat/{submission_id}",
            json={"message": question}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Answer: {data.get('content', '')[:200]}...")
            print(f"Citations: {len(data.get('citations', []))} sources")
        else:
            print(f"❌ Chat failed: {response.text}")
            return False
    
    print("✅ Chat test passed")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Career Advice Platform - System Test")
    print("=" * 60)
    
    try:
        # Test 1: Health
        test_health()
        
        # Test 2: Submit
        submission_id = test_submit()
        
        # Test 3: Status (wait for completion)
        if test_status(submission_id):
            # Test 4: Report
            test_report(submission_id)
            
            # Test 5: Chat
            test_chat(submission_id)
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
