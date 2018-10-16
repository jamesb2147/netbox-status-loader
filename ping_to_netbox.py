#Copyright Sean Hunter
#Using MIT License (see license file for detail)

import json, requests, ipaddress, dns.resolver, time
#Python3 way (currently broken)
#import ping3
#Python2 way (currently the only non-broken way)
import ping
from multiprocessing import Pool

#############################################################################
#DEAR USER - YOU MUST DEFINE EVERYTHING FROM HERE ###########################
#############################################################################

#How long to wait for ping responses
timeout = 2
#Currently configured for a local run against a Docker Netbox install
#Adjust to fit your environment (in prod, probably on port 80 or 443)
ip_addresses_url = "http://localhost:32768/api/ipam/ip-addresses/"
ip_prefixes_url = "http://localhost:32768/api/ipam/prefixes/"

#Authorization header
#This must be generated from the Netbox web UI at http://netbox/user/api-tokens/
header={"Authorization": "Token _REALLY_LONG_RANDOM_STRING_"}

#Set to:
#1 - Scan RFC1918 space (192.168.0.0/16, 172.16.0.0/12, 10.0.0.0/8)
#2 - Scan IP addresses defined in Netbox
#3 - Scan prefixes defined in Netbox
load_scanner_from_rfc1918_or_netbox = 2

#OK, don't touch this line
myResolver = dns.resolver.Resolver()
#But MAKE CERTAIN that this one fits your environment; there will be reverse
#DNS requests made to this(these) server(s)
myResolver.nameservers = ['192.168.110.100','8.8.8.8']

#Determines the number of simultaneous pings to execute during timeout
#This can have a *very* high impact on performance, and can impact system
#stability so it is advised to only mess with it if you really know what you
#are doing
numProcesses = 100

#############################################################################
#THROUGH HERE ###############################################################
#############################################################################

#NOTE: Current possible status for IP addresses in Netbox include:
#1 - Active
#2 - Reserved
#3 - Deprecated
#5 - DHCP
#Don't ask what happened to 4. I assume Jeremy Stretch murdered him, the poor fellow.

def threadedPingReverseSave(addr):
	#Drop trailing /xx
	ip = (addr['address'].split("/"))[0]
	#Run ping twice - first to ensure ARP completes before second ping goes through
	#this is often visible in labs where the first ping to a newly online device will fail
	ping.do_one(ip, timeout)
	rtt = ping.do_one(ip, timeout)
	#Create the appropriate search string for a PTR record by reversing the IP space and
	#adding in-addr.arpa to the query
	dnsreq = '.'.join(reversed(ip.split("."))) + ".in-addr.arpa"
	#If the ping failed...
	if rtt == None:
		print(ip + ": NO RESPONSE BEFORE ICMP TIMEOUT EXPIRY")
		#There's not a great answer here, so we're going to assume the IP is merely reserved
		#Feel free to adjust this to your needs
		addr['status']=2
		try:
			#Do a reverse DNS (aka pointer/PTR) query
			myResolver.query(dnsreq, "PTR")
			dnsreply = myResolver.query(dnsreq, "PTR").response.answer
			for i in dnsreply:
				for j in i.items:
					#Save the reply to the description
					addr['description'] = j.to_text().rstrip('.')
					#Always save IP addresses with a reverse.
					saveAddr(addr)
		except:
			#If there is no reply, set the description variable to...
			addr['description'] = "No reverse."
			#No ping, but it is an IP-address scan, so we should save the result
			#Otherwise, it's from a prefix or RFC1918 space, so do NOT save it
			#this allows you to programmatically pull free IP addresses as needed
			if load_scanner_from_rfc1918_or_netbox == 2:
				saveAddr(addr)
			#raise

	#If the ping succeeded...
	else:
		addr['status'] = 1
		try:
			#Do a reverse DNS (aka pointer/PTR) query
			myResolver.query(dnsreq, "PTR")
			dnsreply = myResolver.query(dnsreq, "PTR").response.answer
			for i in dnsreply:
				for j in i.items:
					#Save the reply to a description variable
					desc = j.to_text()
		except:
			#If there is no reply, set the description variable to...
			desc = "No reverse.."
			#raise
		print(ip + ": " + str(rtt) + "s and reverse: " + desc)
		#Remove the right-most period (DNS resolver returns one, e.g. example.com.)
		addr['description'] = desc.rstrip('.')
		#Always save successful pings
		saveAddr(addr)
	result = addr
	return result

def saveAddr(addr):
	print("entered saveAddr")
	if addr['isNew'] == "new":
		addr.pop('isNew', None)
		post = requests.post(ip_addresses_url, headers=header, json=addr)
		print(post.status_code)
		print(post.json())
	elif addr['isNew'] == "old":
		addr.pop('isNew', None)
		try:
			role = addr['role']['value']
			addr.pop('role', None)
			addr['role'] = role
		except:
			#Do nothing
			print("Role exception.")
		post = requests.put(ip_addresses_url + str(addr['id']) + "/", headers=header, json=addr)
		print(post.status_code)
		print(post.json())
	return addr

if __name__ == '__main__':
	start_time = time.time()
	if load_scanner_from_rfc1918_or_netbox == 1:
		#Load from RFC1918
		print("Not currently loading addresses from RFC1918, even though I was told to!!")
	if load_scanner_from_rfc1918_or_netbox == 2:
		#GET IP addresses from Netbox
		response = requests.get(ip_addresses_url, headers=header)
		listOfIpsWithMask = response.json()['results']
		for ipaddr in listOfIpsWithMask:
			ipaddr['isNew'] = "old"
	if load_scanner_from_rfc1918_or_netbox == 3:
		#GET IP prefixes from Netbox
		response = requests.get(ip_prefixes_url, headers=header)
		listOfPrefixes = response.json()['results']
		print(json.dumps(listOfPrefixes, indent=4))
		listOfIps = []
		for prefixObj in listOfPrefixes:
			print(prefixObj['prefix'])
			print(ipaddress.ip_network(prefixObj['prefix']).hosts())
			for host in ipaddress.ip_network(prefixObj['prefix']).hosts():
				listOfIps.append({"address": str(host)})
		listOfIpsWithMask = listOfIps
		for ipaddr in listOfIpsWithMask:
			ipaddr['isNew'] = "new"
#		print "Stopping..." + None
	#Pretty print new copy for debugging
	print(json.dumps(listOfIpsWithMask, indent=4))
	#Multithread the process. This isn't to speed up "processing" but eliminate the 
	#wait on timeout expiry; adjust to speed up/slow down system.	
	pool = Pool(processes=numProcesses)
	#Here, we call isPingable for every entity in listOfIpsWithMask
	result = pool.map(threadedPingReverseSave, listOfIpsWithMask)
#	Presently looking at solutions that can sort this mess by IP address... currently results are unsorted.
	print(result)
	print(json.dumps(result, indent=4))
	completion_time = time.time() - start_time
	print("Run took " + format(completion_time / 60) + " minutes and " + format(completion_time % 60) + " seconds")
#	r = requests.post(ip_addresses_url, headers=header, json={"address": "192.168.3.2", "status": "1"})
#	print r.status_code
#	print r.json()
