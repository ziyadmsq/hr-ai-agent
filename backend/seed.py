"""Seed script for HR SaaS platform.

Populates the database with realistic HR data for testing:
- 1 organization (Acme Corporation)
- 10 users with matching employees
- 20 leave balances (annual + sick per employee)
- ~10 leave requests (mix of pending, approved, rejected)
- 5 HR policy documents with RAG ingestion
- 3 alert configurations

Usage:
    cd backend && python seed.py
    # Or inside Docker:
    docker-compose exec backend python seed.py
"""

import asyncio
import sys
import os
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

# Ensure the backend directory is on the path when running from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.models import (
    AlertConfig,
    Employee,
    LeaveBalance,
    LeaveRequest,
    Organization,
    PolicyDocument,
    User,
)
from app.services.rag.pipeline import RAGPipeline


# ── Seed Data Definitions ────────────────────────────────────────────────────

USERS_DATA = [
    {"role": "admin", "name": "Sarah Chen", "email": "sarah.chen@acme.com",
     "dept": "Executive", "position": "CEO", "code": "EMP001",
     "hire": date(2024, 1, 15)},
    {"role": "hr_manager", "name": "Michael Roberts", "email": "michael.roberts@acme.com",
     "dept": "Human Resources", "position": "HR Director", "code": "EMP002",
     "hire": date(2024, 2, 1)},
    {"role": "employee", "name": "Emily Johnson", "email": "emily.johnson@acme.com",
     "dept": "Engineering", "position": "Senior Developer", "code": "EMP003",
     "hire": date(2024, 3, 10)},
    {"role": "employee", "name": "James Wilson", "email": "james.wilson@acme.com",
     "dept": "Engineering", "position": "DevOps Engineer", "code": "EMP004",
     "hire": date(2024, 4, 22)},
    {"role": "employee", "name": "Priya Patel", "email": "priya.patel@acme.com",
     "dept": "Marketing", "position": "Marketing Manager", "code": "EMP005",
     "hire": date(2024, 6, 1)},
    {"role": "employee", "name": "David Kim", "email": "david.kim@acme.com",
     "dept": "Finance", "position": "Financial Analyst", "code": "EMP006",
     "hire": date(2024, 7, 15)},
    {"role": "employee", "name": "Maria Garcia", "email": "maria.garcia@acme.com",
     "dept": "Sales", "position": "Account Executive", "code": "EMP007",
     "hire": date(2024, 9, 1)},
    {"role": "employee", "name": "Alex Thompson", "email": "alex.thompson@acme.com",
     "dept": "Engineering", "position": "Junior Developer", "code": "EMP008",
     "hire": date(2024, 11, 1)},
    {"role": "employee", "name": "Lisa Wang", "email": "lisa.wang@acme.com",
     "dept": "Human Resources", "position": "HR Specialist", "code": "EMP009",
     "hire": date(2025, 1, 10)},
    {"role": "employee", "name": "Robert Brown", "email": "robert.brown@acme.com",
     "dept": "Operations", "position": "Operations Manager", "code": "EMP010",
     "hire": date(2025, 3, 1)},
]

# Leave balance used_days per employee index (annual, sick)
LEAVE_USED = [
    (5.0, 2.0), (3.0, 1.0), (8.0, 3.0), (4.0, 0.0), (6.0, 2.0),
    (2.0, 1.0), (7.0, 4.0), (1.0, 0.0), (3.0, 1.0), (4.0, 2.0),
]

