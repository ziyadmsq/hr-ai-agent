"""Agent tool definitions and execution for OpenAI function calling.

Each tool maps to an existing HR service or RAG pipeline operation.
"""

import json
import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest
from app.models.policy_document import PolicyDocument
from app.services.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

# ── OpenAI function/tool definitions ─────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_leave_balance",
            "description": "Check an employee's leave balance. Returns remaining days for each leave type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "leave_type": {
                        "type": "string",
                        "description": "Optional leave type filter (annual, sick, maternity, paternity, unpaid). If omitted, returns all types.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_leave_request",
            "description": "Submit a leave request on behalf of the employee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "leave_type": {"type": "string", "description": "Type of leave (annual, sick, maternity, paternity, unpaid)"},
                    "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                    "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                    "reason": {"type": "string", "description": "Reason for the leave request"},
                },
                "required": ["leave_type", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_info",
            "description": "Get the current employee's profile information (name, department, position, hire date, etc.).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policies",
            "description": "Search the organization's HR policy documents using semantic search. Use this to answer questions about company policies, benefits, rules, and procedures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query describing what policy information is needed"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_document",
            "description": "Generate an HR document for the employee (e.g., resignation letter, experience letter, salary certificate, NOC).",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "description": "Type of document to generate (contract, resignation_letter, experience_letter, salary_certificate, noc)",
                    },
                },
                "required": ["document_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_details",
            "description": "Get the full text of a specific policy document by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "The UUID of the policy document"},
                },
                "required": ["policy_id"],
            },
        },
    },
]


# ── Tool execution ───────────────────────────────────────────────────────────

_rag_pipeline = RAGPipeline()


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    db: AsyncSession,
    employee_id: UUID,
    organization_id: UUID,
) -> str:
    """Execute a tool call and return the result as a JSON string.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Parsed arguments from the LLM.
        db: Async database session.
        employee_id: The employee making the request.
        organization_id: Tenant ID for isolation.

    Returns:
        JSON-encoded string with the tool result.
    """
    try:
        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        result = await handler(arguments, db, employee_id, organization_id)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.exception("Tool execution error for %s", tool_name)
        return json.dumps({"error": str(e)})


async def _check_leave_balance(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    query = select(LeaveBalance).where(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.organization_id == org_id,
    )
    leave_type = args.get("leave_type")
    if leave_type:
        query = query.where(LeaveBalance.leave_type == leave_type)

    result = await db.execute(query)
    balances = result.scalars().all()
    return {
        "balances": [
            {
                "leave_type": b.leave_type,
                "total_days": b.total_days,
                "used_days": b.used_days,
                "remaining_days": b.total_days - b.used_days,
                "year": b.year,
            }
            for b in balances
        ]
    }


async def _submit_leave_request(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    leave_request = LeaveRequest(
        organization_id=org_id,
        employee_id=employee_id,
        leave_type=args["leave_type"],
        start_date=date.fromisoformat(args["start_date"]),
        end_date=date.fromisoformat(args["end_date"]),
        reason=args.get("reason"),
    )
    db.add(leave_request)
    await db.flush()
    return {
        "status": "submitted",
        "request_id": str(leave_request.id),
        "leave_type": leave_request.leave_type,
        "start_date": str(leave_request.start_date),
        "end_date": str(leave_request.end_date),
    }


async def _get_employee_info(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id, Employee.organization_id == org_id
        )
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        return {"error": "Employee record not found"}
    return {
        "employee_code": emp.employee_code,
        "full_name": emp.full_name,
        "email": emp.email,
        "department": emp.department,
        "position": emp.position,
        "hire_date": str(emp.hire_date) if emp.hire_date else None,
        "status": emp.status,
    }


async def _search_policies(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    query_text = args["query"]
    chunks = await _rag_pipeline.query(db, query_text, org_id, top_k=5)
    if not chunks:
        return {"results": [], "message": "No matching policies found."}
    return {
        "results": [
            {
                "policy_document_id": str(c.policy_document_id),
                "text": c.chunk_text,
                "similarity": round(c.similarity, 3),
            }
            for c in chunks
        ]
    }


async def _generate_document(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    template_titles = {
        "contract": "Employment Contract",
        "resignation_letter": "Resignation Letter",
        "experience_letter": "Experience Letter",
        "salary_certificate": "Salary Certificate",
        "noc": "No Objection Certificate",
    }
    doc_type = args["document_type"]
    title = template_titles.get(doc_type, f"Generated {doc_type}")

    document = Document(
        organization_id=org_id,
        employee_id=employee_id,
        document_type="letter",
        title=title,
        file_path=None,
        generated_from_template=True,
    )
    db.add(document)
    await db.flush()
    return {
        "status": "generated",
        "document_id": str(document.id),
        "title": title,
        "message": f"{title} has been generated successfully.",
    }


async def _get_policy_details(
    args: dict, db: AsyncSession, employee_id: UUID, org_id: UUID
) -> dict:
    policy_id = UUID(args["policy_id"])
    result = await db.execute(
        select(PolicyDocument).where(
            PolicyDocument.id == policy_id,
            PolicyDocument.organization_id == org_id,
            PolicyDocument.is_active.is_(True),
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        return {"error": "Policy document not found"}
    return {
        "id": str(policy.id),
        "title": policy.title,
        "content": policy.content,
        "category": policy.category,
    }


# Handler registry
_TOOL_HANDLERS = {
    "check_leave_balance": _check_leave_balance,
    "submit_leave_request": _submit_leave_request,
    "get_employee_info": _get_employee_info,
    "search_policies": _search_policies,
    "generate_document": _generate_document,
    "get_policy_details": _get_policy_details,
}
