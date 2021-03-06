# -*- encoding: utf-8 -*-
#
# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
SQLAlchemy models for baremetal data.
"""

import json

from oslo_config import cfg
from oslo_db import options as db_options
from oslo_db.sqlalchemy import models
import six.moves.urllib.parse as urlparse
from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import ForeignKey, Integer
from sqlalchemy import schema, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator, TEXT

from ironic.common import paths


sql_opts = [
    cfg.StrOpt('mysql_engine',
               default='InnoDB',
               help='MySQL engine to use.')
]

_DEFAULT_SQL_CONNECTION = 'sqlite:///' + paths.state_path_def('ironic.sqlite')


cfg.CONF.register_opts(sql_opts, 'database')
db_options.set_defaults(cfg.CONF, _DEFAULT_SQL_CONNECTION, 'ironic.sqlite')


def table_args():
    engine_name = urlparse.urlparse(cfg.CONF.database.connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': cfg.CONF.database.mysql_engine,
                'mysql_charset': "utf8"}
    return None


class JsonEncodedType(TypeDecorator):
    """Abstract base type serialized as json-encoded string in db."""
    type = None
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is None:
            # Save default value according to current type to keep the
            # interface the consistent.
            value = self.type()
        elif not isinstance(value, self.type):
            raise TypeError("%s supposes to store %s objects, but %s given"
                            % (self.__class__.__name__,
                               self.type.__name__,
                               type(value).__name__))
        serialized_value = json.dumps(value)
        return serialized_value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class JSONEncodedDict(JsonEncodedType):
    """Represents dict serialized as json-encoded string in db."""
    type = dict


class JSONEncodedList(JsonEncodedType):
    """Represents list serialized as json-encoded string in db."""
    type = list


class IronicBase(models.TimestampMixin,
                 models.ModelBase):

    metadata = None

    def as_dict(self):
        d = {}
        for c in self.__table__.columns:
            d[c.name] = self[c.name]
        return d

    def save(self, session=None):
        import ironic.db.sqlalchemy.api as db_api

        if session is None:
            session = db_api.get_session()

        super(IronicBase, self).save(session)

Base = declarative_base(cls=IronicBase)


class Chassis(Base):
    """Represents a hardware chassis."""

    __tablename__ = 'chassis'
    __table_args__ = (
        schema.UniqueConstraint('uuid', name='uniq_chassis0uuid'),
        table_args()
    )
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36))
    extra = Column(JSONEncodedDict)
    description = Column(String(255), nullable=True)


class Conductor(Base):
    """Represents a conductor service entry."""

    __tablename__ = 'conductors'
    __table_args__ = (
        schema.UniqueConstraint('hostname', name='uniq_conductors0hostname'),
        table_args()
    )
    id = Column(Integer, primary_key=True)
    hostname = Column(String(255), nullable=False)
    drivers = Column(JSONEncodedList)
    online = Column(Boolean, default=True)


class Node(Base):
    """Represents a bare metal node."""

    __tablename__ = 'nodes'
    __table_args__ = (
        schema.UniqueConstraint('uuid', name='uniq_nodes0uuid'),
        schema.UniqueConstraint('instance_uuid',
                                name='uniq_nodes0instance_uuid'),
        schema.UniqueConstraint('name', name='uniq_nodes0name'),
        table_args())
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36))
    # NOTE(deva): we store instance_uuid directly on the node so that we can
    #             filter on it more efficiently, even though it is
    #             user-settable, and would otherwise be in node.properties.
    instance_uuid = Column(String(36), nullable=True)
    name = Column(String(255), nullable=True)
    chassis_id = Column(Integer, ForeignKey('chassis.id'), nullable=True)
    power_state = Column(String(15), nullable=True)
    target_power_state = Column(String(15), nullable=True)
    provision_state = Column(String(15), nullable=True)
    target_provision_state = Column(String(15), nullable=True)
    provision_updated_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    instance_info = Column(JSONEncodedDict)
    properties = Column(JSONEncodedDict)
    driver = Column(String(15))
    driver_info = Column(JSONEncodedDict)
    driver_internal_info = Column(JSONEncodedDict)
    clean_step = Column(JSONEncodedDict)

    raid_config = Column(JSONEncodedDict)
    target_raid_config = Column(JSONEncodedDict)

    # NOTE(deva): this is the host name of the conductor which has
    #             acquired a TaskManager lock on the node.
    #             We should use an INT FK (conductors.id) in the future.
    reservation = Column(String(255), nullable=True)

    # NOTE(deva): this is the id of the last conductor which prepared local
    #             state for the node (eg, a PXE config file).
    #             When affinity and the hash ring's mapping do not match,
    #             this indicates that a conductor should rebuild local state.
    conductor_affinity = Column(Integer,
                                ForeignKey('conductors.id',
                                           name='nodes_conductor_affinity_fk'),
                                nullable=True)

    maintenance = Column(Boolean, default=False)
    maintenance_reason = Column(Text, nullable=True)
    console_enabled = Column(Boolean, default=False)
    inspection_finished_at = Column(DateTime, nullable=True)
    inspection_started_at = Column(DateTime, nullable=True)
    extra = Column(JSONEncodedDict)


class Port(Base):
    """Represents a network port of a bare metal node."""

    __tablename__ = 'ports'
    __table_args__ = (
        schema.UniqueConstraint('address', name='uniq_ports0address'),
        schema.UniqueConstraint('uuid', name='uniq_ports0uuid'),
        table_args())
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36))
    address = Column(String(18))
    node_id = Column(Integer, ForeignKey('nodes.id'), nullable=True)
    extra = Column(JSONEncodedDict)