ALERT_CONFIGS = [
    {
        "name": "Excessive Absence Alert",
        "trigger_type": "absence",
        "trigger_config": {"threshold_days": 5, "period_days": 30,
                           "leave_types": ["sick", "unpaid"]},
        "action_template": ("Employee {employee_name} has been absent for "
                            "{absence_days} days in the last 30 days. "
                            "Please review and take appropriate action."),
    },
    {
        "name": "Contract Expiry Reminder",
        "trigger_type": "contract_expiry",
        "trigger_config": {"days_before": 30,
                           "notify_roles": ["hr_manager", "admin"]},
        "action_template": ("Reminder: {employee_name}'s contract expires on "
                            "{expiry_date}. Please initiate the renewal process."),
    },
    {
        "name": "Probation Review Alert",
        "trigger_type": "probation_end",
        "trigger_config": {"days_before": 14, "probation_months": 6},
        "action_template": ("Employee {employee_name}'s probation period ends on "
                            "{probation_end_date}. Schedule a performance review."),
    },
]


# ── Policy Content ────────────────────────────────────────────────────────────

ANNUAL_LEAVE_POLICY = """\
Annual Leave Policy — Acme Corporation

1. Purpose and Scope
This Annual Leave Policy outlines the guidelines and procedures for requesting, approving, and managing annual leave (vacation) for all employees of Acme Corporation. This policy applies to all full-time and part-time employees who have completed their probationary period. The purpose of this policy is to ensure that all employees have adequate time for rest and personal activities while maintaining business continuity and operational efficiency across all departments.

2. Annual Leave Entitlement
All full-time employees are entitled to 21 working days of paid annual leave per calendar year. Part-time employees receive a pro-rated entitlement based on their contracted hours. New employees who join mid-year will receive a pro-rated entitlement for the remainder of the calendar year. Leave entitlement is calculated from January 1 to December 31 each year. Employees in their first year of service will accrue leave at a rate of 1.75 days per month of service.

3. Requesting Annual Leave
Employees must submit leave requests through the HR management system at least two weeks in advance for leave periods of three days or more. For leave of one to two days, at least five business days' notice is required. Requests are subject to approval by the employee's direct manager and the HR department. The company reserves the right to decline leave requests during critical business periods, including month-end closing, annual audits, and major project deadlines. Employees are encouraged to plan their leave well in advance to avoid conflicts with team schedules.

4. Carry-Over and Expiration
Employees may carry over a maximum of 5 unused annual leave days to the following calendar year. Carried-over days must be used by March 31 of the following year, after which they will expire. In exceptional circumstances, the HR Director may approve extensions to the carry-over deadline on a case-by-case basis. The company does not provide monetary compensation for unused annual leave except upon termination of employment.

5. Leave During Probation
Employees in their probationary period (first 6 months) may request annual leave, but it will be limited to a maximum of 3 days during this period. Any leave taken during probation must be approved by both the direct manager and the HR department. Probationary employees who take extended leave may have their probation period extended accordingly.

6. Public Holidays and Annual Leave
If a public holiday falls within an approved annual leave period, that day will not be counted against the employee's annual leave balance. The company observes all national public holidays as published by the government each year. A list of observed public holidays will be communicated to all employees at the beginning of each calendar year.

7. Cancellation and Changes
Employees who need to cancel or modify approved leave must notify their manager and HR at least three business days before the original leave start date. Late cancellations may not be accepted if replacement arrangements have already been made. Repeated cancellations may result in future leave requests being subject to additional review."""

