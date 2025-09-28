from sqlalchemy import select

from .models import User, Signal, Strategy, Crypto


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
    

class CryptoCRUD():
    def __init__(self, session):
        self.session = session
        self.model = Crypto

    async def get_by_symbol(self, symbol: str):
        stm = select(self.model).where(Crypto.symbol == symbol)
        result = await self.session.execute(stm)
        return result.scalars().first()