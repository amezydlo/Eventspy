from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Pop: _ClassVar[EventType]
    Rock: _ClassVar[EventType]
    Metal: _ClassVar[EventType]
    HeavyMetal: _ClassVar[EventType]
    House: _ClassVar[EventType]
    Musicals: _ClassVar[EventType]
Pop: EventType
Rock: EventType
Metal: EventType
HeavyMetal: EventType
House: EventType
Musicals: EventType

class Client(_message.Message):
    __slots__ = ("id", "nick")
    ID_FIELD_NUMBER: _ClassVar[int]
    NICK_FIELD_NUMBER: _ClassVar[int]
    id: int
    nick: str
    def __init__(self, id: _Optional[int] = ..., nick: _Optional[str] = ...) -> None: ...

class NotificationRequest(_message.Message):
    __slots__ = ("client", "events")
    CLIENT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    client: Client
    events: _containers.RepeatedScalarFieldContainer[EventType]
    def __init__(self, client: _Optional[_Union[Client, _Mapping]] = ..., events: _Optional[_Iterable[_Union[EventType, str]]] = ...) -> None: ...

class Notification(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedScalarFieldContainer[EventType]
    def __init__(self, events: _Optional[_Iterable[_Union[EventType, str]]] = ...) -> None: ...

class NotificationResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...
