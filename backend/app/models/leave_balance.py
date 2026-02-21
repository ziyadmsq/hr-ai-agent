import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    leave_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # annual, sick, maternity, paternity, unpaid
    total_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    used_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="leave_balances")

