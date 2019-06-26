# Router program that implements shortest path routing

import sys
import socket
import struct

if len(sys.argv) != 5:
	print "Usage ./%s <router_id> <nse_host> <nse_port> <router_port>" % sys.argv[0]
	exit(1)

this_router_id = int(sys.argv[1])
nse_host = sys.argv[2]
nse_port = int(sys.argv[3])
this_router_port = int(sys.argv[4])
log = open("router" + str(this_router_id) + ".log", "w+")

#----------- Router Structs -----------#

class pkt_INIT:
	def __init__(self, router_id):
		self.router_id = router_id

class pkt_HELLO:
	def __init__(self, router_id, link_id):
		self.router_id = router_id
		self.link_id = link_id

class pkt_LSPDU:
	def __init__(self, sender, router_id, link_id, cost, via):
		self.sender = sender
		self.router_id = router_id
		self.link_id =	link_id
		self.cost = cost
		self.via = via

class link_cost:
	def __init__(self, link, cost):
		self.link = link
		self.cost = cost

class circuit_DB:
	def __init__(self, nbr_link, linkcost):
		self.nbr_link = nbr_link
		self.linkcost = linkcost  # An array (with max 5 elems) of link_costs structs

#----------- Struct Conversion Funcs -----------#

# Formating convert byte array to struct
# < : little endian notation
# I : unsigned integer value
INIT_fmt = "< I"
HELLO_fmt = "< I I"
LSPDU_fmt = "< I I I I I"
circuit_DB_fmt = "< I I I I I I I I I I I"

def byte_array_to_struct(fmt, fmt_num, arr):
	s = struct.Struct(fmt)
	unpacked = s.unpack(arr)
	if fmt_num == 0:
		return pkt_INIT(unpacked[0])
	elif fmt_num == 1:
		return pkt_HELLO(unpacked[0], unpacked[1])
	elif fmt_num == 2:
		return pkt_LSPDU(unpacked[0], unpacked[1], unpacked[2], unpacked[3], unpacked[4])
	elif fmt_num == 3:
		linkcosts = []
		nbr_links = unpacked[0]
		for i in range(1, nbr_links * 2, 2):
			linkcosts += [link_cost(unpacked[i], unpacked[i+1])]
		return circuit_DB(nbr_links, linkcosts)

def struct_to_byte_array(fmt, fmt_num, p):
	s = struct.Struct(fmt)
	if fmt_num == 0:
		return s.pack(p.router_id)
	if fmt_num == 1:
		return s.pack(p.router_id, p.link_id)
	if fmt_num == 2:
		return s.pack(p.sender, p.router_id, p.link_id, p.cost, p.via)


#----------- Router Funcs -----------#

def print_lsdb(lsdb):
	log.write("# Topology Database\n")
	for i in range(len(lsdb)):
		if (lsdb[i] != []):
			log.write("R" + str(this_router_id) + " -> R" + str(i+1) + " nbr link " 
				+ str(len(lsdb[i])) + "\n")
			for j in range(len(lsdb[i])):
				log.write("R" + str(this_router_id) + " -> R" + str(i+1) + " link " + str(lsdb[i][j].link)
					+ " cost " + str(lsdb[i][j].cost) + "\n")

def print_rib(next_hop, cost):
	log.write("# RIB\n")
	for i in range(len(next_hop)):
		if i+1 == this_router_id:
			log.write("R" + str(this_router_id) + " -> R" + str(this_router_id) + " -> Local, 0\n")
		elif cost[i] == 999:
			log.write("R" + str(this_router_id) + " -> R" + str(i+1) + " -> INF, INF\n")
		else:
			log.write("R" + str(this_router_id) + " -> R" + str(i+1) + " -> R" + str(next_hop[i]) + 
				", " + str(cost[i]) + "\n")

def find_corresponding_router(lsdb, link_id, router_id):
	for i in range(len(lsdb)):
		for j in range(len(lsdb[i])):
			if i != router_id-1 and lsdb[i][j].link == link_id:
				return i+1
	return -1

def create_adjacency_matrix(lsdb):
	matrix = [[999 for x in range(len(lsdb))] for x in range(len(lsdb))]
	for i in range(len(lsdb)):
		for j in range(len(lsdb[i])):
			router_id = find_corresponding_router(lsdb, lsdb[i][j].link, i+1)
			if router_id == -1:
				continue
			matrix[i][router_id-1] = lsdb[i][j].cost
	return matrix

# Taken from https://gist.github.com/shintoishere/f0fa40fe1134b20e7729
def dijkstras_algorithm(lsdb, n_vertices):
	matrix = create_adjacency_matrix(lsdb)
	cost=[[0 for x in range(n_vertices)] for x in range(1)]
	next_hop = [-1] * n_vertices
	offsets = []
	offsets.append(this_router_id-1)
	elepos=0
	for j in range(n_vertices):
		cost[0][j]=matrix[this_router_id-1][j]
		next_hop[j]=j+1
	mini=999
	for x in range (n_vertices-1):
		mini=999
		for j in range (n_vertices):
			if cost[0][j]<=mini and j not in offsets:
				mini=cost[0][j]
				elepos=j
		offsets.append(elepos)
		for j in range (n_vertices):
			if cost[0][j] > cost[0][elepos]+matrix[elepos][j]:
				cost[0][j]=cost[0][elepos]+matrix[elepos][j]
				next_hop[j]=next_hop[elepos]
	print_rib(next_hop, cost[0])