REMOTE_WORK_POLICY = """\
Remote Work Policy — Acme Corporation

1. Purpose and Scope
This Remote Work Policy establishes the guidelines and expectations for employees who work remotely, either on a regular basis or occasionally. This policy applies to all employees whose roles have been approved for remote work by their department head and the HR department. The goal is to provide flexibility while maintaining productivity, collaboration, and security standards.

2. Eligibility and Approval
Remote work is available to employees who have completed their probationary period and whose role can be effectively performed outside the office. Employees must submit a remote work request through the HR system, specifying the proposed schedule (full-time remote, hybrid, or occasional). Approval is at the discretion of the department head and must be reviewed by HR. Approval can be revoked at any time if performance standards are not met or business needs change.

3. Work Schedule and Availability
Remote employees must maintain their regular working hours (9:00 AM to 6:00 PM local time) unless alternative arrangements have been approved in writing. Employees must be available via company communication tools (Slack, email, video conferencing) during core business hours (10:00 AM to 4:00 PM). Remote employees are expected to attend all scheduled meetings via video conference with cameras on. Any changes to the agreed work schedule must be communicated to the manager at least 24 hours in advance.

4. Workspace Requirements
Remote employees must maintain a dedicated workspace that is quiet, secure, and free from distractions. The workspace must have reliable high-speed internet access (minimum 25 Mbps download speed). Employees are responsible for ensuring their home office meets basic ergonomic standards. The company may provide a one-time home office setup allowance of up to $500 for approved remote workers, subject to receipt submission and HR approval.

5. Equipment and Technology
The company will provide necessary equipment including a laptop, monitor, keyboard, and mouse for approved remote workers. All company equipment must be used in accordance with the IT Security Policy. Employees must use the company VPN when accessing internal systems. Personal devices may only be used for work purposes if they comply with the company's Bring Your Own Device (BYOD) policy and have been registered with IT.

6. Data Security and Confidentiality
Remote employees must adhere to all data protection and information security policies. Confidential documents must not be printed at home unless absolutely necessary, and must be securely destroyed after use. Screen locks must be activated when stepping away from the workstation. Employees must not use public Wi-Fi networks for work purposes without using the company VPN.

7. Performance and Accountability
Remote employees will be evaluated using the same performance criteria and KPIs as office-based employees. Managers will conduct regular check-ins (at least weekly) with remote team members. Remote employees must track their work hours and submit timesheets as required. Failure to meet performance standards while working remotely may result in a return-to-office requirement."""

CODE_OF_CONDUCT_POLICY = """\
Code of Conduct — Acme Corporation

1. Purpose and Scope
This Code of Conduct sets forth the ethical standards and behavioral expectations for all employees, contractors, and representatives of Acme Corporation. Every individual associated with our company is expected to uphold these standards in all business activities, interactions with colleagues, clients, and external stakeholders. Violations of this code may result in disciplinary action, up to and including termination of employment.

2. Professional Behavior
All employees are expected to conduct themselves in a professional manner at all times. This includes treating colleagues, clients, and business partners with respect and courtesy. Employees should communicate openly and honestly, and be willing to listen to different perspectives. Professional disagreements should be resolved through constructive dialogue and appropriate escalation channels, never through personal attacks or intimidation.

3. Integrity and Honesty
Employees must act with integrity in all business dealings. This includes being truthful in communications, accurate in reporting, and transparent in decision-making. Falsifying records, reports, or expense claims is strictly prohibited and will result in immediate termination. Employees who become aware of dishonest behavior by others have a duty to report it through the appropriate channels.

4. Conflict of Interest
Employees must avoid situations where personal interests conflict, or appear to conflict, with the interests of the company. Any potential conflict of interest must be disclosed to the employee's manager and the HR department immediately. Employees may not accept gifts or entertainment from vendors, clients, or business partners valued at more than $50 without prior written approval from their department head.

5. Confidentiality and Intellectual Property
Employees must protect confidential company information, trade secrets, and intellectual property at all times. This obligation continues even after employment ends. Employees must not disclose proprietary information to unauthorized individuals, whether inside or outside the company. All work products created during employment belong to Acme Corporation as outlined in the employment agreement.

6. Use of Company Resources
Company resources, including equipment, software, and facilities, are provided for business purposes. Limited personal use of company resources is permitted, provided it does not interfere with work duties or violate any company policy. Employees must not use company resources for illegal activities, personal commercial ventures, or activities that could damage the company's reputation.

7. Compliance with Laws and Regulations
All employees must comply with applicable local, state, and federal laws and regulations in the conduct of company business. This includes but is not limited to labor laws, anti-corruption laws, data protection regulations, and industry-specific regulations. Employees who are unsure about the legality of an action should consult with the Legal department before proceeding.

8. Reporting Violations
Employees who witness or become aware of violations of this Code of Conduct have a duty to report them. Reports can be made to the employee's direct manager, the HR department, or through the anonymous ethics hotline. The company strictly prohibits retaliation against anyone who reports a violation in good faith. All reports will be investigated promptly and confidentially."""

