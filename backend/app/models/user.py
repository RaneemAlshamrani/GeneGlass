"""User account model prepared for the authentication task."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SqlEnum, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.review import Review


class UserRole(str, Enum):
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=UserRole.SPECIALIST,
        server_default=UserRole.SPECIALIST.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="owner")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="reviewer",
        foreign_keys="Review.reviewer_id",
    )
