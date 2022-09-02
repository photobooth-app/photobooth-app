import datetime
from threading import Thread
from multiprocessing import Pipe


def client(conn, message):
    conn.send(message)  # Send message to worker
    result = conn.recv()  # Receive result
    print('Bytes received from worker:', len(result))


def worker(conn):
    message = conn.recv()  # Get message from client
    def do_something(x): return x[::-1]
    result = do_something(message)
    conn.send(result)  # Send result to client


if __name__ == '__main__':
    large_message = 'X' * (2 << 4)
    client_conn, worker_conn = Pipe(duplex=True)  # Bidirectional pipe
    client_process = Thread(target=client, args=(client_conn, large_message))
    worker_process = Thread(target=worker, args=(worker_conn,))

    start_time = datetime.datetime.now()
    client_process.start()
    worker_process.start()

    client_process.join()
    worker_process.join()
    dt = datetime.datetime.now() - start_time

    # ~9.07 secs on my machine
    print('Time elapsed using Pipe:', dt.total_seconds())