ANTI_HARASSMENT_POLICY = """\
Anti-Harassment Policy — Acme Corporation

1. Purpose and Commitment
Acme Corporation is committed to maintaining a work environment free from harassment, discrimination, and bullying. This Anti-Harassment Policy applies to all employees, contractors, interns, and visitors in all company locations, at company events, and in any situation related to company business, including remote work environments and digital communications.

2. Definition of Harassment
Harassment includes any unwelcome conduct based on race, color, religion, sex, national origin, age, disability, genetic information, sexual orientation, gender identity, or any other characteristic protected by law. Harassment can take many forms including verbal abuse, offensive jokes, slurs, intimidation, threatening behavior, physical assault, unwelcome physical contact, visual displays of offensive material, and cyberbullying through electronic communications.

3. Sexual Harassment
Sexual harassment specifically includes unwelcome sexual advances, requests for sexual favors, and other verbal or physical conduct of a sexual nature. This includes quid pro quo harassment, where employment decisions are based on submission to or rejection of sexual advances, and hostile work environment harassment, where unwelcome sexual conduct unreasonably interferes with an individual's work performance or creates an intimidating, hostile, or offensive work environment.

4. Bullying and Intimidation
Workplace bullying is repeated, unreasonable behavior directed toward an employee or group of employees that creates a risk to health and safety. This includes verbal abuse, spreading rumors, social isolation, assigning unreasonable workloads, setting impossible deadlines, and persistent criticism without constructive purpose. A single incident of sufficiently serious conduct may also constitute bullying.

5. Reporting Procedures
Any employee who experiences or witnesses harassment should report it immediately through one of the following channels: their direct manager (unless the manager is involved), the HR department, the anonymous ethics hotline available 24/7, or by email to ethics@acmecorp.com. The company encourages early reporting of concerns so that prompt and appropriate action can be taken. Employees are not required to confront the harasser before reporting.

6. Investigation Process
All complaints will be investigated promptly, thoroughly, and as confidentially as possible. The investigation will typically include interviews with the complainant, the accused, and any relevant witnesses. The HR department will lead all investigations, with assistance from the Legal department when necessary. Both parties will be informed of the outcome of the investigation. The typical investigation timeline is 10 to 15 business days from the date of the complaint.

7. Consequences and Disciplinary Action
Employees found to have engaged in harassment will face disciplinary action appropriate to the severity of the offense. Disciplinary measures may include verbal or written warning, mandatory training, suspension without pay, demotion, transfer, or termination of employment. In cases involving criminal conduct, the matter will be referred to law enforcement. The company reserves the right to take interim protective measures during the investigation period.

8. Retaliation Prohibition
Retaliation against any employee who reports harassment, participates in an investigation, or opposes discriminatory practices is strictly prohibited. Retaliation includes adverse employment actions such as termination, demotion, unfavorable schedule changes, or hostile treatment. Any employee found to have engaged in retaliation will be subject to disciplinary action, up to and including termination.

9. Training and Prevention
All employees are required to complete anti-harassment training within 30 days of hire and annually thereafter. Managers and supervisors receive additional training on recognizing, preventing, and responding to harassment. The company will regularly review and update its anti-harassment policies and procedures to ensure they remain effective and compliant with applicable laws."""

