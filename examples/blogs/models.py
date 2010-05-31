# -*- coding: utf-8 -*-

from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relation
from sqlalchemy.orm.exc import NoResultFound
from insanities.ext.auth import check_password, encrypt_password


ModelBase = declarative_base()


class User(ModelBase):

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    login = Column(String)
    password = Column(String)
    title = Column(String)

    @classmethod
    def by_credential(cls, rctx, login, password):
        try:
            user = rctx.vals.db.query(User).filter_by(login=login).one()
            if check_password(password, user.password):
                return user.id
        except NoResultFound:
            pass
        return None

    @classmethod
    def by_id(cls, rctx, id):
        try:
            user = rctx.vals.db.query(User).filter_by(id=id).one()
        except NoResultFound:
            pass
        else:
            return user
        return None

    def set_password(self, password):
        self.password = encrypt_password(password)

    def __repr__(self):
        return '<%s: %d>' % (self.__class__.__name__, self.id)


class Post(ModelBase):

    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    slug = Column(String)
    body = Column(Text)
    date = Column(DateTime)
    author_id = Column(Integer, ForeignKey(User.id))
    author = relation(User)

    def __repr__(self):
        return '<%s: %d>' % (self.__class__.__name__, self.id)
