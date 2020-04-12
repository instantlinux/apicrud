# Metrics at scale are a hard problem; see
#  https://www.infoworld.com/article/3230455/how-to-use-redis-for-real-time-metering-applications.html
# The main counting is done in memory with redis but data has to be
#  periodically persisted here--and older entries have to be pruned,
#  which is an expensive delete operation.

# Food for thought: why not create (upon first use for a given
# user/metric) a decrementing redis key that expires at the end of the
# grant period? If the redis deployment is sufficiently reliable,
# persistence to disk here might be unwanted. At worst, a redis crash
# would cause users to get free service for a while--a lower cost than
# trying to scale this damn thing.

# This was the metrics table I contemplated for sqlalchemy:

# class Metric(Base):
#     __tablename__ = 'metrics'
#     __table_args__ = (
#         UniqueConstraint(u'uid', u'name', u'day', name='uniq_metric'),
#     )
#
#     id = Column(String(16), primary_key=True, unique=True)
#     name = Column(Enum(u'direct', u'email', u'events', u'photos', u'sms'),
#                   nullable=False)
#     value = Column(BIGINT, nullable=False, server_default="0")
#     day = Column(INTEGER)
#     uid = Column(ForeignKey(u'people.id'), nullable=False, index=True)
#     created = Column(TIMESTAMP, nullable=False, server_default=func.now())
#     modified = Column(TIMESTAMP)
#
#     owner = relationship('Person', foreign_keys=[uid])
