# Our simple sender program

from socket import *
import struct
import sys
import binascii

# Packet structure used to implement GBN
class packet:
	def __init__(self, type, seqnum, length, data):
		self.type   = type
		self.seqnum = seqnum
		self.length = length
		self.data   = data

# Ensure the correct format
if len(sys.argv) != 5:
	print "Invalid arguements provided to the program"
	print "Usage ./%s <em_addr> <em_port> <ack_port> <filename>" % sys.argv[0]
	exit(1)

em_addr  = sys.argv[1]
em_port  = int(sys.argv[2])
ack_port = int(sys.argv[3])
filename = sys.argv[4]

# Files for logging
seqnum_log = open("seqnum.log", "w+")
ack_log = open("ack.log", "w+")

# --------------------- Helper functions to send/recv --------------------- #

# Setup UDP socket to send & recieve info
send_udp_sock = socket(AF_INET, SOCK_DGRAM)
recv_udp_sock = socket(AF_INET, SOCK_DGRAM)
recv_udp_sock.settimeout(.1)
recv_udp_sock.bind(('', ack_port))

# Formating convert byte array to struct
# > : big endian notation
# I : integer value
# s : string value (with size prepended)
def byte_array_to_packet(arr):
	s = struct.Struct('> I I I') # ACK packets have data of length 0
	print binascii.hexlify(arr)
	unpacked = s.unpack(arr)
	return packet(unpacked[0], unpacked[1], unpacked[2], "")

def packet_to_byte_array(p):
	s = struct.Struct('> I I I 500s')
	packed = s.pack(p.type, p.seqnum, p.length, p.data)
	return packed

# We have a timer on the UDP sock, let's see if we can get an ACK
# for send base in this time. Also drop any out of order ACK's
def check_ack():
	try:
		msg, _ = recv_udp_sock.recvfrom(12)
	except timeout:
		return -1

	p = byte_array_to_packet(msg)
	return p.seqnum

def send_pack(packet):
	seqnum_log.write(str(packet.seqnum) + "\n")
	arr = packet_to_byte_array(packet)
	send_udp_sock.sendto(arr, (em_addr, em_port))

# ------------------------- GBN setup variables -------------------------#

DATA = 1
EOT  = 2
send_base   = 0
nxt_seqnum  = 0
window_size = 10
data_buffer = [None] * window_size
ack_buffer  = [1]    * 32

# ------------------------- GBN main loop ------------------------- #

# Open the file for reading
file = open(filename, "r")
data = file.read(500)
while data or send_base != nxt_seqnum:

	# Send packets while we have room to do so
	while nxt_seqnum - send_base < window_size and data:
		p = packet(DATA, nxt_seqnum % 32, len(data), data)
		send_pack(p)
		# Store data incase we need to resend
		data_buffer[nxt_seqnum % window_size] = data
		ack_buffer[nxt_seqnum % 32] = 0
		# Get next buffer of data
		data = file.read(500)
		if data:
			nxt_seqnum += 1


	# Acknowledge packets until timer has hit or all packets have been ACKed
	retcode = 0
	while retcode >= 0 and send_base != nxt_seqnum:
		retcode = check_ack()
		if retcode != -1:
			ack_log.write(str(retcode) + "\n")
			if ack_buffer[retcode] == 0:
				while send_base % 32 != retcode:
					ack_buffer[send_base % 32] = 1
					send_base += 1

	# Resend dropped packets (or if ACKS were out of order) if any exist
	if send_base != nxt_seqnum:
		for seqnum in range(send_base, send_base + window_size):
			if ack_buffer[seqnum % 32] == 0:
				payload = data_buffer[seqnum % window_size]
				p = packet(DATA, seqnum % 32, len(payload), payload)
				send_pack(p)


# ------------------------- Close the connection ------------------------- #

# Send of the EOT packet and wait for a corresponding EOT from reciever
eot = packet(EOT, 0, 0, "")
send_pack(eot)

while True:
	try:
		msg, _ = recv_udp_sock.recvfrom(12)
		eot = byte_array_to_packet(msg)
		if eot.type == EOT:
			break
	except timeout:
		p = packet(EOT, 0, 0, "")
		send_pack(p)

# Close any open files
file.close()
ack_log.close()
seqnum_log.close()