def main():

	#----------- Network Initialization -----------#

	# Create UDP socket, open log file for writing
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(('', this_router_port))

	# Initialize the router to begin
	pkt_init = pkt_INIT(this_router_id)
	init_arr = struct_to_byte_array(INIT_fmt, 0, pkt_init)
	sock.sendto(init_arr, (nse_host, nse_port))
	log.write("R" + str(this_router_id) + " sends an INIT: router_id " + str(this_router_id) + "\n")

	# Get circuit DB from emulator
	data = sock.recv(1024)
	cdb = byte_array_to_struct(circuit_DB_fmt, 3, data)
	log.write("R" + str(this_router_id) + " recieves a CIRCUIT_DB: nbr_link " + str(cdb.nbr_link) + "\n")

	# Store network info in Routing Information Base and Link State DB
	# Send HELLO packet to each neighbour
	active_neighbours = []
	lsdb = [[],[],[],[],[]]
	for i in range(cdb.nbr_link):
		active_neighbours += [[-1, link_cost(cdb.linkcost[i].link, cdb.linkcost[i].cost)]]
		lsdb[this_router_id-1] += [link_cost(cdb.linkcost[i].link, cdb.linkcost[i].cost)]
		hello_pkt = pkt_HELLO(this_router_id, cdb.linkcost[i].link)
		hello_arr = struct_to_byte_array(HELLO_fmt, 1, hello_pkt)
		sock.sendto(hello_arr, (nse_host, nse_port))
		log.write("R" + str(this_router_id) + " sends a HELLO: router_id " + 
			str(this_router_id) +" link_id " + str(cdb.linkcost[i].link) + "\n")

	#----------- Network Optimization -----------#


	data = sock.recv(1024)
	while(data):

		# Length 8 means a HELLO packet
		if len(data) == 8:
			hello_pkt = byte_array_to_struct(HELLO_fmt, 1, data)
			log.write("R" + str(this_router_id) + " recieves a HELLO: router_id " + 
				str(hello_pkt.router_id) + " link_id " + str(hello_pkt.link_id) + "\n")
			
			# Update active neighbours
			for i in range(len(active_neighbours)):
				if active_neighbours[i][1].link == hello_pkt.link_id:
					active_neighbours[i][0] = hello_pkt.router_id

			# Send over router's Circuit DB (stored in lsdb)
			for i in range(len(lsdb[this_router_id-1])):
				lspdu_pkt = pkt_LSPDU(this_router_id, this_router_id, lsdb[this_router_id-1][i].link, 
					lsdb[this_router_id-1][i].cost, hello_pkt.link_id)
				lspdu_arr = struct_to_byte_array(LSPDU_fmt, 2, lspdu_pkt)
				sock.sendto(lspdu_arr, (nse_host, nse_port))
				log.write("R" + str(this_router_id) + " sends an LS PDU: sender " + str(lspdu_pkt.sender) +
					", router_id " + str(lspdu_pkt.router_id) + ", link_id " + str(lspdu_pkt.link_id) +
					", cost " + str(lspdu_pkt.cost) + ", via " + str(lspdu_pkt.via) + "\n")


		# Length 20 means a LSPDU packet
		if len(data) == 20:
			lspdu_pkt = byte_array_to_struct(LSPDU_fmt, 2, data)
			log.write("R" + str(this_router_id) + " recieves an LS PDU: sender " + str(lspdu_pkt.sender) +
					", router_id " + str(lspdu_pkt.router_id) + ", link_id " + str(lspdu_pkt.link_id) +
					", cost " + str(lspdu_pkt.cost) + ", via " + str(lspdu_pkt.via) + "\n")

			# Update lsdb
			entry_exists = False			
			for i in range(len(lsdb[lspdu_pkt.router_id-1])):
				if lsdb[lspdu_pkt.router_id-1][i].link == lspdu_pkt.link_id:
					print_lsdb(lsdb)
					entry_exists = True
					break

			# Add entry if it doesnt exist
			if not entry_exists:
				lsdb[lspdu_pkt.router_id-1] += [link_cost(lspdu_pkt.link_id,lspdu_pkt.cost)]
				print_lsdb(lsdb)

			# Update Routing Information Base using Dijkstra's algorithm
			dijkstras_algorithm(lsdb, len(lsdb))
			
			# Propogate LSPDU packet to neighbours if necessary (i.e. if sender is describing its own circuitDB)
			if lspdu_pkt.sender == lspdu_pkt.router_id:
				for i in range(len(active_neighbours)):
					if active_neighbours[i][0] != -1 and active_neighbours[i][0] != lspdu_pkt.sender:
						propogation_pkt = pkt_LSPDU(this_router_id, lspdu_pkt.router_id, lspdu_pkt.link_id, 
							lspdu_pkt.cost, active_neighbours[i][1].link)
						propogation_arr = struct_to_byte_array(LSPDU_fmt, 2, propogation_pkt)
						sock.sendto(propogation_arr, (nse_host, nse_port))
						log.write("R" + str(this_router_id) + " sends an LS PDU: sender " + str(propogation_pkt.sender) +
							", router_id " + str(propogation_pkt.router_id) + ", link_id " + str(propogation_pkt.link_id) +
							", cost " + str(propogation_pkt.cost) + ", via " + str(propogation_pkt.via) + "\n")

		data = sock.recv(1024)


if __name__== "__main__":
	main()