DATA_PRIVACY_POLICY = """\
Data Privacy & Security Policy — Acme Corporation

1. Purpose and Scope
This Data Privacy and Security Policy establishes the framework for protecting personal data, sensitive business information, and digital assets at Acme Corporation. This policy applies to all employees, contractors, and third parties who access, process, or handle company data. Compliance with this policy is mandatory and essential for maintaining customer trust and meeting legal obligations.

2. Data Classification
All company data is classified into four categories: Public (freely shareable information), Internal (for employee use only), Confidential (restricted to specific teams or roles), and Highly Confidential (restricted to named individuals only). All data must be labeled with its classification level. When in doubt about classification, employees should treat data as Confidential until confirmed otherwise by the data owner.

3. Personal Data Protection
The company collects and processes personal data of employees, customers, and business partners only for legitimate business purposes. Personal data includes names, addresses, contact information, identification numbers, financial information, and any other data that can identify an individual. All personal data processing must comply with applicable data protection laws, including GDPR where applicable.

4. Data Collection and Consent
Personal data may only be collected when there is a lawful basis for processing. Where consent is required, it must be freely given, specific, informed, and unambiguous. Employees must ensure that data subjects are informed about what data is collected, why it is collected, how it will be used, and how long it will be retained. Privacy notices must be provided at the point of data collection.

5. Data Storage and Retention
All company data must be stored on approved company systems and platforms. Data must not be stored on personal devices, unauthorized cloud services, or removable media without explicit written approval from IT Security. The company maintains a data retention schedule that specifies how long each type of data should be kept. Data must be securely deleted or anonymized when it is no longer needed for its original purpose.

6. Access Control
Access to data must follow the principle of least privilege — employees should only have access to data necessary for their job functions. Access rights must be reviewed quarterly by department heads and IT Security. Multi-factor authentication is required for all systems containing Confidential or Highly Confidential data. Shared accounts and passwords are strictly prohibited. Employees must never share their login credentials with others.

7. Incident Response
Any suspected data breach or security incident must be reported to the IT Security team immediately, and no later than 24 hours after discovery. The IT Security team will assess the severity of the incident and activate the appropriate response plan. Where required by law, affected individuals and regulatory authorities will be notified within the prescribed timeframes. All incidents will be documented, investigated, and followed up with corrective actions to prevent recurrence.

8. Employee Responsibilities
All employees are responsible for protecting the data they handle. This includes locking workstations when unattended, using strong passwords (minimum 12 characters with complexity requirements), not sharing sensitive information over unsecured channels, and reporting suspicious activities to IT Security. Employees must complete data protection training within 30 days of hire and annually thereafter.

9. Third-Party Data Sharing
Company data may only be shared with third parties when there is a legitimate business need and appropriate contractual protections are in place. All third-party data processors must sign a Data Processing Agreement before receiving any personal or confidential data. The company maintains a register of all third-party data processors, which is reviewed annually by the Legal and IT Security teams.

10. Enforcement and Penalties
Violations of this policy may result in disciplinary action, up to and including termination of employment. In cases of intentional or grossly negligent data breaches, the company may pursue legal action to recover damages. All employees are required to acknowledge and sign this policy upon hire and after each annual revision."""


POLICIES_DATA = [
    {"title": "Annual Leave Policy", "content": ANNUAL_LEAVE_POLICY, "category": "leave"},
    {"title": "Remote Work Policy", "content": REMOTE_WORK_POLICY, "category": "workplace"},
    {"title": "Code of Conduct", "content": CODE_OF_CONDUCT_POLICY, "category": "compliance"},
    {"title": "Anti-Harassment Policy", "content": ANTI_HARASSMENT_POLICY, "category": "compliance"},
    {"title": "Data Privacy & Security Policy", "content": DATA_PRIVACY_POLICY, "category": "security"},
]


# ── Leave Request Data ────────────────────────────────────────────────────────

