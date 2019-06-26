# Our simple reciever program

from socket import *
import struct
import sys

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
	print "Usage ./%s <em_addr> <em_port> <data_port> <filename>" % sys.argv[0]
	exit(1)

em_addr   = sys.argv[1]
em_port   = int(sys.argv[2])
data_port = int(sys.argv[3])
filename  = sys.argv[4]

# --------------------- Helper functions to send/recv --------------------- #

# Setup UDP socket to send & recieve info
send_udp_sock = socket(AF_INET, SOCK_DGRAM)
recv_udp_sock = socket(AF_INET, SOCK_DGRAM)
recv_udp_sock.bind(('', data_port))

# Formating convert byte array to struct
# > : big endian notation
# I : integer value
# s : string value (with size prepended)
def byte_array_to_packet(arr):
	s = struct.Struct('> I I I 500s')
	unpacked = s.unpack(arr)
	return packet(unpacked[0], unpacked[1], unpacked[2], unpacked[3])

def packet_to_byte_array(p):
	# We can ignore the data arguement since we are only sending ACKs
	s = struct.Struct('> I I I')
	packed = s.pack(p.type, p.seqnum, p.length)
	return packed

def send_pack(packet):
	arr = packet_to_byte_array(packet)
	send_udp_sock.sendto(arr, (em_addr, em_port))

# ------------------------- GBN setup variables -------------------------#

ACK  = 0
EOT  = 2
recv_base = 0

# Open files for reading & logging
file = open(filename, "w+")
logging = open("arrival.log", "w+")

# ------------------------- GBN main loop ------------------------- #

data, _ = recv_udp_sock.recvfrom(512)
while data:

	p = byte_array_to_packet(data)
	logging.write(str(p.seqnum) + "\n")

	if p.type == EOT:
		# Send a few EOT packets for good measure
		for i in range(0, 20):
			eot_p = packet(EOT, 0, 0, "")
			send_pack(eot_p)
		break

	if p.seqnum == recv_base % 32:
		# Trim data to specified length & append to file
		trimmed_data = p.data[:p.length]
		file.write(trimmed_data)
		# Acknowledge recieved packet & increase send base
		ack_p = packet(ACK, p.seqnum, 0, "")
		send_pack(ack_p)
		recv_base += 1
	else:
		# We recieved an out of order packet, resend ACK for recent in-order packet
		ack_p = packet(ACK, max((recv_base-1) % 32, 0), 0, "")
		send_pack(ack_p)

	data, _ = recv_udp_sock.recvfrom(512)

# Close any open files
file.close()
logging.close()

