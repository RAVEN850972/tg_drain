import datetime
from sqlalchemy import Index, Integer, String, BigInteger, ForeignKey, Boolean, DateTime, func
from sqlalchemy.orm import mapped_column, relationship, Mapped
from sqlalchemy import Text
from db import Base
from sqlalchemy import UniqueConstraint
from sqlalchemy import JSON

class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    status: Mapped[str] = mapped_column(String(64), default="Воркер", nullable=False)
    log_bot_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_counter: Mapped[int] = mapped_column(Integer, default=0)
    commission_every: Mapped[int] = mapped_column(Integer, default=4)
    gifts_unique_sent: Mapped[int] = mapped_column(Integer, default=0)
    stars_sent: Mapped[int] = mapped_column(Integer, default=0)
    daily_gifts_unique: Mapped[int] = mapped_column(Integer, default=0)
    daily_stars_sent: Mapped[int] = mapped_column(Integer, default=0)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    worker_added_payout_id_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_in_top: Mapped[bool] = mapped_column(Boolean, default=False)

    worker_bots: Mapped[list["WorkerBot"]] = relationship(
        "WorkerBot", back_populates="owner", cascade="all, delete"
    )
    settings: Mapped["Settings"] = relationship(
        "Settings", back_populates="admin", uselist=False, cascade="all, delete"
    )
    templates: Mapped[list["Template"]] = relationship(
        "Template", back_populates="owner", cascade="all, delete"
    )

class WorkerBot(Base):
    __tablename__ = "worker_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128))
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64))
    server_port: Mapped[int] = mapped_column(Integer, nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("admins.id"))
    owner: Mapped["Admin"] = relationship("Admin", back_populates="worker_bots")

    users: Mapped[list["WorkerBotUser"]] = relationship(
        "WorkerBotUser", back_populates="worker_bot", cascade="all, delete"
    )

    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    template: Mapped["Template"] = relationship("Template")

    base_template_id: Mapped[str | None] = mapped_column(String(32), nullable=True) # Новое

    custom_template_id: Mapped[int | None] = mapped_column(ForeignKey("custom_gifts.id"), nullable=True)
    custom_template: Mapped["CustomGift"] = relationship("CustomGift")

    launches: Mapped[int] = mapped_column(Integer, default=0)
    premium_launches: Mapped[int] = mapped_column(Integer, default=0)  
    connection_count: Mapped[int] = mapped_column(Integer, default=0)
    forward_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    nft_transfer_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    after_start: Mapped[str] = mapped_column(String, nullable=False)
    non_premium_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_rights_text: Mapped[str | None] = mapped_column(Text, nullable=True)  
    disconnect_text: Mapped[str | None] = mapped_column(Text, nullable=True) 
    video_path: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(255), nullable=True) 
    button_url: Mapped[str | None] = mapped_column(String(2000), nullable=True) 
    second_button_text: Mapped[str | None] = mapped_column(String(255), nullable=True) 
    second_button_reply: Mapped[str | None] = mapped_column(Text, nullable=True) 
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), nullable=True)
    share_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    owner: Mapped["Admin"] = relationship("Admin", back_populates="templates")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), unique=True)
    payout_ids: Mapped[str | None] = mapped_column(String, nullable=True)

    transfer_stars_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    convert_gifts_to_stars_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    fake_spin_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # << добавь это поле

    admin: Mapped["Admin"] = relationship("Admin", back_populates="settings")

class WorkerBotUser(Base):
    __tablename__ = "worker_bot_users"
    __table_args__ = (
        UniqueConstraint('telegram_id', 'worker_bot_id', name='uix_telegram_worker'),
        Index('ix_ref_by_user', 'referred_by_user_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_premium: Mapped[bool] = mapped_column(Boolean, default=False) 
    spin_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    stars_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)#

    worker_bot_id: Mapped[int | None] = mapped_column(ForeignKey("worker_bots.id"), nullable=True)
    worker_bot: Mapped["WorkerBot"] = relationship("WorkerBot", back_populates="users")

    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    referred_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("worker_bot_users.id"), nullable=True)
    referred_by: Mapped["WorkerBotUser"] = relationship("WorkerBotUser", remote_side=[id], backref="referrals")

class BusinessConnection(Base):
    __tablename__ = "business_connections"
    __table_args__ = (
        UniqueConstraint("worker_bot_id", "telegram_id", name="uix_worker_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"))
    admin: Mapped["Admin"] = relationship("Admin", backref="business_connections")

    worker_bot_id: Mapped[int] = mapped_column(ForeignKey("worker_bots.id"))
    worker_bot: Mapped["WorkerBot"] = relationship("WorkerBot", backref="business_connections")

    connected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    is_connected: Mapped[bool] = mapped_column(Boolean, default=True)

    business_connection_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    rights_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  

    nft_count: Mapped[int] = mapped_column(Integer, default=0)               
    regular_gift_count: Mapped[int] = mapped_column(Integer, default=0)      
    stars_count: Mapped[int] = mapped_column(Integer, default=0) 

class GlobalStats(Base):
    __tablename__ = "global_stats"

    id: Mapped[int] = mapped_column(primary_key=True)

    total_gifts_unique: Mapped[int] = mapped_column(Integer, default=0)
    total_stars_sent: Mapped[int] = mapped_column(Integer, default=0)

    daily_gifts_unique: Mapped[int] = mapped_column(Integer, default=0)
    daily_stars_sent: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)

    project_source: Mapped[str] = mapped_column(Text)   
    scam_experience: Mapped[str] = mapped_column(Text)  
    work_time: Mapped[str] = mapped_column(Text)        
    goals: Mapped[str] = mapped_column(Text)            

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

class CustomGift(Base):
    __tablename__ = "custom_gifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_name: Mapped[str] = mapped_column(String(255), default="")
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"))
    slugs: Mapped[str] = mapped_column(Text)
    message_text: Mapped[str] = mapped_column(Text)
    button_text: Mapped[str] = mapped_column(String(255))
    lang: Mapped[str] = mapped_column(String(16), default="RU")
    ref_message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  
    admin: Mapped["Admin"] = relationship("Admin", backref="custom_gifts")

class UserGiftHistory(Base):
    __tablename__ = "user_gift_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("worker_bot_users.id"), index=True)
    worker_bot_id: Mapped[int] = mapped_column(ForeignKey("worker_bots.id"), index=True)
    gift_slug: Mapped[str] = mapped_column(String(255), nullable=False)  
    gift_url: Mapped[str] = mapped_column(String(1024), nullable=False)  
    won_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    gift_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["WorkerBotUser"] = relationship("WorkerBotUser")
    worker_bot: Mapped["WorkerBot"] = relationship("WorkerBot")

class NFTGift(Base):
    __tablename__ = "nft_gifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)           

class StarCheck(Base):
    __tablename__ = "star_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False) 
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)  
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("worker_bot_users.id"), nullable=True)  
    used_by_user: Mapped["WorkerBotUser"] = relationship("WorkerBotUser")