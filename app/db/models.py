from sqlalchemy import String, BigInteger, Integer, DateTime, ForeignKey, Float, Boolean, Index, UniqueConstraint, text, func, Text, Date
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

from datetime import datetime, date


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id:             Mapped[int]         = mapped_column(Integer, primary_key=True)
    telegram_id:    Mapped[int]         = mapped_column(BigInteger, nullable=False)
    first_name:     Mapped[str]         = mapped_column(String, nullable=False)
    last_name:      Mapped[str | None]  = mapped_column(String, nullable=True)
    username:       Mapped[str | None]  = mapped_column(String, nullable=True)
    created_at:     Mapped[datetime]    = mapped_column(DateTime, default=func.now(), server_default=func.now())
    is_active:      Mapped[bool]        = mapped_column(Boolean, default=True, server_default=text("'true'"))

    signals = relationship("Signal", back_populates="user")

    __table_args__ = (
        UniqueConstraint(telegram_id, name="uq_users_telegram_id"),
        Index("ix_users_telegram_id", telegram_id),
        Index("ix_users_username", username),
    )

    def to_dict(self):
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

    id:         Mapped[int] = mapped_column(primary_key=True)
    name:       Mapped[str] = mapped_column(String, nullable=False)
    code:       Mapped[str] = mapped_column(String, nullable=False)
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("'true'"))
    performance_weight: Mapped[float] = mapped_column(
        Float, default=1.0, server_default=text("1.0")
    )

    signals = relationship("Signal", back_populates="strategy")

    __table_args__ = (
        UniqueConstraint("code", name="uq_strategies_code"),
        Index("ix_strategies_code", "code"),
        Index("ix_strategies_name", "name"),
    )

    def __repr__(self):
        return f"Strategy(id={self.id!r}, name={self.name!r}, code={self.code!r}, is_active={self.is_active!r})"

    def __str__(self):
        return f"Strategy(id={self.id!r}, name={self.name!r}, code={self.code!r})"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "is_active": self.is_active,
            "performance_weight": self.performance_weight,
        }


class Crypto(Base):
    __tablename__ = 'cryptos'

    id:     Mapped[int] = mapped_column(primary_key=True)
    name:   Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)

    signals = relationship("Signal", back_populates="crypto")

    __table_args__ = (
        UniqueConstraint("symbol", name="uq_cryptos_symbol"),
        Index("ix_cryptos_symbol", "symbol"),
        Index("ix_cryptos_name", "name"),
    )

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

    id:             Mapped[int]             = mapped_column(primary_key=True)
    user_id:        Mapped[int]             = mapped_column(ForeignKey("users.id"), nullable=False)
    strategy_id:    Mapped[int]             = mapped_column(ForeignKey("strategies.id"), nullable=False)
    crypto_id:      Mapped[int]             = mapped_column(ForeignKey("cryptos.id"), nullable=False)

    signal:         Mapped[str]             = mapped_column(String, nullable=False)
    timeframe:      Mapped[str]             = mapped_column(String, nullable=False, default='1h')
    stop_loss:      Mapped[float | None]    = mapped_column(Float, nullable=True)
    take_profit_1:  Mapped[float | None]    = mapped_column(Float, nullable=True)
    take_profit_2:  Mapped[float | None]    = mapped_column(Float, nullable=True)
    take_profit_3:  Mapped[float | None]    = mapped_column(Float, nullable=True)
    entry_price:    Mapped[float | None]    = mapped_column(Float, nullable=True)
    position_size:  Mapped[float | None]    = mapped_column(Float, nullable=True)
    in_position:    Mapped[bool]            = mapped_column(Boolean, default=False, server_default=text("'false'"))
    created_at:     Mapped[datetime]        = mapped_column(DateTime, default=func.now(), server_default=func.now())
    closed_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment:        Mapped[str | None]      = mapped_column(String, nullable=True)

    user                                    = relationship("User", back_populates="signals")
    strategy                                = relationship("Strategy", back_populates="signals")
    crypto                                  = relationship("Crypto", back_populates="signals")


    __table_args__ = (
        Index("ix_signals_user_id", "user_id"),
        Index("ix_signals_strategy_id", "strategy_id"),
        Index("ix_signals_crypto_id", "crypto_id"),
        Index("ix_signals_created_at", "created_at"),
        Index("ix_signals_signal", "signal"),
        Index("ix_signals_timeframe", "timeframe"),
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
            "timeframe": self.timeframe,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "in_position": self.in_position,
            "comment": self.comment,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "closed_at": self.closed_at.strftime("%Y-%m-%d %H:%M:%S") if self.closed_at else None
        }


