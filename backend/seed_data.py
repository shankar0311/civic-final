
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, select
from database import DATABASE_URL
from models import Department, User, UserRole, FieldTeam
from utils.security import get_password_hash
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

async def seed():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        print("Seeding departments...")
        departments = [
            {"name": "Roads", "slug": "roads"},
        ]
        
        for dept_data in departments:
            result = await session.execute(select(Department).where(Department.slug == dept_data["slug"]))
            dept = result.scalars().first()
            if not dept:
                new_dept = Department(**dept_data)
                session.add(new_dept)
                print(f"Created department: {dept_data['name']}")
        
        await session.commit()
        
        print("Seeding users...")
        # Admin User
        admin_email = "admin@example.com"
        result = await session.execute(select(User).where(User.email == admin_email))
        admin = result.scalars().first()
        if not admin:
            hashed_pw = get_password_hash("admin123")
            new_admin = User(
                email=admin_email,
                name="Admin User",
                hashed_password=hashed_pw,
                role=UserRole.admin
            )
            session.add(new_admin)
            print("Created Admin user: admin@example.com / admin123")
        
        # Citizen User
        citizen_email = "citizen@example.com"
        result = await session.execute(select(User).where(User.email == citizen_email))
        citizen = result.scalars().first()
        if not citizen:
            hashed_pw = get_password_hash("citizen123")
            new_citizen = User(
                email=citizen_email,
                name="John Citizen",
                hashed_password=hashed_pw,
                role=UserRole.citizen
            )
            session.add(new_citizen)
            print("Created Citizen user: citizen@example.com / citizen123")

        await session.commit()
        print("Seeding complete!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
