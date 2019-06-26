import requests
import sys
import base64

if len(sys.argv) != 2:
	print "Usage ./%s [cookie]" % sys.argv[0]
	exit(1)

# Setup
server="http://localhost:4555"
block_size=16
cookie=sys.argv[1]

# Decryption algorithm using b1 to decrypt b2
def decrypt_block(b1, b2):

	# Will use this array to brute force appropriate padding
	probe=bytearray(block_size)
	for i in reversed(range(0,block_size)):
		for j in range(0,256):
			new_cookie=base64.b64encode(probe + b2)
			cookie = dict(user=new_cookie)
			r = requests.get(server, cookies=cookie)

			# Probe to see how much padding we correctly guessed
			if r.status_code == 200:
				first_pad_index = i
				for k in range(0,i):
					probe[k] = 1 ^ probe[k]
					new_cookie=base64.b64encode(b1 + probe + b2)
                    			cookie = dict(user=new_cookie)
                    			r = requests.get(server, cookies=cookie)
					probe[k] = 1 ^ probe[k]

                    			# Once we alter a byte in the padding we should get an error
					if r.status_code == 500:
						first_pad_index = k
						break
				if i==0:
					break

				# Adjust probe array for next byte of decryption
				for k in range(first_pad_index, block_size):
					probe[k] = (probe[k] ^ ((k - first_pad_index + 1) ^ (k - first_pad_index + 2)))
				break

			else:
				probe[i] += 1

	# Get plaintext using encrypted_block_1[i] and probe[i]
	decrypted = ""
	for i in range(0,block_size):
		decrypted = decrypted + chr(probe[i] ^ ord(b1[i]) ^ (i+1))
	return decrypted

# Call decryption func on all blocks (except first one)
decrypted = ""
decoded = base64.b64decode(cookie)
while len(decoded) > block_size:
	decrypted = decrypt_block(decoded[-block_size*2:-block_size],decoded[-block_size:]) + decrypted
	decoded=decoded[:-block_size]

# Trim padding
while ord(decrypted[-1]) < block_size:
	decrypted = decrypted[:-1]
print decrypted

