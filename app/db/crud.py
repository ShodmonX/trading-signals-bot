from sqlalchemy import select, and_
from datetime import date

from .models import User, Signal, Strategy, Crypto, BacktestResult


class UserCRUD():
    def __init__(self, session):
        self.session = session
        self.model = User

    async def get(self, telegram_id: int):
        stm = select(self.model).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stm)
        return result.scalars().first()
    
    async def get_all(self):
        stm = select(self.model)
        result = await self.session.execute(stm)
        return result.scalars().all()
    
    async def create(self, data: dict):
        user = self.model(**data)
        self.session.add(user)
        try:
            await self.session.commit()
            await self.session.refresh(user)
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return user
    
    async def update(self, data: dict):
        telegram_id = data.pop("telegram_id")
        if not telegram_id:
            raise ValueError("telegram_id is required")
        
        user = await self.get(telegram_id)
        if not user:
            raise ValueError("User not found")
        
        for key, value in data.items():
            setattr(user, key, value)
        
        try:
            await self.session.commit()
            await self.session.refresh(user)
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return user
    
    async def delete(self, telegram_id: int):
        user = await self.get(telegram_id)
        if not user:
            raise ValueError("User not found")
        try:
            await self.session.delete(user)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return user
    
    async def create_and_update(self, data: dict):
        telegram_id = data.get("telegram_id")
        if not telegram_id:
            raise ValueError("telegram_id is required")
        
        user = await self.get(telegram_id)
        if not user:
            user = await self.create(data)
        else:
            user = await self.update(data)
        
        return user


class SignalCRUD():
    def __init__(self, session):
        self.session = session
        self.model = Signal

    async def create(self, data: dict):
        signal = self.model(**data)
        self.session.add(signal)
        try:
            await self.session.commit()
            await self.session.refresh(signal)
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return signal
    
    async def get(self, id: int): 
        stm = select(self.model).where(Signal.id == id)
        result = await self.session.execute(stm)
        return result.scalars().first()
    
    async def delete(self, id: int):
        signal = await self.get(id)
        if not signal:
            raise ValueError("Signal not found")
        try:
            await self.session.delete(signal)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return signal
    
    async def create_and_update(self, data: dict):
        id = data.get("id")
        if not id:
            raise ValueError("id is required")
        
        signal = await self.get(id)
        if not signal:
            signal = await self.create(data)
        else:
            signal = await self.update(data)
        
        return signal
    
    async def update(self, data: dict):
        id = data.pop("id")
        if not id:
            raise ValueError("id is required")
        
        signal = await self.get(id)
        if not signal:
            raise ValueError("Signal not found")
        
        for key, value in data.items():
            setattr(signal, key, value)
        
        try:
            await self.session.commit()
            await self.session.refresh(signal)
        except Exception as e:
            await self.session.rollback()
            raise e
        
        return signal


class StrategyCRUD():
    def __init__(self, session):
        self.session = session
        self.model = Strategy

    async def get_by_code(self, code: str):
        stm = select(self.model).where(Strategy.code == code)
        result = await self.session.execute(stm)
        return result.scalars().first()
    
    async def get_all(self, only_active: bool = True) -> list[Strategy]:
        """Barcha strategiyalarni olish"""
        if only_active:
            stm = select(self.model).where(Strategy.is_active == True)
        else:
            stm = select(self.model)
        result = await self.session.execute(stm)
        return list(result.scalars().all())
    
    async def get_by_id(self, id: int):
        stm = select(self.model).where(Strategy.id == id)
        result = await self.session.execute(stm)
        return result.scalars().first()
    
    async def update_status(self, code: str, is_active: bool):
        """Strategiya statusini o'zgartirish"""
        strategy = await self.get_by_code(code)
        if strategy:
            strategy.is_active = is_active
            await self.session.commit()
            await self.session.refresh(strategy)
        return strategy
    

class CryptoCRUD():
    def __init__(self, session):
        self.session = session
        self.model = Crypto

    async def get_by_symbol(self, symbol: str):
        stm = select(self.model).where(Crypto.symbol == symbol)
        result = await self.session.execute(stm)
        return result.scalars().first()


class BacktestResultCRUD():
    """Backtest natijalarini saqlash va olish uchun CRUD"""
    
    def __init__(self, session):
        self.session = session
        self.model = BacktestResult
    
    async def find_existing(
        self,
        user_id: int,
        symbol: str,
        timeframe: str,
        threshold: float,
        start_date: date,
        end_date: date,
    ) -> BacktestResult | None:
        """Mavjud backtest natijasini qidirish"""
        stm = select(self.model).where(
            and_(
                BacktestResult.user_id == user_id,
                BacktestResult.symbol == symbol,
                BacktestResult.timeframe == timeframe,
                BacktestResult.threshold == threshold,
                BacktestResult.start_date == start_date,
                BacktestResult.end_date == end_date,
            )
        )
        result = await self.session.execute(stm)
        return result.scalars().first()
    
    async def create(self, data: dict) -> BacktestResult:
        """Yangi backtest natijasini saqlash"""
        result = self.model(**data)
        self.session.add(result)
        try:
            await self.session.commit()
            await self.session.refresh(result)
        except Exception as e:
            await self.session.rollback()
            raise e
        return result
    
    async def update(self, result_id: int, data: dict) -> BacktestResult | None:
        """Backtest natijasini yangilash"""
        stm = select(self.model).where(BacktestResult.id == result_id)
        result = await self.session.execute(stm)
        backtest = result.scalars().first()
        
        if not backtest:
            return None
        
        for key, value in data.items():
            setattr(backtest, key, value)
        
        try:
            await self.session.commit()
            await self.session.refresh(backtest)
        except Exception as e:
            await self.session.rollback()
            raise e
        return backtest
    
    async def delete(self, result_id: int) -> bool:
        """Backtest natijasini o'chirish"""
        stm = select(self.model).where(BacktestResult.id == result_id)
        result = await self.session.execute(stm)
        backtest = result.scalars().first()
        
        if not backtest:
            return False
        
        try:
            await self.session.delete(backtest)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e
        return True
    
    async def get_by_user(self, user_id: int, limit: int = 10) -> list[BacktestResult]:
        """Foydalanuvchining backtest natijalarini olish"""
        stm = (
            select(self.model)
            .where(BacktestResult.user_id == user_id)
            .order_by(BacktestResult.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stm)
        return list(result.scalars().all())
    
    async def get_by_id(self, result_id: int) -> BacktestResult | None:
        """ID bo'yicha backtest natijasini olish"""
        stm = select(self.model).where(BacktestResult.id == result_id)
        result = await self.session.execute(stm)
        return result.scalars().first()