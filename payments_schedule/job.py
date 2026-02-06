from datetime import date
from sqlalchemy import update, func
from constants.group_constants import GroupType
from database.groups import Group


async def check_daily_payments(session_maker):
    async with session_maker() as session:
        today = date.today()

        stmt = (
            update(Group)
            .where(
                Group.subscription_type == GroupType.PAID,
                Group.paid_until.isnot(None),
                func.date(Group.paid_until) < today,
            )
            .values(
                subscription_type=GroupType.FREE,
                paid_until=None,
            )
        )

        await session.execute(stmt)
        await session.commit()
