import random
import threading
import time
from concurrent import futures
from typing import Dict, Union

import events_pb2
import events_pb2_grpc
import grpc
from events_pb2 import *


class Connection:
    def __init__(self, client_id, client_nick, subscription_context):
        self.subscription_context = subscription_context
        self.client_id = client_id
        self.client_nick = client_nick


class EventService(events_pb2_grpc.EventServiceServicer):
    def __init__(self, clients, event_processor, condition):
        self.clients: Dict[int, Connection] = clients
        self.should_stop_stream = False
        self.condition: threading.Condition = condition
        self.event_processor: EventProcessor = event_processor

    def find_lowest_id(self, ids, l, r, lowest):
        if r < l:
            return lowest
        q = (l + r) // 2
        if ids[q] != q + 1 and q + 1 < lowest:
            lowest = q + 1
            return self.find_lowest_id(ids, l, q - 1, lowest)

        elif ids[q] == q + 1:
            return self.find_lowest_id(ids, q + 1, r, lowest)

    def create_unique_id(self):
        ids = sorted(self.clients.keys())
        if len(ids) == 0:
            return 1
        return self.find_lowest_id(ids, 0, len(ids) - 1, ids[len(ids) - 1] + 1)

    def connectClient(self, request, context):
        if request.nick is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client nick field cannot empty')

        if request.id == 0:
            print("Creating new client...")
            client_id = self.create_unique_id()
            client_connection = Connection(client_id, request.nick, None)
            self.clients[client_id] = client_connection
            return Client(id=client_id, nick=request.nick)  # ACK

        elif request.id in self.clients:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, 'Client already exists')

        context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client has invalid ID')

    def disconnectClient(self, request, context):
        if request.id == 0 or request.id not in self.clients:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client has invalid ID')
        else:
            del self.clients[request.id]
            return NotificationResponse(message="successfully deleted client")

    def subscribe(self, request: events_pb2.NotificationRequest, context):
        if request.client is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client field cannot empty')

        client = request.client
        if client.id == 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client id field cannot empty')

        elif client.id in self.clients:
            self.clients[client.id].subscription_context = context  # ustawiamy kontekst aby wiedzieć gdzie wysyłamy
            # todo to be changed
            events_raw = request.events
            events_names = [EventType.Name(event) for event in events_raw]

            observed_events = [EventType.Value(event) for event in events_raw]
            print(f"Client {client.nick} subscribed for events {events_names}")

            while not self.should_stop_stream:
                self.condition.acquire()
                while self.event_processor.latest_event not in observed_events:
                    self.condition.wait()
                yield Notification(events=events_raw)

                self.condition.release()

        # try:
        #     print(f"Client {client.nick} subscribed for events {events_names}")
        #     while not self.should_stop_stream:
        #         yield Notification(events=events_raw)
        #         time.sleep(5)
        #
        # except grpc.RpcError as e:
        #     print(f"Error occurred for {client.nick}: {e}")
        #     del self.clients[client.id]

    def unsubscribe(self, request: events_pb2.NotificationRequest, context):
        if not request.client:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client field cannot empty')

        client = request.client
        if not client.id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client.id cannot be empty')

        elif client.id in self.clients:
            message = f"Client {client.nick} successfully unsubscribed"
            return NotificationResponse(message)
            # todo unsubscribe events


class Server:
    def __init__(self, event_processor, condition):
        self.clients: Dict[int, Connection] = {}
        self.condition = condition
        self.event_processor = event_processor
        self.event_service = EventService(self.clients, self.event_processor, self.condition)

    def list_clients(self):
        for key, connection in self.clients.items():
            print("Client ID:", key)
            print("Client Nick:", connection.client_nick)
            print()

    # todo sorted version for future
    # def list_clients(self):
    #     sorted_clients = sorted(self.clients.items(), key=lambda x: x[0])
    #     for key, connection in sorted_clients:
    #         print("Client ID:", key)
    #         print("Client Nick:", connection.client_nick)
    #         print()

    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        events_pb2_grpc.add_EventServiceServicer_to_server(self.event_service, server)
        server.add_insecure_port('[::]:50051')
        server.start()
        print("Server started")
        server.wait_for_termination()
        print("Terminated")


class EventProcessor:
    def __init__(self, condition):
        self.latest_event: Union[EventType, None] = None
        self.condition: threading.Condition = condition

    def run(self):
        while True:
            self.condition.acquire()
            self.latest_event = random.choice(EventType.values())
            print(self.latest_event)
            self.condition.notify_all()
            self.condition.release()
            time.sleep(5)


if __name__ == "__main__":
    condition = threading.Condition()
    event_processor = EventProcessor(condition)

    server_instance = Server(event_processor, condition)
    serve_thread = threading.Thread(target=server_instance.serve)
    serve_thread.start()

    event_processing_thread = threading.Thread(target=event_processor.run)
    event_processing_thread.start()

    while True:
        server_instance.list_clients()
        time.sleep(5)