class BacktestResult(Base):
    """Backtest natijalarini saqlash uchun model"""
    __tablename__ = 'backtest_results'

    id:                 Mapped[int]             = mapped_column(primary_key=True)
    user_id:            Mapped[int]             = mapped_column(BigInteger, nullable=False)
    
    # Parametrlar
    symbol:             Mapped[str]             = mapped_column(String(20), nullable=False)
    timeframe:          Mapped[str]             = mapped_column(String(10), nullable=False)
    threshold:          Mapped[float]           = mapped_column(Float, nullable=False)
    start_date:         Mapped[date]            = mapped_column(Date, nullable=False)
    end_date:           Mapped[date]            = mapped_column(Date, nullable=False)
    
    # Statistika
    total_signals:      Mapped[int]             = mapped_column(Integer, default=0)
    long_signals:       Mapped[int]             = mapped_column(Integer, default=0)
    short_signals:      Mapped[int]             = mapped_column(Integer, default=0)
    wins:               Mapped[int]             = mapped_column(Integer, default=0)
    losses:             Mapped[int]             = mapped_column(Integer, default=0)
    partial_wins:       Mapped[int]             = mapped_column(Integer, default=0)
    timeouts:           Mapped[int]             = mapped_column(Integer, default=0)
    
    # TP statistikasi
    tp1_hits:           Mapped[int]             = mapped_column(Integer, default=0)
    tp2_hits:           Mapped[int]             = mapped_column(Integer, default=0)
    tp3_hits:           Mapped[int]             = mapped_column(Integer, default=0)
    
    # Profit statistikasi
    total_profit:       Mapped[float]           = mapped_column(Float, default=0.0)
    average_profit:     Mapped[float]           = mapped_column(Float, default=0.0)
    average_loss:       Mapped[float]           = mapped_column(Float, default=0.0)
    max_profit:         Mapped[float]           = mapped_column(Float, default=0.0)
    max_loss:           Mapped[float]           = mapped_column(Float, default=0.0)
    profit_factor:      Mapped[float]           = mapped_column(Float, default=0.0)
    win_rate:           Mapped[float]           = mapped_column(Float, default=0.0)
    
    # Trade ma'lumotlari (JSON sifatida)
    trades_json:        Mapped[str | None]      = mapped_column(Text, nullable=True)

    # Strategiyalar performance ma'lumotlari (JSON)
    strategy_performance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # PDF file path
    pdf_path:           Mapped[str | None]      = mapped_column(String(500), nullable=True)
    
    created_at:         Mapped[datetime]        = mapped_column(DateTime, default=func.now(), server_default=func.now())

    __table_args__ = (
        # Parametrlar bo'yicha unique constraint - ayni parametrlar uchun bitta natija
        Index("ix_backtest_user_params", "user_id", "symbol", "timeframe", "threshold", "start_date", "end_date"),
        Index("ix_backtest_user_id", "user_id"),
        Index("ix_backtest_created_at", "created_at"),
    )

    def __repr__(self):
        return f"BacktestResult(id={self.id}, symbol={self.symbol}, timeframe={self.timeframe})"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "threshold": self.threshold,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "total_signals": self.total_signals,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "total_profit": self.total_profit,
            "profit_factor": self.profit_factor,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "strategy_performance_json": self.strategy_performance_json,
        }


