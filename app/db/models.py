from sqlalchemy import String, BigInteger, Integer, DateTime, ForeignKey, Float, Boolean, Index
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    signals = relationship("Signal", back_populates="user")

    def to_dict(self):
        """
        Returns a dictionary representation of the User object

        The dictionary will contain the following keys:
            id (int): Unique identifier of the user
            telegram_id (int): The user's Telegram ID
            username (str): The user's username
            first_name (str): The user's first name
            last_name (str): The user's last name
            created_at (str): The date and time the user was added, in ISO 8601 format

        Returns:
            dict: A dictionary representation of the User object
        """

        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    def __repr__(self):
        return f"User(id={self.id!r}, username={self.username!r}, first_name={self.first_name!r}, last_name={self.last_name!r})"

    def __str__(self):
        return f"User(id={self.id!r}, username={self.username!r}, first_name={self.first_name!r}, last_name={self.last_name!r})"
    

class Strategy(Base):
    __tablename__ = 'strategies'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String, unique=True)

    signals = relationship("Signal", back_populates="strategy")

    def __repr__(self):
        return f"Strategy(id={self.id!r}, name={self.name!r}, code={self.code!r})"

    def __str__(self):
        return f"Strategy(id={self.id!r}, name={self.name!r}, code={self.code!r})"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code
        }


class Crypto(Base):
    __tablename__ = 'cryptos'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String, unique=True)

    signals = relationship("Signal", back_populates="crypto")

    def __repr__(self):
        return f"Crypto(id={self.id!r}, name={self.name!r}, symbol={self.symbol!r})"

    def __str__(self):
        return f"Crypto(id={self.id!r}, name={self.name!r}, symbol={self.symbol!r})"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "symbol": self.symbol
        }
    

class Signal(Base):
    __tablename__ = 'signals'

    id: Mapped[int]                         = mapped_column(primary_key=True)
    user_id: Mapped[int]                    = mapped_column(ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[int]                = mapped_column(ForeignKey("strategies.id"), nullable=False)
    crypto_id: Mapped[int]                  = mapped_column(ForeignKey("cryptos.id"), nullable=False)

    signal: Mapped[str]                     = mapped_column(String, nullable=False)
    stop_loss: Mapped[float]                = mapped_column(Float)
    take_profit_1: Mapped[float]            = mapped_column(Float)
    take_profit_2: Mapped[float]            = mapped_column(Float)
    take_profit_3: Mapped[float]            = mapped_column(Float)
    entry_price: Mapped[float]              = mapped_column(Float)
    position_size: Mapped[float | None]     = mapped_column(Float, nullable=True)
    in_position: Mapped[bool]               = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime]            = mapped_column(DateTime, default=datetime.now, index=True)
    closed_at: Mapped[datetime | None]      = mapped_column(DateTime, nullable=True)
    comment: Mapped[str | None]             = mapped_column(String, nullable=True)

    user                                    = relationship("User", back_populates="signals")
    strategy                                = relationship("Strategy", back_populates="signals")
    crypto                                  = relationship("Crypto", back_populates="signals")


    __table_args__ = (
        Index("ix_signals_in_position_true", "in_position", postgresql_where=(in_position == True)),
    )

    def __repr__(self):
        return f"Signal(id={self.id!r}, user_id={self.user_id!r}, strategy_id={self.strategy_id!r}, crypto_id={self.crypto_id!r}, signal={self.signal!r}, created_at={self.created_at!r})"

    def __str__(self):
        return f"Signal(id={self.id!r}, user_id={self.user_id!r}, strategy_id={self.strategy_id!r}, crypto_id={self.crypto_id!r}, signal={self.signal!r}, created_at={self.created_at!r})"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "crypto_id": self.crypto_id,
            "signal": self.signal,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "in_position": self.in_position,
            "position_type": self.position_type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "closed_at": self.closed_at.strftime("%Y-%m-%d %H:%M:%S") if self.closed_at else None
        }


