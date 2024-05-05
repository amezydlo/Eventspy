import random
import threading
import time
from concurrent import futures
from typing import Dict, Union, List

import grpc

from gen import events_pb2_grpc, events_pb2
from gen.events_pb2 import Client, NotificationResponse, EventType, Notification


class ClientContext:
    def __init__(self, client_id, client_nick, subscription_context):
        self.subscription_context = subscription_context
        self.client_id = client_id
        self.client_nick = client_nick
        self.observed_events = {}


class EventService(events_pb2_grpc.EventServiceServicer):
    def __init__(self, clients, event_processor, condition):
        self.clients: Dict[int, ClientContext] = clients
        self.should_stop_stream = {}
        self.condition: threading.Condition = condition
        self.event_processor: EventProcessor = event_processor
        self.should_notify_client = {}

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
            client_connection = ClientContext(client_id, request.nick, None)
            self.clients[client_id] = client_connection
            self.should_stop_stream[client_id] = False
            return Client(id=client_id, nick=request.nick)  # ACK

        elif request.id in self.clients:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, 'Client already exists')

        context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client has invalid ID')

    def disconnectClient(self, request, context):
        if request.id == 0 or request.id not in self.clients:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client has invalid ID')
        else:
            self.condition.acquire()
            self.should_stop_stream[request.id] = True
            self.condition.notify_all()
            self.condition.release()
            del self.clients[request.id]
            print(f"Client {request.id} disconnected")
            return NotificationResponse(message="successfully deleted client")

    def subscribe(self, request: events_pb2.NotificationRequest, context):
        if request.client is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client field cannot empty')

        client = request.client

        if client.id == 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client id field cannot empty')

        elif client.id in self.clients:
            if self.clients[client.id].subscription_context is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, 'Client already opened its subscription')

            self.clients[client.id].subscription_context = context  # ustawiamy kontekst aby wiedzieć gdzie wysyłamy

            events_raw = request.events
            observed_events = list(events_raw)
            self.clients[client.id].observed_events = observed_events

            events_names = [EventType.Name(event) for event in events_raw]
            print(f"Client {client.nick} subscribed for events {events_names}")

            while not self.should_stop_stream[client.id]:
                self.condition.acquire()

                notifyme = False
                while not self.should_stop_stream[client.id] and not notifyme:
                    self.condition.wait()
                    if self.should_stop_stream[client.id]:
                        del self.should_stop_stream[client.id]
                        self.condition.release()
                        return
                    else:
                        notifyme = True

                events_to_notify = []
                for event in self.event_processor.random_events:
                    if event in self.clients[client.id].observed_events:
                        events_to_notify.append(EventType.Name(event))

                if len(events_to_notify) > 0:

                    print(f"Notifying client: {client.nick} ({client.id}) about: "
                          f"{events_to_notify}")
                    yield Notification(events=events_to_notify)
                self.condition.release()

    def unsubscribe(self, request: events_pb2.NotificationRequest, context):
        if not request.client:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client field cannot empty')

        client = request.client
        if not client.id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client.id cannot be empty')

        elif client.id in self.clients:
            if self.clients[client.id].subscription_context is None:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Client has no subscription')

            events_raw = request.events
            unsubscribed_events = [EventType.Value(event) for event in events_raw]

            print(f"Client {client.nick} unsubscribed for events {unsubscribed_events}")
            self.clients[client.id].observed_events \
                = [elem for elem in self.clients[client.id].observed_events if elem not in unsubscribed_events]

            message = f"Client {client.nick} unsubscribed for events {unsubscribed_events}"
            return NotificationResponse(message)


class Server:
    def __init__(self, event_processor, condition):
        self.clients: Dict[int, ClientContext] = {}
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
        self.random_events: List[EventType] = []

        self.condition: threading.Condition = condition

    def run(self):
        while True:
            self.condition.acquire()
            self.random_events = self.generate_random_events()

            for event in self.random_events:
                print(EventType.Name(event))

            print()

            self.condition.notify_all()
            self.condition.release()
            time.sleep(5)

    @staticmethod
    def generate_random_events():
        length = random.randint(1, 4)

        random_events = random.sample(list(EventType.values()), length)

        return random_events


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
