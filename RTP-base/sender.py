import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

# kich thuoc toi da goi rtp la 1472, tru 16 bytes header con 1456
MAX_DATA_SIZE = 1456
TIMEOUT = 0.5


def create_pkt(pkt_type, seq_num, data=b""):
    # tao goi tin va tinh checksum
    hdr = PacketHeader(type=pkt_type, seq_num=seq_num, length=len(data), checksum=0)
    hdr.checksum = compute_checksum(hdr / data)
    return bytes(hdr / data)


def parse_ack(raw_bytes):
    # doc goi ack nhan ve va check xem co bi loi khong
    if len(raw_bytes) < 16:
        return None
    hdr = PacketHeader(raw_bytes[:16])
    payload = raw_bytes[16 : 16 + hdr.length]

    old_crc = hdr.checksum
    hdr.checksum = 0
    if compute_checksum(hdr / payload) != old_crc:
        return None

    if hdr.type != 3:
        return None
    return hdr.seq_num


def sender(receiver_ip, receiver_port, window_size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_addr = (receiver_ip, receiver_port)

    # doc du lieu dau vao tu stdin
    raw_input = sys.stdin.buffer.read()

    # cat du lieu thanh tung doan toi da 1456 bytes
    chunks = []
    for i in range(0, len(raw_input), MAX_DATA_SIZE):
        chunks.append(raw_input[i : i + MAX_DATA_SIZE])

    total_pkts = len(chunks)

    # dong goi san cac goi data tu 1 den total_pkts
    data_pkts = {}
    for idx, chunk in enumerate(chunks):
        seq = idx + 1
        data_pkts[seq] = create_pkt(2, seq, chunk)

    # gui goi START (type=0, seq=0) va cho ACK=1
    start_pkt = create_pkt(0, 0)
    while True:
        sock.sendto(start_pkt, target_addr)
        sock.settimeout(TIMEOUT)
        try:
            resp, _ = sock.recvfrom(2048)
            ack_num = parse_ack(resp)
            if ack_num == 1:
                break
        except (socket.timeout, OSError):
            continue

    # truyen data theo sliding window voi cumulative ack
    base_seq = 1
    next_seq = 1
    timer_start = time.time()

    while base_seq <= total_pkts:
        # gui cac goi moi neu con cho trong window
        while next_seq < base_seq + window_size and next_seq <= total_pkts:
            sock.sendto(data_pkts[next_seq], target_addr)
            if base_seq == next_seq:
                timer_start = time.time()
            next_seq += 1

        # tinh thoi gian con lai cua timer 500ms
        time_left = TIMEOUT - (time.time() - timer_start)
        if time_left <= 0:
            # qua 500ms chua nhich window thi gui lai het cac goi trong window
            for s in range(base_seq, next_seq):
                sock.sendto(data_pkts[s], target_addr)
            timer_start = time.time()
            continue

        sock.settimeout(time_left)
        try:
            resp, _ = sock.recvfrom(2048)
            ack_num = parse_ack(resp)
            if ack_num is not None and base_seq < ack_num <= total_pkts + 1:
                # nhan duoc ack lon hon base_seq thi dich window len va reset timer
                base_seq = ack_num
                timer_start = time.time()
        except (socket.timeout, OSError):
            # het gio cho, vong lap sau se gui lai
            pass

    # gui goi END (type=1) de ket thuc va doi toi da 500ms
    end_seq = total_pkts + 1
    end_pkt = create_pkt(1, end_seq)
    sock.sendto(end_pkt, target_addr)
    end_start = time.time()

    while True:
        rem = TIMEOUT - (time.time() - end_start)
        if rem <= 0:
            break
        sock.settimeout(rem)
        try:
            resp, _ = sock.recvfrom(2048)
            ack_num = parse_ack(resp)
            if ack_num is not None and ack_num >= end_seq + 1:
                break
        except (socket.timeout, OSError):
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

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