def build_leave_requests(employees: list, admin_user_id, org_id):
    """Build leave request records. Called after employees are created."""
    return [
        # Pending requests (recent)
        {"emp_idx": 2, "type": "annual", "start": date(2026, 3, 10),
         "end": date(2026, 3, 14), "status": "pending",
         "reason": "Family vacation to Hawaii"},
        {"emp_idx": 4, "type": "annual", "start": date(2026, 3, 17),
         "end": date(2026, 3, 21), "status": "pending",
         "reason": "Attending a marketing conference in New York"},
        {"emp_idx": 7, "type": "sick", "start": date(2026, 2, 20),
         "end": date(2026, 2, 21), "status": "pending",
         "reason": "Dental surgery and recovery"},
        {"emp_idx": 9, "type": "annual", "start": date(2026, 4, 1),
         "end": date(2026, 4, 4), "status": "pending",
         "reason": "Moving to a new apartment"},
        # Approved requests (past dates)
        {"emp_idx": 0, "type": "annual", "start": date(2026, 1, 6),
         "end": date(2026, 1, 10), "status": "approved",
         "reason": "New Year extended holiday", "approved": True},
        {"emp_idx": 3, "type": "annual", "start": date(2026, 1, 20),
         "end": date(2026, 1, 24), "status": "approved",
         "reason": "Visiting family abroad", "approved": True},
        {"emp_idx": 5, "type": "sick", "start": date(2026, 2, 3),
         "end": date(2026, 2, 4), "status": "approved",
         "reason": "Flu and fever", "approved": True},
        {"emp_idx": 6, "type": "annual", "start": date(2026, 2, 10),
         "end": date(2026, 2, 14), "status": "approved",
         "reason": "Wedding anniversary trip", "approved": True},
        # Rejected requests
        {"emp_idx": 8, "type": "annual", "start": date(2026, 2, 16),
         "end": date(2026, 2, 27), "status": "rejected",
         "reason": "Extended personal travel"},
        {"emp_idx": 1, "type": "annual", "start": date(2026, 3, 2),
         "end": date(2026, 3, 6), "status": "rejected",
         "reason": "Personal time off — conflicted with payroll processing"},
    ]


# ── Main Seed Function ────────────────────────────────────────────────────────

