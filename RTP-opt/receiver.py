import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum


def send_ack(sock, addr, seq_num):
    # tao va gui goi ack (type=3) voi dung seq_num truyen vao
    hdr = PacketHeader(type=3, seq_num=seq_num, length=0, checksum=0)
    hdr.checksum = compute_checksum(hdr / b"")
    sock.sendto(bytes(hdr / b""), addr)


def receiver(receiver_ip, receiver_port, window_size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((receiver_ip, receiver_port))

    in_connection = False
    expected_seq = 1
    recv_buffer = {}  # luu tam cac goi den chua dung thu tu

    while True:
        try:
            pkt, address = sock.recvfrom(2048)
        except OSError:
            continue
        if len(pkt) < 16:
            continue

        # tach header va data
        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16 : 16 + pkt_header.length]

        # check checksum, neu loi thi bo qua goi tin
        pkt_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        if pkt_checksum != computed_checksum:
            continue

        pkt_type = pkt_header.type
        seq_num = pkt_header.seq_num

        # xu ly goi START (type=0)
        if pkt_type == 0:
            if not in_connection:
                in_connection = True
                expected_seq = 1
                recv_buffer.clear()
                send_ack(sock, address, 1)
            continue

        if not in_connection:
            continue

        # xu ly goi DATA (type=2)
        if pkt_type == 2:
            # bo qua goi vuot qua gioi han window
            if seq_num >= expected_seq + window_size:
                continue

            if seq_num >= expected_seq:
                if seq_num not in recv_buffer:
                    recv_buffer[seq_num] = msg

                # neu goi vua nhan trung voi expected_seq thi ghi ra stdout
                if seq_num == expected_seq:
                    while expected_seq in recv_buffer:
                        sys.stdout.buffer.write(recv_buffer.pop(expected_seq))
                        expected_seq += 1
                    sys.stdout.buffer.flush()

            # nhan duoc goi data nao thi gui ack dung seq_num cua goi do
            send_ack(sock, address, seq_num)

        # xu ly goi END (type=1)
        elif pkt_type == 1:
            if seq_num == expected_seq:
                send_ack(sock, address, seq_num)
                sys.stdout.buffer.flush()
                break

    sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
