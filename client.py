import threading
import time

import grpc

from gen import events_pb2_grpc, events_pb2
from gen.events_pb2 import *



class Client:
    def __init__(self):
        self.running = False
        self.client_network_thread = threading.Thread(target=self.run)
        self.channel = None

    def repl(self):
        while True:
            command = input("> ")
            if command == "start":
                self.start_client()
            elif command == "stop":
                self.stop_client()

    def start_client(self):
        if not self.running:
            self.running = True
            self.channel = grpc.insecure_channel('localhost:50051')
            self.client_network_thread.start()

    def stop_client(self):
        if self.running:
            self.running = False

    def run(self):
        try:
            stub = events_pb2_grpc.EventServiceStub(self.channel)

            client = events_pb2.Client(nick="alina")
            # request = events_pb2.NotificationRequest(client=client)
            #
            # request.events.extend([EventType.Pop, EventType.Rock])
            #
            # ret = stub.subscribe(request)
            # for i in ret:
            #     print(i)
            ret = stub.connectClient(client)
            client.id = ret.id
            time.sleep(5)

            notifications = NotificationRequest(client=client, events=[EventType.House])
            ret = stub.subscribe(notifications)


            for r in ret:
                print(r)

            time.sleep(5)

            stub.disconnectClient(client)

        finally:
            if not self.running:
                self.channel.close()


if __name__ == '__main__':
    client = Client()
    client.repl()
