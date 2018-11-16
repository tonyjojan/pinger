import socket
import os
import time
import struct
import argparse
import sys

parser = argparse.ArgumentParser()
parser = argparse.ArgumentParser(conflict_handler= "resolve")
parser.add_argument('-p', action='store', dest='payload',
                    help='Specify the port number', required=False)
parser.add_argument('-l', action='store', dest='logfile',
                    help='Specify the string to include in the payload', required=False)
parser.add_argument('-c', action='store', dest='count',
                    help='Specify the number of packets used to compute RTT', required=False)
parser.add_argument('-d', action='store', dest='destination',
                    help='Specify the destination IP for the ping message', required=False)
results = parser.parse_args()

payload = 'Hello World'
logfile = 'log.txt'
count = 10
destination = 'www.google.com'

if results.payload is not None:
    payload = results.payload
if results.logfile is not None:
    logfile = results.logfile
if results.count is not None:
    count = int(results.count)
if results.destination is not None:
    destination = results.destination

ICMP_ECHO_REQUEST = 8

#calculates the checksum of the packet
def calculate_checksum(source_string):
    sum = 0
    count_to = (len(source_string) / 2) * 2
    count = 0
    while count < count_to:
        this_val = ord(source_string[count + 1])*256+ord(source_string[count])
        sum = sum + this_val
        sum = sum & 0xffffffff # Necessary?
        count = count + 2
    if count_to < len(source_string):
        sum = sum + ord(source_string[len(source_string) - 1])
        sum = sum & 0xffffffff # Necessary?
    sum = (sum >> 16) + (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff
    # Swap bytes. Bugger me if I know why.
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer


def send(packet_id, payload, address, p_socket):
    try:
        host = socket.gethostbyname(destination)
    except socket.gaierror:
        return -1

    #bbHHh is format of header as seen in https://docs.python.org/2/library/struct.html#format-characters
    #b - signed char, H - unsigned short, h - short

    header = struct.pack('bbHHh', ICMP_ECHO_REQUEST, 0, 0, packet_id, 1)
    checksum = calculate_checksum(header + payload)
    header = struct.pack('bbHHh', ICMP_ECHO_REQUEST, 0,
                         socket.htons(checksum), packet_id, 1)
    packet = header + payload
    while packet:
        sent = p_socket.sendto(packet, (address, 1))
        packet = packet[sent:]
    return time.time()


def receive(packet_id, p_socket, start_time, sequence_number):
    while True:
        p_socket.settimeout(1)

        try:
            r_packet, addr = p_socket.recvfrom(1024)
        except socket.timeout as e:
            print("Request time out for icmp_seq " + str(sequence_number))
            return -1
        p_socket.settimeout(None)

        end_time = time.time()
        total_time = (end_time - start_time) * 1000

        # extract icmp and ip headers from received packet
        ip_header = r_packet[0:20]
        ip_header = struct.unpack('!BBHHHBBH4s4s', ip_header)
        ttl = ip_header[5]

        icmp_header = r_packet[20:28]
        type, code, checksum, p_id, sequence = struct.unpack(
            'bbHHh', icmp_header)

        if p_id == packet_id:
            payload_size = str(sys.getsizeof(r_packet[28:]))
            print("Reply from " + str(addr[0]) + ": bytes=" + str(payload_size)
                  + " time=" + "%.2f" % total_time + "ms TTL = " + str(ttl))
            return total_time
        return -1


def pinger(pings, payload):
    number_packets_sent = 0
    number_packets_received = 0
    round_trip_times = []
    print("Pinging " + str(socket.gethostbyname(destination)) + " with " + str(sys.getsizeof(payload)) +
          " bytes of data \"" + payload + "\":")
    try:
        p_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname('icmp'))
    except socket.error as e:
        if e.errno == 1:
            e.msg += "Pinger must be a root process to run."
            raise socket.error(e.msg)
    except Exception as e:
        print("Exception: %s" % (e))

    for i in range(0, pings):
        current_packet_id = (os.getpid() + i) & 0xFFFF

        start_time = send(current_packet_id, payload, destination, p_socket)
        if start_time != -1:
            number_packets_sent = number_packets_sent + 1

        round_trip_time = receive(current_packet_id, p_socket, start_time, i)
        if round_trip_time != -1:
            number_packets_received = number_packets_received + 1

        round_trip_times.append(round_trip_time)

    percent_loss = ((number_packets_sent-number_packets_received)/count) * 100
    avg_rtt = sum(round_trip_times)/len(round_trip_times)
    min_rtt = min(round_trip_times)
    max_rtt = max(round_trip_times)
    print("Ping statistics for " + str(socket.gethostbyname(destination)) + ": ")
    print("Packets: Sent = " + str(number_packets_sent)
          + ", Received = " + str(number_packets_received)
          + ", Lost = " + str(number_packets_sent - number_packets_received)
          + " (" + str(percent_loss) + "% loss),")
    if(percent_loss != 100):
        print("Approximate round trip times in milli-seconds: ")
        print("Minimum = " + "%.2f" % min_rtt + "ms, Maximum = " + "%.2f" % max_rtt + "ms, Average = " + "%.2f" % avg_rtt + "ms")


pinger(count, payload)


