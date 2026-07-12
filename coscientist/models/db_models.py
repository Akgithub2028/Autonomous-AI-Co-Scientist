import os
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Goal(Base):
    __tablename__ = 'goals'
    id = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    hypotheses = relationship("Hypothesis", back_populates="goal")

class Hypothesis(Base):
    __tablename__ = 'hypotheses'
    uid = Column(String, primary_key=True)
    goal_id = Column(String, ForeignKey('goals.id'), nullable=False)
    content = Column(Text, nullable=False)
    elo = Column(Float, default=1200.0)
    stage = Column(String) # 'generated', 'reviewed', 'evolved'
    goal = relationship("Goal", back_populates="hypotheses")
    reviews = relationship("Review", back_populates="hypothesis")

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis_uid = Column(String, ForeignKey('hypotheses.uid'))
    verification_result = Column(Text)
    hypothesis = relationship("Hypothesis", back_populates="reviews")

class Match(Base):
    __tablename__ = 'matches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    winner_uid = Column(String, ForeignKey('hypotheses.uid'))
    loser_uid = Column(String, ForeignKey('hypotheses.uid'))
    justification = Column(Text)