async def seed():
    """Seed the database with realistic HR data."""
    async with async_session_factory() as db:
        # 1. Check idempotency
        result = await db.execute(
            select(Organization).where(Organization.slug == "acme-corp")
        )
        if result.scalar_one_or_none():
            print("⚠️  Organization 'acme-corp' already exists. Skipping seed.")
            print("   To re-seed, delete the organization first or reset the DB.")
            return

        print("🌱 Starting database seed...\n")

        # 2. Create Organization
        print("📦 Creating organization: Acme Corporation...")
        org = Organization(name="Acme Corporation", slug="acme-corp")
        db.add(org)
        await db.flush()
        org_id = org.id
        print(f"   ✅ Organization created (ID: {org_id})")

        # 3. Create Employees and Users
        print("\n👥 Creating employees and users...")
        hashed_pw = hash_password("password123")
        employees = []
        users = []

        for data in USERS_DATA:
            emp = Employee(
                organization_id=org_id,
                employee_code=data["code"],
                full_name=data["name"],
                email=data["email"],
                department=data["dept"],
                position=data["position"],
                hire_date=data["hire"],
                status="active",
            )
            db.add(emp)
            await db.flush()
            employees.append(emp)

            user = User(
                organization_id=org_id,
                email=data["email"],
                hashed_password=hashed_pw,
                role=data["role"],
                full_name=data["name"],
                employee_id=emp.id,
                is_active=True,
            )
            db.add(user)
            users.append(user)
            print(f"   ✅ {data['code']}: {data['name']} ({data['role']})")

        await db.flush()
        admin_user = users[0]  # Sarah Chen is the admin


        # 4. Create Leave Balances
        print("\n📊 Creating leave balances (year 2026)...")
        for i, emp in enumerate(employees):
            annual_used, sick_used = LEAVE_USED[i]
            annual_bal = LeaveBalance(
                organization_id=org_id,
                employee_id=emp.id,
                leave_type="annual",
                total_days=21.0,
                used_days=annual_used,
                year=2026,
            )
            sick_bal = LeaveBalance(
                organization_id=org_id,
                employee_id=emp.id,
                leave_type="sick",
                total_days=10.0,
                used_days=sick_used,
                year=2026,
            )
            db.add(annual_bal)
            db.add(sick_bal)
        await db.flush()
        print(f"   ✅ {len(employees) * 2} leave balances created")

        # 5. Create Leave Requests
        print("\n📝 Creating leave requests...")
        requests_data = build_leave_requests(employees, admin_user.id, org_id)
        leave_count = 0
        for req in requests_data:
            emp = employees[req["emp_idx"]]
            lr = LeaveRequest(
                organization_id=org_id,
                employee_id=emp.id,
                leave_type=req["type"],
                start_date=req["start"],
                end_date=req["end"],
                status=req["status"],
                reason=req["reason"],
                approved_by=admin_user.id if req.get("approved") else None,
            )
            db.add(lr)
            leave_count += 1
        await db.flush()
        print(f"   ✅ {leave_count} leave requests created")

        # 6. Create Policy Documents
        print("\n📋 Creating policy documents...")
        policies = []
        for pdata in POLICIES_DATA:
            policy = PolicyDocument(
                organization_id=org_id,
                title=pdata["title"],
                content=pdata["content"],
                category=pdata["category"],
                is_active=True,
            )
            db.add(policy)
            policies.append(policy)
        await db.flush()
        print(f"   ✅ {len(policies)} policies created")

        # 7. RAG Ingestion
        print("\n🤖 Ingesting policies into RAG system (generating embeddings)...")
        rag = RAGPipeline()
        total_chunks = 0
        for policy in policies:
            try:
                chunks = await rag.ingest(db, policy.id, org_id)
                total_chunks += chunks
                print(f"   ✅ {policy.title}: {chunks} chunks")
            except Exception as e:
                print(f"   ⚠️  {policy.title}: Failed - {e}")
        await db.flush()
        print(f"   📊 Total RAG chunks: {total_chunks}")

        # 8. Create Alert Configurations
        print("\n🔔 Creating alert configurations...")
        for adata in ALERT_CONFIGS:
            alert = AlertConfig(
                organization_id=org_id,
                name=adata["name"],
                trigger_type=adata["trigger_type"],
                trigger_config=adata["trigger_config"],
                action_template=adata["action_template"],
                is_active=True,
            )
            db.add(alert)
        await db.flush()
        print(f"   ✅ {len(ALERT_CONFIGS)} alert configurations created")

        # 9. Commit everything
        await db.commit()
        print("\n" + "=" * 60)
        print("✅ Database seeding complete!")
        print("=" * 60)
        print(f"\n📊 Summary:")
        print(f"   • 1 organization (Acme Corporation)")
        print(f"   • {len(users)} users with employee profiles")
        print(f"   • {len(employees) * 2} leave balances (annual + sick)")
        print(f"   • {leave_count} leave requests")
        print(f"   • {len(policies)} policy documents")
        print(f"   • {total_chunks} RAG chunks (with embeddings)")
        print(f"   • {len(ALERT_CONFIGS)} alert configurations")
        print(f"\n🔑 Login Credentials (all use password: password123):")
        print(f"   {'Email':<35} {'Role':<15} {'Name'}")
        print(f"   {'-'*35} {'-'*15} {'-'*20}")
        for data in USERS_DATA:
            print(f"   {data['email']:<35} {data['role']:<15} {data['name']}")
        print()


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("🌱 HR SaaS Seed Script")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key and api_key != "sk-placeholder":
        print(f"✅ OPENAI_API_KEY is set ({api_key[:12]}...)")
    else:
        print("⚠️  OPENAI_API_KEY not set — RAG will use mock embeddings")

    print()
    asyncio.run(seed())